"""Read the public status of one CSV job."""

import logging
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError

from application.common.aws_clients import get_dynamodb_client
from application.common.config import JOBS_TABLE
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
            TableName=JOBS_TABLE,
            Key={"job_id": {"S": job_id}},
            ConsistentRead=True,
        ).get("Item")
    except (BotoCoreError, ClientError):
        logger.exception("Could not read job %s", job_id)
        return response(500, {"error": "Could not read job."})
    if not item:
        return response(404, {"error": "Job not found."})
    body = {key: item[key]["S"] for key in ("job_id", "status", "created_at", "updated_at")}
    body["filename"] = item["original_filename"]["S"]
    body["file_size_bytes"] = (
        int(item["file_size_bytes"]["N"]) if item.get("file_size_bytes") else None
    )
    for field in ("uploaded_at", "processing_started_at", "completed_at", "failed_at", "error"):
        body[field] = item[field]["S"] if item.get(field) else None
    return response(200, body)
