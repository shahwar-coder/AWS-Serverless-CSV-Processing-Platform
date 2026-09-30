import json
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import allure
import pytest

from application.common.aws_clients import get_dynamodb_client, get_s3_client
from application.common.config import INPUT_BUCKET, JOBS_TABLE, RESULTS_BUCKET
from application.scripts.deploy_local_backend import get_local_api_url


@dataclass(frozen=True)
class CreatedJob:
    job_id: str
    status: str
    input_bucket: str
    input_key: str
    original_filename: str
    content_type: str
    created_at: str
    upload_url: str = field(repr=False)
    upload_headers: dict[str, str] = field(repr=False)
    expires_in: int = 900


@dataclass(frozen=True)
class UploadedCsv:
    job: CreatedJob
    status_code: int


@dataclass(frozen=True)
class ProcessedJob:
    job: CreatedJob
    status: dict
    report: dict


def _attach_json(name: str, value: dict) -> None:
    allure.attach(json.dumps(value, indent=2), name, allure.attachment_type.JSON)


@pytest.fixture
def sample_csv() -> str:
    return "product,quantity,price,region\nMouse,2,500,North\nKeyboard,1,1500,South\n mouse ,1,250,East\n"


@pytest.fixture
def created_job():
    if os.getenv("RUN_FLOCI_E2E") != "1":
        pytest.skip("Set RUN_FLOCI_E2E=1 to run the Floci E2E flow")

    request_body = {"filename": "sales.csv", "content_type": "text/csv"}
    api_url = get_local_api_url()
    with allure.step("Create Job"):
        _attach_json("Create Job request", request_body)
        request = Request(
            f"{api_url}/jobs",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            status_code = response.status
            body = json.load(response)
        job_id = body.get("job_id")
        input_key = f"uploads/{job_id}/input.csv" if job_id else None

    try:
        with allure.step("Validate Create Job response"):
            assert status_code == 201
            assert body["status"] == "UPLOAD_PENDING"
            upload = body["upload"]
            assert upload["method"] == "PUT"
            assert upload["headers"] == {"Content-Type": "text/csv"}
            assert upload["expires_in"] == 900
            assert job_id is not None
            safe_url = urlsplit(upload["url"])
            _attach_json(
                "Create Job response",
                {
                    **body,
                    "upload": {
                        **upload,
                        "url": f"{safe_url.scheme}://{safe_url.netloc}{safe_url.path}?<redacted>",
                    },
                },
            )
            allure.attach(job_id, "job_id", allure.attachment_type.TEXT)

        job = CreatedJob(
            job_id=job_id,
            status=body["status"],
            input_bucket=INPUT_BUCKET,
            input_key=input_key,
            original_filename=request_body["filename"],
            content_type=request_body["content_type"],
            created_at=body["created_at"],
            upload_url=upload["url"],
            upload_headers=upload["headers"],
            expires_in=upload["expires_in"],
        )

        with allure.step("Verify DynamoDB record"):
            record = get_dynamodb_client().get_item(
                TableName=JOBS_TABLE,
                Key={"job_id": {"S": job.job_id}},
                ConsistentRead=True,
            )["Item"]
            _attach_json("DynamoDB record", record)
            assert record["job_id"]["S"] == job.job_id
            assert record["status"]["S"] == job.status
            assert record["input_bucket"]["S"] == job.input_bucket
            assert record["input_key"]["S"] == job.input_key
            assert record["original_filename"]["S"] == job.original_filename
            assert record["content_type"]["S"] == job.content_type
            assert record["created_at"]["S"] == job.created_at
            assert record["updated_at"]["S"] == job.created_at

        with allure.step("Verify HTTP job status"):
            with urlopen(f"{api_url}/jobs/{job_id}", timeout=45) as status_response:
                assert status_response.status == 200
                status = json.load(status_response)
            _attach_json("GET job response", status)
            assert status["job_id"] == job_id
            assert status["status"] == "UPLOAD_PENDING"
            assert status["filename"] == "sales.csv"
            assert status["file_size_bytes"] is None
            assert status["uploaded_at"] is None
            assert status["processing_started_at"] is None
            assert status["completed_at"] is None

        with allure.step("Verify result is not ready"):
            try:
                urlopen(f"{api_url}/jobs/{job_id}/result", timeout=45)
                pytest.fail("Result should not exist before processing")
            except HTTPError as error:
                assert error.code == 409

        yield job
    finally:
        if job_id:
            with allure.step("Clean up test job record"):
                get_dynamodb_client().delete_item(
                    TableName=JOBS_TABLE,
                    Key={"job_id": {"S": job_id}},
                )


@pytest.fixture
def uploaded_csv(created_job: CreatedJob, sample_csv: str) -> UploadedCsv:
    try:
        with allure.step("Upload CSV"):
            _attach_json(
                "Upload metadata",
                {
                    "method": "PUT",
                    "bucket": created_job.input_bucket,
                    "object_key": created_job.input_key,
                    "expires_in": created_job.expires_in,
                    "required_headers": created_job.upload_headers,
                },
            )
            allure.attach(sample_csv, "CSV payload", allure.attachment_type.TEXT)
            request = Request(
                created_job.upload_url,
                data=sample_csv.encode("utf-8"),
                headers={**created_job.upload_headers, "Origin": "http://localhost:5174"},
                method="PUT",
            )
            with urlopen(request, timeout=10) as response:
                status_code = response.status
                _attach_json("PUT response", {"status_code": status_code})
                assert status_code in (200, 201)
                assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5174"

        yield UploadedCsv(job=created_job, status_code=status_code)
    finally:
        with allure.step("Clean up test CSV object"):
            get_s3_client().delete_object(
                Bucket=created_job.input_bucket,
                Key=created_job.input_key,
            )


@pytest.fixture
def processed_job(uploaded_csv: UploadedCsv) -> ProcessedJob:
    job = uploaded_csv.job
    api_url = get_local_api_url()
    try:
        with allure.step("Wait for SQS worker completion"):
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                with urlopen(f"{api_url}/jobs/{job.job_id}", timeout=45) as response:
                    status = json.load(response)
                if status["status"] in ("COMPLETED", "FAILED"):
                    break
                time.sleep(1)
            else:
                pytest.fail("Worker did not finish within 90 seconds")
            _attach_json("Completed job status", status)
            assert status["status"] == "COMPLETED"
            assert status["filename"] == job.original_filename
            assert status["file_size_bytes"] is not None
            assert status["uploaded_at"]
            assert status["processing_started_at"]
            assert status["completed_at"]
            assert status["failed_at"] is None
            assert status["error"] is None

        with allure.step("Read result API"):
            with urlopen(f"{api_url}/jobs/{job.job_id}/result", timeout=45) as response:
                assert response.status == 200
                report = json.load(response)
            _attach_json("Result API report", report)
        yield ProcessedJob(job=job, status=status, report=report)
    finally:
        with allure.step("Clean up test report"):
            get_s3_client().delete_object(
                Bucket=RESULTS_BUCKET,
                Key=f"results/{job.job_id}/report.json",
            )
