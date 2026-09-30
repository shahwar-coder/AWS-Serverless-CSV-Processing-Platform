import json
from unittest.mock import Mock

from botocore.exceptions import ClientError

from application.common.config import INPUT_BUCKET, PROCESSING_QUEUE_NAME
from application.scripts import create_local_resources as resources
from application.scripts import delete_local_resources as cleanup
from application.scripts import deploy_local_backend as deployment


def test_queue_setup_preserves_existing_policy(monkeypatch):
    sqs_client = Mock()
    sqs_client.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/queue"}
    sqs_client.get_queue_attributes.return_value = {
        "Attributes": {
            "QueueArn": "arn:aws:sqs:us-east-1:000000000000:serverless-csv-processing",
            "Policy": json.dumps(
                {"Version": "2012-10-17", "Statement": [{"Sid": "OtherRule"}]}
            ),
        }
    }
    monkeypatch.setattr(resources, "get_sqs_client", lambda: sqs_client)

    queue_arn = resources.ensure_processing_queue()

    assert queue_arn.endswith(PROCESSING_QUEUE_NAME)
    sqs_client.create_queue.assert_not_called()
    policy = json.loads(sqs_client.set_queue_attributes.call_args.kwargs["Attributes"]["Policy"])
    assert policy["Statement"][0] == {"Sid": "OtherRule"}
    assert policy["Statement"][1]["Principal"] == {"Service": "s3.amazonaws.com"}
    assert policy["Statement"][1]["Condition"] == {
        "ArnEquals": {"aws:SourceArn": f"arn:aws:s3:::{INPUT_BUCKET}"},
        "StringEquals": {"aws:SourceAccount": "000000000000"},
    }


def test_notification_setup_preserves_other_rules_and_is_idempotent(monkeypatch):
    queue_arn = "arn:aws:sqs:us-east-1:000000000000:serverless-csv-processing"
    other_rule = {"Id": "OtherRule", "QueueArn": "arn:aws:sqs:other", "Events": ["s3:ObjectRemoved:*"]}
    s3_client = Mock()
    s3_client.get_bucket_notification_configuration.return_value = {
        "QueueConfigurations": [other_rule],
        "EventBridgeConfiguration": {},
    }
    monkeypatch.setattr(resources, "get_s3_client", lambda: s3_client)

    resources.ensure_input_bucket_notification(queue_arn)

    configuration = s3_client.put_bucket_notification_configuration.call_args.kwargs[
        "NotificationConfiguration"
    ]
    assert configuration["QueueConfigurations"][0] == other_rule
    assert configuration["QueueConfigurations"][1] == {
        "Id": "CsvInputToProcessingQueue",
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
    assert configuration["EventBridgeConfiguration"] == {}

    s3_client.get_bucket_notification_configuration.return_value = configuration
    s3_client.put_bucket_notification_configuration.reset_mock()
    resources.ensure_input_bucket_notification(queue_arn)
    s3_client.put_bucket_notification_configuration.assert_not_called()


def test_queue_cleanup_ignores_missing_queue_and_deletes_existing_one(monkeypatch):
    sqs_client = Mock()
    sqs_client.get_queue_url.side_effect = ClientError(
        {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue"}},
        "GetQueueUrl",
    )
    monkeypatch.setattr(cleanup, "get_sqs_client", lambda: sqs_client)

    cleanup.delete_processing_queue_if_exists()
    sqs_client.delete_queue.assert_not_called()

    sqs_client.get_queue_url.side_effect = None
    sqs_client.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/queue"}
    cleanup.delete_processing_queue_if_exists()
    sqs_client.delete_queue.assert_called_once_with(QueueUrl="http://localhost:4566/queue")


def test_local_ui_cors_allows_both_vite_ports(monkeypatch):
    s3_client = Mock()
    s3_client.get_bucket_cors.side_effect = ClientError(
        {"Error": {"Code": "NoSuchCORSConfiguration"}}, "GetBucketCors"
    )
    monkeypatch.setattr(deployment, "create_aws_client", lambda service: s3_client)

    deployment._ensure_ui_s3_cors()

    rules = s3_client.put_bucket_cors.call_args.kwargs["CORSConfiguration"]["CORSRules"]
    assert rules[0]["AllowedOrigins"] == ["http://localhost:5173", "http://localhost:5174"]
    assert rules[0]["AllowedMethods"] == ["PUT"]
