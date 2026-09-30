"""Create local AWS resources used by the CSV processing platform.

Run from the project root with:
    python -m application.scripts.create_local_resources
"""

import json

from botocore.exceptions import ClientError

from application.common.aws_clients import (
    get_dynamodb_client,
    get_s3_client,
    get_sqs_client,
)
from application.common.config import (
    INPUT_BUCKET,
    JOBS_TABLE,
    PROCESSING_QUEUE_NAME,
    RESULTS_BUCKET,
)


PROCESSING_NOTIFICATION_ID = "CsvInputToProcessingQueue"
S3_SEND_MESSAGE_SID = "AllowInputBucketNotifications"


def create_bucket_if_missing(bucket_name: str) -> None:
    """Create a bucket only when absent, keeping repeated setup runs idempotent. No duplicates ever."""
    s3_client = get_s3_client()

    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket already exists: {bucket_name}")
        return
    except ClientError:
        pass

    s3_client.create_bucket(Bucket=bucket_name)
    print(f"Bucket created: {bucket_name}")


def create_jobs_table_if_missing() -> None:
    """Create the jobs table only when absent, keeping repeated setup runs idempotent."""
    dynamodb_client = get_dynamodb_client()

    try:
        dynamodb_client.describe_table(TableName=JOBS_TABLE)
        print(f"Table already exists: {JOBS_TABLE}")
        return
    except dynamodb_client.exceptions.ResourceNotFoundException:
        pass

    dynamodb_client.create_table(
        TableName=JOBS_TABLE,
        KeySchema=[
            {
                "AttributeName": "job_id",
                "KeyType": "HASH",
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "job_id",
                "AttributeType": "S",
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    print(f"Table created: {JOBS_TABLE}")


def ensure_processing_queue() -> str:
    """Create the standard queue if absent and allow input-bucket notifications."""
    sqs_client = get_sqs_client()
    try:
        queue_url = sqs_client.get_queue_url(QueueName=PROCESSING_QUEUE_NAME)["QueueUrl"]
    except ClientError as error:
        if error.response["Error"]["Code"] not in (
            "AWS.SimpleQueueService.NonExistentQueue",
            "QueueDoesNotExist",
        ):
            raise
        queue_url = sqs_client.create_queue(QueueName=PROCESSING_QUEUE_NAME)["QueueUrl"]
    attributes = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn", "Policy"],
    )["Attributes"]
    queue_arn = attributes["QueueArn"]
    arn_parts = queue_arn.split(":")
    partition, account_id = arn_parts[1], arn_parts[4]
    statement = {
        "Sid": S3_SEND_MESSAGE_SID,
        "Effect": "Allow",
        "Principal": {"Service": "s3.amazonaws.com"},
        "Action": "sqs:SendMessage",
        "Resource": queue_arn,
        "Condition": {
            "ArnEquals": {"aws:SourceArn": f"arn:{partition}:s3:::{INPUT_BUCKET}"},
            "StringEquals": {"aws:SourceAccount": account_id},
        },
    }
    policy = json.loads(attributes["Policy"]) if attributes.get("Policy") else {
        "Version": "2012-10-17",
        "Statement": [],
    }
    statements = policy["Statement"]
    if isinstance(statements, dict):
        statements = [statements]
    updated = [item for item in statements if item.get("Sid") != S3_SEND_MESSAGE_SID]
    updated.append(statement)
    if updated != statements:
        policy["Statement"] = updated
        sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={"Policy": json.dumps(policy)},
        )

    print(f"Queue ready: {PROCESSING_QUEUE_NAME}")
    return queue_arn


def ensure_input_bucket_notification(queue_arn: str) -> None:
    """Add the managed S3-to-SQS rule without replacing unrelated rules."""
    s3_client = get_s3_client()
    current = s3_client.get_bucket_notification_configuration(Bucket=INPUT_BUCKET)
    configuration = {
        name: current[name]
        for name in (
            "TopicConfigurations",
            "QueueConfigurations",
            "LambdaFunctionConfigurations",
            "EventBridgeConfiguration",
        )
        if name in current
    }
    rule = {
        "Id": PROCESSING_NOTIFICATION_ID,
        "QueueArn": queue_arn,
        "Events": ["s3:ObjectCreated:Put"],
        "Filter": {
            "Key": {
                "FilterRules": [
                    {"Name": "prefix", "Value": "uploads/"},
                    {"Name": "suffix", "Value": ".csv"},
                ]
            }
        },
    }
    existing = configuration.get("QueueConfigurations", [])
    if any(item.get("Id") == PROCESSING_NOTIFICATION_ID and item == rule for item in existing):
        print("Input bucket notification already configured")
        return
    configuration["QueueConfigurations"] = [
        item for item in existing if item.get("Id") != PROCESSING_NOTIFICATION_ID
    ] + [rule]
    s3_client.put_bucket_notification_configuration(
        Bucket=INPUT_BUCKET,
        NotificationConfiguration=configuration,
    )
    print("Input bucket notification configured")


def main() -> None:
    create_bucket_if_missing(INPUT_BUCKET)
    create_bucket_if_missing(RESULTS_BUCKET)
    create_jobs_table_if_missing()
    queue_arn = ensure_processing_queue()
    ensure_input_bucket_notification(queue_arn)

if __name__ == "__main__":
    main()
