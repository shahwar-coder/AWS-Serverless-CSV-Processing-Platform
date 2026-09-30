import test from "node:test";
import assert from "node:assert/strict";
import { createJob, getJob, getResult, listJobs, uploadCsv } from "./api.js";

test("create job sends only metadata and upload uses signed PUT request", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push([url, options]);
    return url === "/api/jobs" ? new Response(JSON.stringify({ job_id: "id", upload: { url: "http://s3.example/input.csv?signature=secret", method: "PUT", headers: { "Content-Type": "text/csv" } } }), { status: 201 }) : new Response(null, { status: 200 });
  });
  const job = await createJob("sales.csv");
  const file = new Blob(["product,quantity,price\nMouse,2,5"]);
  await uploadCsv(job.upload, file);
  assert.deepEqual(JSON.parse(calls[0][1].body), { filename: "sales.csv", content_type: "text/csv" });
  assert.equal(calls[1][1].method, "PUT");
  assert.equal(calls[1][1].headers["Content-Type"], "text/csv");
  assert.equal(calls[1][1].body, file);
});

test("status and result use their job endpoints", async (t) => {
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url) => { urls.push(url); return new Response(JSON.stringify({ status: "COMPLETED" }), { status: 200 }); });
  await getJob("abc");
  await getResult("abc");
  assert.deepEqual(urls, ["/api/jobs/abc", "/api/jobs/abc/result"]);
});

test("API errors expose the safe backend message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ error: "Job not found." }), { status: 404 }));
  await assert.rejects(getJob("missing"), /Job not found/);
});

test("history uses the jobs collection endpoint", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.equal(url, "/api/jobs");
    return new Response(JSON.stringify({ jobs: [{ job_id: "one" }] }), { status: 200 });
  });
  assert.deepEqual((await listJobs()).jobs, [{ job_id: "one" }]);
});
