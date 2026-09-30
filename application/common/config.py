"""Shared AWS environment settings for local Boto3 and CLI-compatible access."""

import os


AWS_ENDPOINT_URL = os.getenv(
    "AWS_ENDPOINT_URL",
    "http://localhost:4566",
)

AWS_REGION = os.getenv(
    "AWS_DEFAULT_REGION",
    "us-east-1",
)

AWS_ACCESS_KEY_ID = os.getenv(
    "AWS_ACCESS_KEY_ID",
    "test",
)

AWS_SECRET_ACCESS_KEY = os.getenv(
    "AWS_SECRET_ACCESS_KEY",
    "test",
)

AWS_PUBLIC_ENDPOINT_URL = os.getenv("AWS_PUBLIC_ENDPOINT_URL", "http://localhost:4566")

INPUT_BUCKET = os.getenv("INPUT_BUCKET", "serverless-csv-input")
RESULTS_BUCKET = os.getenv("RESULTS_BUCKET", "serverless-csv-results")
JOBS_TABLE = os.getenv("JOBS_TABLE", "serverless-csv-jobs")
PROCESSING_QUEUE_NAME = os.getenv("PROCESSING_QUEUE_NAME", "serverless-csv-processing")
LOCAL_API_NAME = "serverless-csv-api"
PROCESSING_LEASE_SECONDS = 120
