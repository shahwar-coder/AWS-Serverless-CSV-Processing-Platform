import test from "node:test";
import assert from "node:assert/strict";
import { clearActiveJobId, readActiveJobId, restoreActiveJob, saveActiveJobId } from "./jobSession.js";

const JOB_ID = "cac425e3-c710-49af-aecc-39a8bedb2dee";

test("only the active job ID is stored and reset clears it", (t) => {
  const values = new Map();
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  t.after(() => { delete globalThis.localStorage; });
  saveActiveJobId(JOB_ID);
  assert.equal(readActiveJobId(), JOB_ID);
  assert.deepEqual([...values.values()], [JOB_ID]);
  clearActiveJobId();
  assert.equal(readActiveJobId(), null);
});

test("completed job restores its report from the backend", async (t) => {
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    urls.push(url);
    return new Response(JSON.stringify(url.endsWith("/result") ? { row_count: 2 } : { job_id: JOB_ID, status: "COMPLETED", uploaded_at: "2026-10-01T00:00:00Z" }), { status: 200 });
  });
  const saved = await restoreActiveJob(JOB_ID);
  assert.equal(saved.phase, "completed");
  assert.equal(saved.report.row_count, 2);
  assert.deepEqual(urls, [`/api/jobs/${JOB_ID}`, `/api/jobs/${JOB_ID}/result`]);
});

test("failed job restores its safe error without requesting a result", async (t) => {
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    urls.push(url);
    return new Response(JSON.stringify({ job_id: JOB_ID, status: "FAILED", error: "Invalid CSV." }), { status: 200 });
  });
  const saved = await restoreActiveJob(JOB_ID);
  assert.equal(saved.phase, "failed");
  assert.equal(saved.error, "Invalid CSV.");
  assert.equal(saved.report, null);
  assert.deepEqual(urls, [`/api/jobs/${JOB_ID}`]);
});

test("pending job resumes polling without claiming its upload succeeded", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ job_id: JOB_ID, status: "UPLOAD_PENDING", uploaded_at: null }), { status: 200 }));
  const saved = await restoreActiveJob(JOB_ID);
  assert.equal(saved.phase, "processing");
  assert.equal(saved.uploadFinished, false);
  assert.equal(saved.report, null);
});
