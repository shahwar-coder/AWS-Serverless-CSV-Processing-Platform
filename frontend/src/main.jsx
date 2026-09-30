import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { createJob, getJob, getResult, listJobs, uploadCsv } from "./api";
import { Dashboard } from "./Dashboard";
import { clearActiveJobId, readActiveJobId, restoreActiveJob, saveActiveJobId } from "./jobSession";
import { readTheme, saveTheme } from "./theme";
import "./style.css";

const MAX_CSV_BYTES = 5 * 1024 * 1024;

function App() {
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(null);
  const [phase, setPhase] = useState(() => readActiveJobId() ? "restoring" : "idle");
  const [error, setError] = useState("");
  const [uploadFinished, setUploadFinished] = useState(false);
  const [view, setView] = useState("dashboard");
  const [theme, setTheme] = useState(readTheme);
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyOpeningId, setHistoryOpeningId] = useState("");
  const [historyVersion, setHistoryVersion] = useState(0);
  const requestRef = useRef(null);

  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (view !== "history") return;
    const controller = new AbortController();
    setHistoryLoading(true);
    setHistoryError("");
    listJobs(controller.signal).then(({ jobs }) => {
      if (!controller.signal.aborted) setHistory(jobs);
    }).catch((cause) => {
      if (!controller.signal.aborted) setHistoryError(cause.message);
    }).finally(() => {
      if (!controller.signal.aborted) setHistoryLoading(false);
    });
    return () => controller.abort();
  }, [view, historyVersion]);

  useEffect(() => {
    const jobId = readActiveJobId();
    if (!jobId) return;
    const controller = new AbortController();
    requestRef.current = controller;
    async function restore() {
      try {
        const saved = await restoreActiveJob(jobId, controller.signal);
        if (controller.signal.aborted) return;
        setJob(saved.job);
        setReport(saved.report);
        setUploadFinished(saved.uploadFinished);
        setError(saved.error);
        setPhase(saved.phase);
      } catch (cause) {
        if (controller.signal.aborted) return;
        if (cause.status === 404) {
          clearActiveJobId();
          setError("Previous job is no longer available. Upload a new CSV.");
          setPhase("idle");
        } else {
          setError(`Could not restore the previous job: ${cause.message}`);
          setPhase("error");
        }
      }
    }
    restore();
    return () => controller.abort();
  }, []);

  function reset() {
    requestRef.current?.abort();
    requestRef.current = null;
    clearActiveJobId();
    setFile(null);
    setJob(null);
    setReport(null);
    setUploadFinished(false);
    setPhase("idle");
    setError("");
    setView("dashboard");
  }

  async function openHistoryJob(jobId) {
    const controller = new AbortController();
    setHistoryOpeningId(jobId);
    setHistoryError("");
    try {
      const saved = await restoreActiveJob(jobId, controller.signal);
      setFile(null);
      setJob(saved.job);
      setReport(saved.report);
      setUploadFinished(saved.uploadFinished);
      setError(saved.error);
      setPhase(saved.phase);
      saveActiveJobId(jobId);
      setView("dashboard");
    } catch (cause) {
      setHistoryError(cause.message);
    } finally {
      setHistoryOpeningId("");
    }
  }

  function selectFile(nextFile) {
    if (job) {
      requestRef.current?.abort();
      clearActiveJobId();
      setJob(null);
      setReport(null);
      setUploadFinished(false);
      setPhase("idle");
    }
    setFile(nextFile);
    setError("");
  }

  async function start(event) {
    event.preventDefault();
    if (!file || !file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file to continue.");
      return;
    }
    if (file.size > MAX_CSV_BYTES) {
      setError("CSV must be 5 MiB or smaller.");
      return;
    }
    const controller = new AbortController();
    requestRef.current = controller;
    clearActiveJobId();
    setError("");
    setReport(null);
    setJob(null);
    setUploadFinished(false);
    try {
      setPhase("creating");
      const created = await createJob(file.name, controller.signal);
      saveActiveJobId(created.job_id);
      setJob({ job_id: created.job_id, filename: file.name, status: created.status, created_at: created.created_at, updated_at: created.created_at });
      setPhase("uploading");
      await uploadCsv(created.upload, file, controller.signal);
      setUploadFinished(true);
      setPhase("processing");
    } catch (cause) {
      if (cause.name !== "AbortError") {
        setError(cause.message);
        setPhase("error");
      }
    }
  }

  useEffect(() => {
    if (!job?.job_id || phase !== "processing") return;
    const controller = new AbortController();
    let timer;
    let attempts = 0;
    async function poll() {
      try {
        const latest = await getJob(job.job_id, controller.signal);
        if (controller.signal.aborted) return;
        setJob(latest);
        if (latest.uploaded_at) setUploadFinished(true);
        if (latest.status === "FAILED") {
          setError(latest.error || "CSV processing failed.");
          setPhase("failed");
          return;
        }
        if (latest.status === "COMPLETED") {
          const result = await getResult(job.job_id, controller.signal);
          if (controller.signal.aborted) return;
          setReport(result);
          setPhase("completed");
          return;
        }
        attempts += 1;
        if (attempts >= 90) throw new Error(latest.status === "UPLOAD_PENDING" && !latest.uploaded_at
          ? "Upload was not confirmed. If it was interrupted, upload the CSV again as a new job."
          : "Processing is taking longer than expected. Keep the job ID and check again later.");
        timer = setTimeout(poll, 1500);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause.message);
          setPhase("error");
        }
      }
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [job?.job_id, uploadFinished, phase]);

  return <Dashboard file={file} onFileChange={selectFile} onSubmit={start} onReset={reset} job={job} report={report} phase={phase} error={error} uploadFinished={uploadFinished} view={view} onViewChange={setView} theme={theme} onThemeChange={() => setTheme(theme === "light" ? "dark" : "light")} history={history} historyLoading={historyLoading} historyError={historyError} historyOpeningId={historyOpeningId} onHistoryRefresh={() => setHistoryVersion((value) => value + 1)} onHistoryOpen={openHistoryJob} />;
}

createRoot(document.getElementById("root")).render(<App />);
