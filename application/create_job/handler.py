"""Create a job and return a signed URL for its CSV upload."""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from application.common.aws_clients import get_dynamodb_client, get_upload_s3_client
from application.common.config import INPUT_BUCKET, JOBS_TABLE
from application.common.http import response


logger = logging.getLogger(__name__)
UPLOAD_URL_EXPIRES_IN = 900
CONTENT_TYPE = "text/csv"


def handler(event: dict, context: object) -> dict:
    """Handle a Lambda-style create-job request."""
    try:
        body = json.loads(event["body"])
    except (KeyError, TypeError, ValueError):
        return response(400, {"error": "Request body must be a JSON object."})

    if not isinstance(body, dict):
        return response(400, {"error": "Request body must be a JSON object."})

    filename = body.get("filename")
    if (
        not isinstance(filename, str)
        or not filename.strip()
        or not filename.strip().lower().endswith(".csv")
        or len(filename.strip()) <= 4
    ):
        return response(400, {"error": "filename must be a nonempty CSV filename."})
    filename = filename.strip()

    if body.get("content_type") != CONTENT_TYPE:
        return response(400, {"error": "content_type must be text/csv."})

    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    input_key = f"uploads/{job_id}/input.csv"

    try:
        upload_url = get_upload_s3_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": INPUT_BUCKET,
                "Key": input_key,
                "ContentType": CONTENT_TYPE,
            },
            ExpiresIn=UPLOAD_URL_EXPIRES_IN,
            HttpMethod="PUT",
        )
        get_dynamodb_client().put_item(
            TableName=JOBS_TABLE,
            Item={
                "job_id": {"S": job_id},
                "status": {"S": "UPLOAD_PENDING"},
                "input_bucket": {"S": INPUT_BUCKET},
                "input_key": {"S": input_key},
                "original_filename": {"S": filename},
                "content_type": {"S": CONTENT_TYPE},
                "attempt_count": {"N": "0"},
                "created_at": {"S": created_at},
                "updated_at": {"S": created_at},
            },
            ConditionExpression="attribute_not_exists(job_id)",
        )
    except (BotoCoreError, ClientError):
        logger.exception("Failed to create job %s", job_id)
        return response(500, {"error": "Could not create job."})

    return response(
        201,
        {
            "job_id": job_id,
            "status": "UPLOAD_PENDING",
            "created_at": created_at,
            "upload": {
                "method": "PUT",
                "url": upload_url,
                "expires_in": UPLOAD_URL_EXPIRES_IN,
                "headers": {"Content-Type": CONTENT_TYPE},
            },
        },
    )
