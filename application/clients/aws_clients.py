import boto3

from application.clients.config import (
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
    return create_aws_client("s3")