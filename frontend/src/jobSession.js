const ACTIVE_JOB_KEY = "csv-sales-analyzer.active-job-id";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function readActiveJobId() {
  try {
    const jobId = localStorage.getItem(ACTIVE_JOB_KEY);
    return jobId && UUID_PATTERN.test(jobId) ? jobId : null;
  } catch {
    return null;
  }
}

export function saveActiveJobId(jobId) {
  try { localStorage.setItem(ACTIVE_JOB_KEY, jobId); } catch { /* Storage is optional. */ }
}

export function clearActiveJobId() {
  try { localStorage.removeItem(ACTIVE_JOB_KEY); } catch { /* Storage is optional. */ }
}

export async function restoreActiveJob(jobId, signal) {
  const job = await getJob(jobId, signal);
  if (job.status === "COMPLETED") {
    return { job, report: await getResult(jobId, signal), phase: "completed", error: "", uploadFinished: true };
  }
  if (job.status === "FAILED") {
    return { job, report: null, phase: "failed", error: job.error || "CSV processing failed.", uploadFinished: Boolean(job.uploaded_at) };
  }
  return { job, report: null, phase: "processing", error: "", uploadFinished: Boolean(job.uploaded_at) };
}
import { getJob, getResult } from "./api.js";
