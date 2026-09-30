# Local Runbook

## 1. Start Floci

```powershell
docker compose up -d
```

Expected output:

```text
[+] up 1/1
 Container floci Started
```

Confirm Floci is running:

```powershell
docker compose ps
```

Expected: the `floci` service shows `Up` (healthy) and port `4566` is published.

Open `http://localhost:4566/_floci/ui` in your browser to start the Floci console. Once it starts, the AWS console is at `http://localhost:4500/console/aws`. The console may take a moment to become reachable on first launch. Port `4566` is the AWS service endpoint; port `4500` is the browser dashboard.

## 2. Create Local Resources

```powershell
python -m application.scripts.create_local_resources
```

Expected output:

```text
Bucket already exists: serverless-csv-input
Bucket already exists: serverless-csv-results
Table already exists: serverless-csv-jobs
Queue ready: serverless-csv-processing
Input bucket notification already configured
```

On the first notification setup, the last line says `Input bucket notification configured`.

## 3. Deploy Local Backend

Deploy or update the Lambda functions, API routes, SQS worker mapping, and UI CORS:

```powershell
python -m application.scripts.deploy_local_backend
```

The script prints the API URL and writes the frontend's ignored `.env.local` proxy configuration. Rerun it after backend code changes.

## 4. Run Tests

Run the focused tests without the Floci E2E check:

```powershell
python -m pytest
```

Run the HTTP Create Job through result flow against Floci and write Allure results:

```powershell
$env:RUN_FLOCI_E2E = "1"
python -m pytest tests/e2e/test_csv_job_flow.py --alluredir=allure-results --clean-alluredir
Remove-Item Env:RUN_FLOCI_E2E
```

To run the full suite with the E2E flow and Allure results, set `RUN_FLOCI_E2E=1` and use `python -m pytest --alluredir=allure-results --clean-alluredir`.

## 5. Run the Minimal UI

After deploying the backend, start the React dev server:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, select a CSV of at most 5 MiB containing `product`, `quantity`, and `price` headers in any order, and submit it. Extra columns are ignored; at most 1,000 distinct products are supported. Prices are treated as INR. If port 5173 is occupied, stop the other dev server or start with `npm run dev -- --port 5174`; both ports are allowed by local S3 CORS after redeploying the backend. Vite will no longer silently switch ports. The UI displays job progress and the completed summary. The local dev server proxies `/api` to Floci because this Floci path-style API endpoint does not return CORS headers for browser preflight; the signed upload still goes directly to S3. A production build requires an equivalent `/api` reverse proxy.

## 6. View Allure Results

Use a separate terminal at the project root while the UI is running.

The `allure-pytest` package writes result files. Viewing an HTML report requires the separate [Allure Report CLI](https://allurereport.org/docs/v3/install/) and Node.js. With Node.js installed, install the CLI and open the report:

```powershell
npm install -g allure
allure generate allure-results -o allure-report
allure open allure-report
```
