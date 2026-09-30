import json
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from application.get_job import handler as get_job
from application.get_result import handler as get_result
from application.process_csv import handler as worker
from application.process_csv.parser import CsvValidationError, summarize_csv


JOB_ID = str(uuid4())
EVENT = {"pathParameters": {"jobId": JOB_ID}}


def _job(status="UPLOAD_PENDING"):
    return {
        "job_id": {"S": JOB_ID},
        "status": {"S": status},
        "created_at": {"S": "2026-01-01T00:00:00+00:00"},
        "updated_at": {"S": "2026-01-01T00:00:00+00:00"},
        "original_filename": {"S": "sales.csv"},
    }


def test_get_job_returns_status_and_not_found(monkeypatch):
    db = Mock()
    db.get_item.return_value = {"Item": _job()}
    monkeypatch.setattr(get_job, "get_dynamodb_client", lambda: db)
    result = get_job.handler(EVENT, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["status"] == "UPLOAD_PENDING"
    assert body["filename"] == "sales.csv"
    assert body["file_size_bytes"] is None
    assert body["uploaded_at"] is None
    assert body["processing_started_at"] is None
    assert body["completed_at"] is None
    assert body["failed_at"] is None
    assert body["error"] is None

    completed = _job("COMPLETED")
    completed["file_size_bytes"] = {"N": "24576"}
    completed["uploaded_at"] = {"S": "2026-01-01T00:00:02+00:00"}
    completed["completed_at"] = {"S": "2026-01-01T00:00:05+00:00"}
    db.get_item.return_value = {"Item": completed}
    body = json.loads(get_job.handler(EVENT, None)["body"])
    assert body["file_size_bytes"] == 24576
    assert body["uploaded_at"] == "2026-01-01T00:00:02+00:00"
    assert body["completed_at"] == "2026-01-01T00:00:05+00:00"
    db.get_item.return_value = {}
    assert get_job.handler(EVENT, None)["statusCode"] == 404
    assert get_job.handler({"pathParameters": {"jobId": "bad"}}, None)["statusCode"] == 400


def test_get_result_only_reads_completed_report(monkeypatch):
    db = Mock()
    s3 = Mock()
    db.get_item.return_value = {"Item": _job()}
    monkeypatch.setattr(get_result, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(get_result, "get_s3_client", lambda: s3)
    assert get_result.handler(EVENT, None)["statusCode"] == 409
    s3.get_object.assert_not_called()

    db.get_item.return_value = {"Item": _job("FAILED")}
    assert get_result.handler(EVENT, None)["statusCode"] == 409
    db.get_item.return_value = {}
    assert get_result.handler(EVENT, None)["statusCode"] == 404

    db.get_item.return_value = {"Item": _job("COMPLETED")}
    s3.get_object.return_value = {"Body": Mock(read=lambda: b'{"row_count": 2}')}
    response = get_result.handler(EVENT, None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["row_count"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        b"wrong,quantity,price\nMouse,2,500\n",
        b"product,quantity,price\nMouse,x,500\n",
        b"product,quantity,price\nMouse,2,NaN\n",
        b"product,quantity,price\n,2,500\n",
        b'"broken\n',
        b"\xff",
    ],
)
def test_invalid_csv_is_rejected(payload):
    with pytest.raises(CsvValidationError):
        summarize_csv(payload)


def test_csv_summary_uses_exact_decimal_arithmetic():
    assert summarize_csv(
        b"price,region,product,quantity\n0.10,North,Mouse,2\n\n0.20,South, mouse ,1\n0.30,West,iPhone,1\n"
    ) == {
        "currency": "INR",
        "row_count": 3,
        "total_quantity": 4,
        "total_revenue": "0.70",
        "unique_products": 2,
        "products": [
            {"product": "Mouse", "quantity": 3, "revenue": "0.40"},
            {"product": "iPhone", "quantity": 1, "revenue": "0.30"},
        ],
    }


def test_csv_limits_are_enforced():
    with pytest.raises(CsvValidationError, match="5 MiB"):
        summarize_csv(b"x" * (5 * 1024 * 1024 + 1))
    rows = ["product,quantity,price"] + [f"Product {index},1,1" for index in range(1001)]
    with pytest.raises(CsvValidationError, match="1,000-product"):
        summarize_csv("\n".join(rows).encode())


def test_worker_writes_report_then_completes(monkeypatch):
    db = Mock()
    s3 = Mock()
    payload = b"product,quantity,price\nMouse,2,500\n"
    s3.get_object.return_value = {
        "Body": Mock(read=lambda: payload),
        "ContentLength": len(payload),
        "LastModified": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(worker, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(worker, "get_s3_client", lambda: s3)
    event = {"Records": [{"body": json.dumps({"Records": [{
        "eventName": "ObjectCreated:Put",
        "s3": {"bucket": {"name": "serverless-csv-input"},
               "object": {"key": f"uploads/{JOB_ID}/input.csv"}},
    }]})}]}

    worker.handler(event, None)

    assert db.update_item.call_count == 3
    assert "lease_expires_at < :now" in db.update_item.call_args_list[0].kwargs["ConditionExpression"]
    assert "processing_started_at = if_not_exists" in db.update_item.call_args_list[0].kwargs["UpdateExpression"]
    metadata = db.update_item.call_args_list[1].kwargs["ExpressionAttributeValues"]
    assert metadata[":size"] == {"N": str(len(payload))}
    assert metadata[":uploaded"] == {"S": "2026-01-01T00:00:00+00:00"}
    assert s3.put_object.call_args.kwargs["Key"] == f"results/{JOB_ID}/report.json"
    assert json.loads(s3.put_object.call_args.kwargs["Body"])["total_revenue"] == "1000"
    assert db.update_item.call_args.kwargs["ExpressionAttributeValues"][":completed"] == {"S": "COMPLETED"}


def test_worker_skips_duplicate_completed_event(monkeypatch):
    db = Mock()
    db.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
    )
    db.get_item.return_value = {"Item": _job("COMPLETED")}
    s3 = Mock()
    monkeypatch.setattr(worker, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(worker, "get_s3_client", lambda: s3)
    worker._process_record({
        "eventName": "ObjectCreated:Put",
        "s3": {"bucket": {"name": "serverless-csv-input"},
               "object": {"key": f"uploads/{JOB_ID}/input.csv"}},
    })
    s3.get_object.assert_not_called()


def test_worker_marks_invalid_csv_failed(monkeypatch):
    db = Mock()
    s3 = Mock()
    payload = b"bad,header\n1,2\n"
    s3.get_object.return_value = {
        "Body": Mock(read=lambda: payload),
        "ContentLength": len(payload),
        "LastModified": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(worker, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(worker, "get_s3_client", lambda: s3)
    worker._process_record({
        "eventName": "ObjectCreated:Put",
        "s3": {"bucket": {"name": "serverless-csv-input"},
               "object": {"key": f"uploads/{JOB_ID}/input.csv"}},
    })
    assert db.update_item.call_args.kwargs["ExpressionAttributeValues"][":failed"] == {"S": "FAILED"}
    assert db.update_item.call_args.kwargs["ExpressionAttributeValues"][":now"]["S"]
    assert db.update_item.call_args_list[1].kwargs["ExpressionAttributeValues"][":size"] == {"N": str(len(payload))}
    s3.put_object.assert_not_called()


def test_oversize_object_is_not_read(monkeypatch):
    db = Mock()
    body = Mock()
    s3 = Mock()
    s3.get_object.return_value = {
        "Body": body,
        "ContentLength": 5 * 1024 * 1024 + 1,
        "LastModified": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(worker, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(worker, "get_s3_client", lambda: s3)
    worker._process_record({
        "eventName": "ObjectCreated:Put",
        "s3": {"bucket": {"name": "serverless-csv-input"},
               "object": {"key": f"uploads/{JOB_ID}/input.csv"}},
    })
    body.read.assert_not_called()
    assert db.update_item.call_args.kwargs["ExpressionAttributeValues"][":failed"] == {"S": "FAILED"}


def test_transient_s3_failure_keeps_job_retryable(monkeypatch):
    db = Mock()
    s3 = Mock()
    s3.get_object.side_effect = ClientError({"Error": {"Code": "InternalError"}}, "GetObject")
    monkeypatch.setattr(worker, "get_dynamodb_client", lambda: db)
    monkeypatch.setattr(worker, "get_s3_client", lambda: s3)
    with pytest.raises(ClientError):
        worker._process_record({
            "eventName": "ObjectCreated:Put",
            "s3": {"bucket": {"name": "serverless-csv-input"},
                   "object": {"key": f"uploads/{JOB_ID}/input.csv"}},
        })
    assert db.update_item.call_count == 1
