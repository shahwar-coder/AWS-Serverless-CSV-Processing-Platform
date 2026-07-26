"""Factory helpers for Boto3 clients configured for the local Floci endpoint."""

import boto3

from application.common.config import (
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)


def create_aws_client(service_name: str):
    """
    Create a Boto3 client configured to communicate with Floci.
    """

    return boto3.client(
        service_name,
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def get_s3_client():
    """Return an S3 client configured for the shared local AWS endpoint."""
    return create_aws_client("s3")


def get_dynamodb_client():
    """Return a DynamoDB client configured for the shared local AWS endpoint."""
    return create_aws_client("dynamodb")
