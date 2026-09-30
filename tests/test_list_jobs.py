import json
from unittest.mock import Mock

from botocore.exceptions import ClientError

from application.list_jobs import handler as list_jobs


def _item(number):
    return {
        "job_id": {"S": f"job-{number}"},
        "status": {"S": "COMPLETED"},
        "original_filename": {"S": f"sales-{number}.csv"},
        "created_at": {"S": f"2026-10-01T00:{number:02d}:00+00:00"},
        "updated_at": {"S": f"2026-10-01T00:{number:02d}:05+00:00"},
        "file_size_bytes": {"N": "42"},
        "attempt_count": {"N": "2"},
    }


def test_list_jobs_reads_all_pages_and_returns_newest_public_summaries(monkeypatch):
    db = Mock()
    db.scan.side_effect = [
        {"Items": [_item(1), _item(3)], "LastEvaluatedKey": {"job_id": {"S": "job-3"}}},
        {"Items": [_item(2)]},
    ]
    monkeypatch.setattr(list_jobs, "get_dynamodb_client", lambda: db)
    result = list_jobs.handler({}, None)
    assert result["statusCode"] == 200
    jobs = json.loads(result["body"])["jobs"]
    assert [job["job_id"] for job in jobs] == ["job-3", "job-2", "job-1"]
    assert jobs[0]["file_size_bytes"] == 42
    assert "attempt_count" not in jobs[0]
    assert db.scan.call_args_list[1].kwargs["ExclusiveStartKey"] == {"job_id": {"S": "job-3"}}


def test_list_jobs_limits_output_to_50(monkeypatch):
    db = Mock()
    db.scan.return_value = {"Items": [_item(number) for number in range(60)]}
    monkeypatch.setattr(list_jobs, "get_dynamodb_client", lambda: db)
    jobs = json.loads(list_jobs.handler({}, None)["body"])["jobs"]
    assert len(jobs) == 50
    assert jobs[0]["job_id"] == "job-59"


def test_list_jobs_returns_safe_error(monkeypatch):
    db = Mock()
    db.scan.side_effect = ClientError({"Error": {"Code": "InternalServerError", "Message": "private detail"}}, "Scan")
    monkeypatch.setattr(list_jobs, "get_dynamodb_client", lambda: db)
    result = list_jobs.handler({}, None)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"error": "Could not list jobs."}
