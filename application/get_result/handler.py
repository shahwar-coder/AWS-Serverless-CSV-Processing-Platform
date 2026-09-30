"""Return the JSON report of a completed CSV job."""

import json
import logging
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError

from application.common.aws_clients import get_dynamodb_client, get_s3_client
from application.common.config import JOBS_TABLE, RESULTS_BUCKET
from application.common.http import response


logger = logging.getLogger(__name__)


def handler(event: dict, context: object) -> dict:
    job_id = ((event or {}).get("pathParameters") or {}).get("jobId")
    try:
        if str(UUID(job_id)) != job_id:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        return response(400, {"error": "Invalid job_id."})
    try:
        item = get_dynamodb_client().get_item(
            TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}, ConsistentRead=True
        ).get("Item")
        if not item:
            return response(404, {"error": "Job not found."})
        if item["status"]["S"] != "COMPLETED":
            return response(409, {"error": "Result is not available.", "status": item["status"]["S"]})
        result = get_s3_client().get_object(
            Bucket=RESULTS_BUCKET, Key=f"results/{job_id}/report.json"
        )
        return response(200, json.loads(result["Body"].read()))
    except (BotoCoreError, ClientError, ValueError):
        logger.exception("Could not read result for %s", job_id)
        return response(500, {"error": "Could not read result."})
