# AGENTS.md

## Project

Build an event-driven CSV processing platform using Floci, Boto3, and core AWS serverless services.

Flow:

```text
API Gateway → Lambda → S3 → SQS → Lambda → DynamoDB / S3 → EventBridge / SNS
```

The project should teach practical AWS usage, clean backend design, asynchronous processing, retries, idempotency, and failure handling.

## Initial Structure

```text
application/
├── common/
│   ├── aws_clients.py
│   ├── config.py
│   └── exceptions.py
├── create_job/
│   └── handler.py
├── get_job/
│   └── handler.py
├── get_result/
│   └── handler.py
├── process_csv/
│   ├── handler.py
│   ├── parser.py
│   └── report.py
└── retry_job/
    └── handler.py
scripts/
tests/
docs/
docker-compose.yml
requirements.txt
README.md
```

Create folders only when required. Avoid premature complexity.

## Coding Rules

- Prefer small, clear, behavior-focused changes.
- Keep functions short, reusable, and easy to understand.
- Separate AWS access, business logic, validation, and handlers.
- Use helpers only when they remove real duplication.
- Use descriptive names and type hints.
- Add short docstrings only where intent is not obvious.
- Handle expected failures explicitly.
- Keep configuration in `config.py`; do not hard-code secrets.
- Make setup scripts safe to run repeatedly.
- Preserve idempotency for event-driven processing.
- Do not add abstractions, libraries, or files without a current need.
- Add or update tests for meaningful behavior changes.

## Before Editing

1. Inspect the relevant files.
2. Identify the smallest safe change.
3. Reuse existing patterns.
4. Implement only the requested scope.
5. Run the most relevant checks.

## Response Format

```text
Implemented: <short summary>

Changed:
- path/to/file.py

Verified:
- command or test

Result:
- passed / remaining issue

Notes:
- important risk or next step, only when needed
```

Keep reports concise and do not claim tests were run when they were not.
