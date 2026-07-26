# Context Management

1. **`AWS client config defaults`** : Added `application/common/config.py` to centralize LocalStack/AWS environment values for endpoint, region, and credentials so client code can stay environment-aware and avoid hardcoding.
2. **`AWS client setup`** : Prepared `application/common/aws_clients.py` as the place to build AWS service clients using the shared config so client creation stays consistent across the project.
3. **`Local resource creation script`** : Added `application/scripts/create_local_resources.py` to create the input and results S3 buckets only when absent, making repeated local setup runs idempotent.
4. **`Local resource deletion script`** : Added `application/scripts/delete_local_resources.py` to empty and delete the local S3 buckets only when present, making repeated cleanup runs safe and idempotent.
5. **`DynamoDB jobs table lifecycle`** : Added idempotent jobs-table creation and deletion to the local resource scripts so the DynamoDB environment can be safely provisioned and cleaned up across repeated development runs.
