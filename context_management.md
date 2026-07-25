# Context Management

1. **`AWS client config defaults`** : Added `application/clients/config.py` to centralize LocalStack/AWS environment values for endpoint, region, and credentials so client code can stay environment-aware and avoid hardcoding.
2. **`AWS client setup`** : Prepared `application/clients/aws_clients.py` as the place to build AWS service clients using the shared config so client creation stays consistent across the project.
