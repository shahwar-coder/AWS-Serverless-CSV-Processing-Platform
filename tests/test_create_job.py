import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
from botocore.exceptions import ClientError

from application.common.aws_clients import get_s3_client
from application.create_job import handler as create_job


def request(filename="sales.csv", content_type="text/csv"):
    return {"body": json.dumps({"filename": filename, "content_type": content_type})}


def test_create_job_stores_record_and_returns_upload_instructions(monkeypatch):
    s3 = Mock()
    s3.generate_presigned_url.return_value = "http://localhost:4566/signed"
    dynamodb = Mock()
    monkeypatch.setattr(create_job, "get_upload_s3_client", lambda: s3)
    monkeypatch.setattr(create_job, "get_dynamodb_client", lambda: dynamodb)

    response = create_job.handler(request(), None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert body["status"] == "UPLOAD_PENDING"
    assert body["upload"] == {
        "method": "PUT",
        "url": "http://localhost:4566/signed",
        "expires_in": 900,
        "headers": {"Content-Type": "text/csv"},
    }
    assert body["job_id"]
    assert body["created_at"]
    s3.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={
            "Bucket": "serverless-csv-input",
            "Key": f"uploads/{body['job_id']}/input.csv",
            "ContentType": "text/csv",
        },
        ExpiresIn=900,
        HttpMethod="PUT",
    )
    kwargs = dynamodb.put_item.call_args.kwargs
    assert kwargs["TableName"] == "serverless-csv-jobs"
    assert kwargs["ConditionExpression"] == "attribute_not_exists(job_id)"
    assert kwargs["Item"] == {
        "job_id": {"S": body["job_id"]},
        "status": {"S": "UPLOAD_PENDING"},
        "input_bucket": {"S": "serverless-csv-input"},
        "input_key": {"S": f"uploads/{body['job_id']}/input.csv"},
        "original_filename": {"S": "sales.csv"},
        "content_type": {"S": "text/csv"},
        "attempt_count": {"N": "0"},
        "created_at": {"S": body["created_at"]},
        "updated_at": {"S": body["created_at"]},
    }


@pytest.mark.parametrize(
    "event",
    [
        {},
        None,
        {"body": "{"},
        {"body": "[]"},
        {"body": json.dumps({"content_type": "text/csv"})},
        request(filename=""),
        request(filename=".csv"),
        request(filename="report.txt"),
        request(filename="   .csv"),
        request(content_type="application/octet-stream"),
        request(content_type="TEXT/CSV"),
    ],
)
def test_invalid_request_returns_400_without_aws_calls(monkeypatch, event):
    monkeypatch.setattr(create_job, "get_upload_s3_client", lambda: pytest.fail("S3 called"))
    monkeypatch.setattr(create_job, "get_dynamodb_client", lambda: pytest.fail("DynamoDB called"))

    response = create_job.handler(event, None)

    assert response["statusCode"] == 400
    assert "error" in json.loads(response["body"])


def test_presigning_failure_does_not_create_a_job(monkeypatch):
    s3 = Mock()
    s3.generate_presigned_url.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}}, "PutObject"
    )
    dynamodb = Mock()
    monkeypatch.setattr(create_job, "get_upload_s3_client", lambda: s3)
    monkeypatch.setattr(create_job, "get_dynamodb_client", lambda: dynamodb)

    response = create_job.handler(request(), None)

    assert response["statusCode"] == 500
    dynamodb.put_item.assert_not_called()


def test_dynamodb_failure_returns_server_error(monkeypatch):
    s3 = Mock()
    s3.generate_presigned_url.return_value = "http://localhost:4566/signed"
    dynamodb = Mock()
    dynamodb.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
        "PutItem",
    )
    monkeypatch.setattr(create_job, "get_upload_s3_client", lambda: s3)
    monkeypatch.setattr(create_job, "get_dynamodb_client", lambda: dynamodb)

    response = create_job.handler(request(), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Could not create job."}


def test_real_s3_client_signs_content_type_with_path_style_url():
    url = get_s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": "serverless-csv-input",
            "Key": "uploads/example/input.csv",
            "ContentType": "text/csv",
        },
        ExpiresIn=900,
        HttpMethod="PUT",
    )

    parsed = urlparse(url)
    assert parsed.netloc == "localhost:4566"
    assert parsed.path == "/serverless-csv-input/uploads/example/input.csv"
    assert "content-type" in parse_qs(parsed.query)["X-Amz-SignedHeaders"][0]
