"""List recent jobs for the local dashboard history."""

import logging

from botocore.exceptions import BotoCoreError, ClientError

from application.common.aws_clients import get_dynamodb_client
from application.common.config import JOBS_TABLE
from application.common.http import response


logger = logging.getLogger(__name__)
HISTORY_LIMIT = 50


def handler(event: dict, context: object) -> dict:
    try:
        db = get_dynamodb_client()
        items = []
        next_key = None
        while True:
            params = {"TableName": JOBS_TABLE, "ProjectionExpression": "job_id, #status, original_filename, created_at, updated_at, file_size_bytes", "ExpressionAttributeNames": {"#status": "status"}}
            if next_key:
                params["ExclusiveStartKey"] = next_key
            page = db.scan(**params)
            items.extend(page.get("Items", []))
            next_key = page.get("LastEvaluatedKey")
            if not next_key:
                break
    except (BotoCoreError, ClientError):
        logger.exception("Could not list jobs")
        return response(500, {"error": "Could not list jobs."})

    items.sort(key=lambda item: (item["created_at"]["S"], item["job_id"]["S"]), reverse=True)
    jobs = [{
        "job_id": item["job_id"]["S"],
        "status": item["status"]["S"],
        "filename": item["original_filename"]["S"],
        "created_at": item["created_at"]["S"],
        "updated_at": item["updated_at"]["S"],
        "file_size_bytes": int(item["file_size_bytes"]["N"]) if item.get("file_size_bytes") else None,
    } for item in items[:HISTORY_LIMIT]]
    return response(200, {"jobs": jobs})
