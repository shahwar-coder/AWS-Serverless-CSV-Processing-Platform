"""Factory helpers for Boto3 clients configured for the local Floci endpoint."""

import boto3
from botocore.config import Config

from application.common.config import (
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_PUBLIC_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)


def create_aws_client(service_name: str, *, config: Config | None = None, endpoint_url: str | None = None):
    """
    Create a Boto3 client configured to communicate with Floci.
    """

    return boto3.client(
        service_name,
        endpoint_url=endpoint_url or AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=config,
    )


def get_s3_client():
    """Return an S3 client configured for the shared local AWS endpoint."""
    return create_aws_client(
        "s3",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_upload_s3_client():
    """Sign browser-facing S3 URLs without changing Lambda's internal AWS endpoint."""
    return create_aws_client(
        "s3",
        endpoint_url=AWS_PUBLIC_ENDPOINT_URL,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_dynamodb_client():
    """Return a DynamoDB client configured for the shared local AWS endpoint."""
    return create_aws_client("dynamodb")


def get_sqs_client():
    """Return an SQS client configured for the shared local AWS endpoint."""
    return create_aws_client("sqs")
