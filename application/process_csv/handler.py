"""Process S3 ObjectCreated events delivered by SQS."""

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus
from uuid import UUID

from botocore.exceptions import ClientError

from application.common.aws_clients import get_dynamodb_client, get_s3_client
from application.common.config import INPUT_BUCKET, JOBS_TABLE, PROCESSING_LEASE_SECONDS, RESULTS_BUCKET
from application.process_csv.parser import MAX_CSV_BYTES, CsvValidationError, summarize_csv


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _process_record(record: dict) -> None:
    if record.get("eventName") != "ObjectCreated:Put":
        return
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    parts = key.split("/")
    if bucket != INPUT_BUCKET or len(parts) != 3 or parts[0] != "uploads" or parts[2] != "input.csv":
        return
    job_id = parts[1]
    try:
        if str(UUID(job_id)) != job_id:
            return
    except ValueError:
        return

    db = get_dynamodb_client()
    now = _now()
    lease = (datetime.now(timezone.utc) + timedelta(seconds=PROCESSING_LEASE_SECONDS)).isoformat()
    key_spec = {"job_id": {"S": job_id}}
    try:
        db.update_item(
            TableName=JOBS_TABLE,
            Key=key_spec,
            UpdateExpression="SET #status = :processing, lease_expires_at = :lease, updated_at = :now, processing_started_at = if_not_exists(processing_started_at, :now) ADD attempt_count :one",
            ConditionExpression="#status = :pending OR (#status = :processing AND lease_expires_at < :now)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":pending": {"S": "UPLOAD_PENDING"},
                ":processing": {"S": "PROCESSING"},
                ":lease": {"S": lease},
                ":now": {"S": now},
                ":one": {"N": "1"},
            },
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        item = db.get_item(TableName=JOBS_TABLE, Key=key_spec, ConsistentRead=True).get("Item")
        if not item or item["status"]["S"] in ("COMPLETED", "FAILED"):
            return
        raise RuntimeError(f"Job {job_id} is still being processed") from error

    s3 = get_s3_client()
    try:
        source = s3.get_object(Bucket=bucket, Key=key)
        try:
            file_size_bytes = source["ContentLength"]
            uploaded_at = source["LastModified"].astimezone(timezone.utc).isoformat()
            db.update_item(
                TableName=JOBS_TABLE,
                Key=key_spec,
                UpdateExpression="SET uploaded_at = :uploaded, file_size_bytes = :size, updated_at = :now",
                ConditionExpression="#status = :processing AND lease_expires_at = :lease",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":processing": {"S": "PROCESSING"},
                    ":lease": {"S": lease},
                    ":uploaded": {"S": uploaded_at},
                    ":size": {"N": str(file_size_bytes)},
                    ":now": {"S": _now()},
                },
            )
            if file_size_bytes > MAX_CSV_BYTES:
                raise CsvValidationError("CSV exceeds the 5 MiB size limit.")
            payload = source["Body"].read()
        finally:
            source["Body"].close()
        summary = summarize_csv(payload)
    except CsvValidationError as error:
        failed_at = _now()
        db.update_item(
            TableName=JOBS_TABLE,
            Key=key_spec,
            UpdateExpression="SET #status = :failed, #error = :error, failed_at = :now, updated_at = :now REMOVE lease_expires_at",
            ConditionExpression="#status = :processing AND lease_expires_at = :lease",
            ExpressionAttributeNames={"#status": "status", "#error": "error"},
            ExpressionAttributeValues={
                ":failed": {"S": "FAILED"},
                ":processing": {"S": "PROCESSING"},
                ":error": {"S": str(error)},
                ":now": {"S": failed_at},
                ":lease": {"S": lease},
            },
        )
        return

    report = {"job_id": job_id, **summary}
    s3.put_object(
        Bucket=RESULTS_BUCKET,
        Key=f"results/{job_id}/report.json",
        Body=json.dumps(report).encode("utf-8"),
        ContentType="application/json",
    )
    completed_at = _now()
    db.update_item(
        TableName=JOBS_TABLE,
        Key=key_spec,
        UpdateExpression="SET #status = :completed, completed_at = :now, updated_at = :now REMOVE lease_expires_at",
        ConditionExpression="#status = :processing AND lease_expires_at = :lease",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":completed": {"S": "COMPLETED"},
            ":processing": {"S": "PROCESSING"},
            ":now": {"S": completed_at},
            ":lease": {"S": lease},
        },
    )


def handler(event: dict, context: object) -> None:
    for message in event["Records"]:
        for record in json.loads(message["body"])["Records"]:
            _process_record(record)
