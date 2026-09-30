"""Deploy the local Lambda/API/SQS processing path to Floci.

Run after create_local_resources: python -m application.scripts.deploy_local_backend
"""

import io
import os
import zipfile
from pathlib import Path

from botocore.exceptions import ClientError

from application.common.aws_clients import create_aws_client, get_sqs_client
from application.common.config import (
    AWS_PUBLIC_ENDPOINT_URL,
    INPUT_BUCKET,
    JOBS_TABLE,
    LOCAL_API_NAME,
    PROCESSING_QUEUE_NAME,
    RESULTS_BUCKET,
)


UI_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]
FUNCTIONS = {
    "serverless-csv-create-job": ("application.create_job.handler.handler", "POST /jobs"),
    "serverless-csv-get-job": ("application.get_job.handler.handler", "GET /jobs/{jobId}"),
    "serverless-csv-list-jobs": ("application.list_jobs.handler.handler", "GET /jobs"),
    "serverless-csv-process-csv": ("application.process_csv.handler.handler", None),
    "serverless-csv-get-result": ("application.get_result.handler.handler", "GET /jobs/{jobId}/result"),
}


def _package() -> bytes:
    root = Path(__file__).resolve().parents[2]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in (root / "application").rglob("*.py"):
            archive.write(path, path.relative_to(root).as_posix())
    return buffer.getvalue()


def _ensure_function(client, name: str, handler_name: str, payload: bytes) -> str:
    environment = {
        "AWS_ENDPOINT_URL": os.getenv("LAMBDA_AWS_ENDPOINT_URL", "http://floci:4566"),
        "AWS_PUBLIC_ENDPOINT_URL": AWS_PUBLIC_ENDPOINT_URL,
        "INPUT_BUCKET": INPUT_BUCKET,
        "RESULTS_BUCKET": RESULTS_BUCKET,
        "JOBS_TABLE": JOBS_TABLE,
        "PROCESSING_QUEUE_NAME": PROCESSING_QUEUE_NAME,
    }
    try:
        current = client.get_function(FunctionName=name)
    except client.exceptions.ResourceNotFoundException:
        result = client.create_function(
            FunctionName=name,
            Runtime="python3.11",
            Role="arn:aws:iam::000000000000:role/serverless-csv-local",
            Handler=handler_name,
            Code={"ZipFile": payload},
            Timeout=30,
            Environment={"Variables": environment},
        )
        print(f"Lambda created: {name}")
        return result["FunctionArn"]
    client.update_function_code(FunctionName=name, ZipFile=payload)
    client.update_function_configuration(
        FunctionName=name,
        Handler=handler_name,
        Timeout=30,
        Environment={"Variables": environment},
    )
    print(f"Lambda updated: {name}")
    return current["Configuration"]["FunctionArn"]


def _ensure_api(api, lambdas, arns: dict[str, str]) -> str:
    existing = next((item for item in api.get_apis()["Items"] if item["Name"] == LOCAL_API_NAME), None)
    if existing:
        api_id = existing["ApiId"]
    else:
        api_id = api.create_api(Name=LOCAL_API_NAME, ProtocolType="HTTP")["ApiId"]
    api.update_api(
        ApiId=api_id,
        CorsConfiguration={
            "AllowOrigins": UI_ORIGINS,
            "AllowMethods": ["GET", "POST", "OPTIONS"],
            "AllowHeaders": ["content-type"],
        },
    )
    integrations = api.get_integrations(ApiId=api_id)["Items"]
    routes = {item["RouteKey"]: item for item in api.get_routes(ApiId=api_id)["Items"]}
    for obsolete in ("GET /jobs/{job_id}", "GET /jobs/{job_id}/result"):
        if obsolete in routes:
            api.delete_route(ApiId=api_id, RouteId=routes.pop(obsolete)["RouteId"])
    for name, (_, route_key) in FUNCTIONS.items():
        if route_key is None:
            continue
        integration = next((item for item in integrations if item.get("IntegrationUri") == arns[name]), None)
        if integration is None:
            integration = api.create_integration(
                ApiId=api_id,
                IntegrationType="AWS_PROXY",
                IntegrationUri=arns[name],
                PayloadFormatVersion="2.0",
            )
        target = f"integrations/{integration['IntegrationId']}"
        if route_key in routes:
            if routes[route_key].get("Target") != target:
                api.update_route(ApiId=api_id, RouteId=routes[route_key]["RouteId"], Target=target)
        else:
            api.create_route(ApiId=api_id, RouteKey=route_key, Target=target)
        try:
            lambdas.add_permission(
                FunctionName=name,
                StatementId="AllowLocalApiGateway",
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:us-east-1:000000000000:{api_id}/*",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                raise
    if not any(stage["StageName"] == "$default" for stage in api.get_stages(ApiId=api_id)["Items"]):
        api.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    url = f"http://localhost:4566/execute-api/{api_id}/%24default"
    print(f"API ready: {url}")
    return url


def get_local_api_url() -> str:
    api = create_aws_client("apigatewayv2")
    match = next((item for item in api.get_apis()["Items"] if item["Name"] == LOCAL_API_NAME), None)
    if not match:
        raise RuntimeError("Local API is missing; run deploy_local_backend first")
    return f"http://localhost:4566/execute-api/{match['ApiId']}/%24default"


def _ensure_worker_mapping(lambdas, worker_arn: str) -> None:
    sqs = get_sqs_client()
    queue_url = sqs.get_queue_url(QueueName=PROCESSING_QUEUE_NAME)["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    mappings = lambdas.list_event_source_mappings(
        FunctionName=worker_arn, EventSourceArn=queue_arn
    )["EventSourceMappings"]
    if not mappings:
        lambdas.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName=worker_arn,
            BatchSize=1,
        )
    print("SQS-to-Lambda mapping ready")


def _ensure_ui_s3_cors() -> None:
    s3 = create_aws_client("s3")
    try:
        existing = s3.get_bucket_cors(Bucket=INPUT_BUCKET)["CORSRules"]
    except ClientError as error:
        if error.response["Error"]["Code"] not in ("NoSuchCORSConfiguration", "NoSuchCORSRule"):
            raise
        existing = []
    rule = {
        "ID": "CsvLocalUiUpload",
        "AllowedOrigins": UI_ORIGINS,
        "AllowedMethods": ["PUT"],
        "AllowedHeaders": ["content-type"],
        "MaxAgeSeconds": 300,
    }
    rules = [item for item in existing if item.get("ID") != rule["ID"]]
    if rules + [rule] != existing:
        s3.put_bucket_cors(Bucket=INPUT_BUCKET, CORSConfiguration={"CORSRules": rules + [rule]})
    print("UI upload CORS ready")


def main() -> None:
    payload = _package()
    lambdas = create_aws_client("lambda")
    api = create_aws_client("apigatewayv2")
    arns = {
        name: _ensure_function(lambdas, name, handler_name, payload)
        for name, (handler_name, _) in FUNCTIONS.items()
    }
    url = _ensure_api(api, lambdas, arns)
    _ensure_worker_mapping(lambdas, arns["serverless-csv-process-csv"])
    _ensure_ui_s3_cors()
    (Path(__file__).resolve().parents[2] / "frontend" / ".env.local").write_text(
        f"VITE_API_BASE_URL={url}\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
