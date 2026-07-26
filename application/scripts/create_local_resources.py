"""Create local AWS resources used by the CSV processing platform.

Run from the project root with:
    python -m application.scripts.create_local_resources
"""

from botocore.exceptions import ClientError

from application.common.aws_clients import (
    get_s3_client,
    get_dynamodb_client
    )


INPUT_BUCKET = "serverless-csv-input"
RESULTS_BUCKET = "serverless-csv-results"
JOBS_TABLE = "serverless-csv-jobs"


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


def main() -> None:
    create_bucket_if_missing(INPUT_BUCKET)
    create_bucket_if_missing(RESULTS_BUCKET)
    create_jobs_table_if_missing()

if __name__ == "__main__":
    main()
