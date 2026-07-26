from botocore.exceptions import ClientError

from application.common.aws_clients import (
    get_dynamodb_client,
    get_s3_client,
)

INPUT_BUCKET = "serverless-csv-input"
RESULTS_BUCKET = "serverless-csv-results"
JOBS_TABLE = "serverless-csv-jobs"


def delete_bucket_if_exists(bucket_name: str) -> None:
    """Delete a bucket only when present, keeping repeated cleanup runs idempotent. No missing bucket errors ever."""
    s3_client = get_s3_client()

    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError:
        print(f"Bucket does not exist: {bucket_name}")
        return

    response = s3_client.list_objects_v2(Bucket=bucket_name)

    objects = [
        {"Key": item["Key"]}
        for item in response.get("Contents", [])
    ]

    if objects:
        s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": objects},
        )

    s3_client.delete_bucket(Bucket=bucket_name)
    print(f"Bucket deleted: {bucket_name}")


def delete_jobs_table_if_exists(table_name: str) -> None:
    """Delete a DynamoDB table only when present, keeping cleanup idempotent."""
    dynamodb_client = get_dynamodb_client()

    try:
        dynamodb_client.describe_table(TableName=table_name)
    except dynamodb_client.exceptions.ResourceNotFoundException:
        print(f"Table does not exist: {table_name}")
        return

    dynamodb_client.delete_table(TableName=table_name)
    print(f"Table deleted: {table_name}")


def main() -> None:
    delete_bucket_if_exists(INPUT_BUCKET)
    delete_bucket_if_exists(RESULTS_BUCKET)
    delete_jobs_table_if_exists(JOBS_TABLE)


if __name__ == "__main__":
    main()
