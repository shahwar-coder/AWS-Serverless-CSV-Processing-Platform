const API_BASE = "/api";

async function readJson(response) {
  let body;
  try { body = await response.json(); } catch { throw new Error(`Invalid server response (${response.status}).`); }
  if (!response.ok) {
    const error = new Error(body.error || `Request failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return body;
}

export async function createJob(filename, signal) {
  return readJson(await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, content_type: "text/csv" }),
    signal,
  }));
}

export async function uploadCsv(upload, file, signal) {
  const response = await fetch(upload.url, { method: upload.method, headers: upload.headers, body: file, signal });
  if (!response.ok) throw new Error(`S3 upload failed (${response.status}).`);
}

export async function getJob(jobId, signal) {
  return readJson(await fetch(`${API_BASE}/jobs/${jobId}`, { signal }));
}

export async function listJobs(signal) {
  return readJson(await fetch(`${API_BASE}/jobs`, { signal }));
}

export async function getResult(jobId, signal) {
  return readJson(await fetch(`${API_BASE}/jobs/${jobId}/result`, { signal }));
}
