from decimal import Decimal
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import allure

from application.common.aws_clients import get_s3_client
from application.scripts.deploy_local_backend import get_local_api_url


@allure.feature("CSV Processing")
@allure.story("Create Job, Process CSV, and Read Result")
@allure.title("Process an uploaded CSV through the HTTP API")
def test_create_job_and_upload_csv(processed_job, sample_csv):
    job = processed_job.job

    with allure.step("Verify S3 object"):
        assert job.input_key == f"uploads/{job.job_id}/input.csv"
        stored = get_s3_client().get_object(Bucket=job.input_bucket, Key=job.input_key)
        assert stored["ContentType"] == job.content_type
        contents = stored["Body"].read()
        allure.attach(job.input_key, "Object key", allure.attachment_type.TEXT)
        allure.attach(contents.decode("utf-8"), "Stored CSV", allure.attachment_type.TEXT)
        assert contents == sample_csv.encode("utf-8")

    with allure.step("Verify CSV summary"):
        assert processed_job.report == {
            "job_id": job.job_id,
            "currency": "INR",
            "row_count": 3,
            "total_quantity": 4,
            "total_revenue": "2750",
            "unique_products": 2,
            "products": [
                {"product": "Keyboard", "quantity": 1, "revenue": "1500"},
                {"product": "Mouse", "quantity": 3, "revenue": "1250"},
            ],
        }
        assert processed_job.status["file_size_bytes"] == len(sample_csv.encode("utf-8"))
        assert sum(item["quantity"] for item in processed_job.report["products"]) == 4
        assert sum(Decimal(item["revenue"]) for item in processed_job.report["products"]) == Decimal("2750")


@allure.feature("CSV Processing")
@allure.story("Invalid CSV")
@allure.title("Keep upload metadata when CSV validation fails")
def test_invalid_csv_retains_upload_metadata(created_job):
    payload = b"product,quantity,price\nMouse,bad,500\n"
    api_url = get_local_api_url()
    try:
        with allure.step("Upload invalid CSV"):
            request = Request(
                created_job.upload_url,
                data=payload,
                headers={**created_job.upload_headers, "Origin": "http://localhost:5174"},
                method="PUT",
            )
            with urlopen(request, timeout=10) as response:
                assert response.status in (200, 201)

        with allure.step("Wait for FAILED status"):
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                with urlopen(f"{api_url}/jobs/{created_job.job_id}", timeout=45) as response:
                    status = json.load(response)
                if status["status"] == "FAILED":
                    break
                time.sleep(1)
            else:
                raise AssertionError("Invalid CSV was not marked FAILED")
            allure.attach(json.dumps(status, indent=2), "Failed job status", allure.attachment_type.JSON)
            assert status["file_size_bytes"] == len(payload)
            assert status["uploaded_at"]
            assert status["processing_started_at"]
            assert status["failed_at"]
            assert status["completed_at"] is None
            assert "Invalid number" in status["error"]

        with allure.step("Verify result is unavailable"):
            try:
                urlopen(f"{api_url}/jobs/{created_job.job_id}/result", timeout=45)
                raise AssertionError("Failed job should not have a report")
            except HTTPError as error:
                assert error.code == 409
                assert json.load(error)["status"] == "FAILED"
    finally:
        with allure.step("Clean up invalid CSV object"):
            get_s3_client().delete_object(
                Bucket=created_job.input_bucket,
                Key=created_job.input_key,
            )
