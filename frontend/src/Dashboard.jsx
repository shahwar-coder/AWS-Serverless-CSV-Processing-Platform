import React, { useState } from "react";
import { ArrowRight, BarChart3, Box, Check, Clipboard, CloudUpload, Code2, Download, FileText, Moon, Package, RefreshCw, Search, ShoppingBasket, Sun, Trophy, Upload, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dateTime, duration, fileSize, filterProducts, integer, rupees, timeOnly, topProducts } from "./format";

function Card({ children, className = "" }) {
  return <section className={`card min-w-0 ${className}`}>{children}</section>;
}

function Badge({ status }) {
  return <span className={`badge badge-${(status || "idle").toLowerCase().replaceAll("_", "-")}`}>{status ? status.replaceAll("_", " ") : "NO JOB"}</span>;
}

function Header({ view, onViewChange, theme, onThemeChange, busy }) {
  return <header className="header">
    <a className="brand" href="#dashboard" aria-label="CSV Sales Analyzer home"><BarChart3 size={23} strokeWidth={2.6} /><strong>CSV Sales Analyzer</strong></a>
    <nav aria-label="Main navigation"><button type="button" className={view === "dashboard" ? "active" : ""} onClick={() => onViewChange("dashboard")}>Dashboard</button><button type="button" onClick={() => onViewChange("dashboard")}>Upload</button><button type="button" className={view === "history" ? "active" : ""} onClick={() => onViewChange("history")} disabled={busy}>History</button><button type="button" className="theme-toggle" onClick={onThemeChange} aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"} title={theme === "light" ? "Dark mode" : "Light mode"}>{theme === "light" ? <Moon size={18} /> : <Sun size={18} />}</button></nav>
  </header>;
}

function HistoryPage({ jobs, loading, error, openingId, onRefresh, onOpen }) {
  return <main className="history-page"><div className="history-heading"><div><span className="history-eyebrow">YOUR PIPELINE</span><h1>Job History</h1><p>Review the 50 most recent jobs stored in Floci. Select one to inspect its status or report.</p></div><button className="secondary history-refresh" onClick={onRefresh} disabled={loading}><RefreshCw size={16} />Refresh</button></div>
    <Card className="history-card">{error && <div className="error-banner" role="alert">{error}</div>}{loading ? <p className="history-empty">Loading jobs...</p> : jobs.length ? <div className="history-list">{jobs.map((item) => <button type="button" className="history-row" key={item.job_id} onClick={() => onOpen(item.job_id)} disabled={Boolean(openingId)}><span className="history-file"><span className="history-file-icon"><FileText size={21} /></span><span><strong>{item.filename}</strong><small>{item.job_id}</small></span></span><span className="history-date">{dateTime(item.created_at)}<small>{fileSize(item.file_size_bytes)}</small></span><Badge status={item.status} /><span className="history-open">{openingId === item.job_id ? "Opening..." : "View job"}<ArrowRight size={16} /></span></button>)}</div> : <p className="history-empty">No jobs yet. Upload a CSV to start your history.</p>}</Card>
  </main>;
}

function CsvUploadPanel({ file, onFileChange, onSubmit, phase, error, job }) {
  const working = ["restoring", "creating", "uploading", "processing"].includes(phase);
  return <Card className="upload-card" >
    <form id="upload" onSubmit={onSubmit} className="upload-form">
      <div className="upload-symbol"><CloudUpload size={32} /></div>
      <div className="upload-copy"><h2>Upload a CSV file</h2><p>CSV must contain: product, quantity, price (extra columns are allowed)</p>
        <label className="file-choice"><Upload size={15} /><span>Choose File</span><input type="file" accept=".csv,text/csv" onChange={(event) => onFileChange(event.target.files?.[0] || null)} disabled={working} /></label>
        <span className="chosen-file">{file?.name || "No file chosen"}</span>
      </div>
      <button className="primary upload-button" type="submit" disabled={!file || working}><Upload size={17} />{phase === "creating" ? "Creating job..." : phase === "uploading" ? "Uploading..." : "Upload CSV"}</button>
    </form>
    {error && !job && <p className="form-error" role="alert">{error}</p>}
  </Card>;
}

const timeline = [
  ["Job Created", "created_at"],
  ["CSV Uploaded", "uploaded_at"],
  ["Processing", "processing_started_at"],
  ["Completed", "completed_at"],
];

function ProcessingTimeline({ job, phase, uploadFinished }) {
  return <div className="timeline" aria-label="Processing timeline">{timeline.map(([label, field], index) => {
    const happened = Boolean(job?.[field]);
    const pendingUpload = index === 1 && uploadFinished && !job?.uploaded_at;
    const failed = index === 3 && job?.status === "FAILED";
    return <div className={`timeline-step ${happened ? "done" : failed ? "failed" : pendingUpload || (index === 2 && job?.status === "PROCESSING") ? "current" : ""}`} key={field}>
      <div className="timeline-node">{happened ? <Check size={13} /> : failed ? <X size={13} /> : index + 1}</div>
      <strong>{failed ? "Failed" : label}</strong><small>{failed ? timeOnly(job?.failed_at) : timeOnly(job?.[field])}</small>
    </div>;
  })}</div>;
}

function JobStatusCard({ job, phase, error, uploadFinished }) {
  if (!job) return <Card className="status-card empty-status"><div className="status-icon neutral"><FileText size={28} /></div><div><h2>{phase === "restoring" ? "Restoring your last job..." : "No job yet"}</h2><p>{phase === "restoring" ? "Fetching the latest status from the backend." : "Select a CSV above to create a job and view its processing timeline."}</p></div></Card>;
  const status = job.status;
  const ended = job.completed_at || job.failed_at;
  return <Card className="status-card">
    <div className="status-top"><div className={`status-icon ${status === "COMPLETED" ? "success" : status === "FAILED" || phase === "error" ? "danger" : "waiting"}`}>{status === "COMPLETED" ? <Check size={33} /> : status === "FAILED" || phase === "error" ? <X size={30} /> : <FileText size={29} />}</div>
      <div className="status-copy"><div className="status-title"><h2>{job.filename}</h2><Badge status={status} /></div><p className="id-line">Job ID: <span title={job.job_id}>{job.job_id}</span><button className="icon-button" type="button" onClick={() => navigator.clipboard.writeText(job.job_id)} aria-label="Copy job ID"><Clipboard size={15} /></button></p>
        <p>{ended ? `${status === "FAILED" ? "Failed" : "Processed"} on ${dateTime(ended)}` : phase === "uploading" ? "Uploading CSV to S3..." : status === "UPLOAD_PENDING" && !uploadFinished ? "Upload not yet confirmed. If interrupted, upload another CSV." : "Waiting for processing..."}{ended && <> <span className="dot-separator">•</span> Processing time: {duration(job.created_at, ended)}</>}</p></div></div>
    <ProcessingTimeline job={job} phase={phase} uploadFinished={uploadFinished} />
    {error && <div className="error-banner" role="alert">{error}</div>}
  </Card>;
}

const statConfig = [
  ["Total Rows", "row_count", FileText, "blue", integer, "Valid product rows"],
  ["Total Quantity", "total_quantity", ShoppingBasket, "green", integer, "Units sold"],
  ["Total Revenue", "total_revenue", BarChart3, "purple", rupees, "Sum of quantity × price"],
  ["Unique Products", "unique_products", Box, "orange", integer, "Different products"],
];

function StatsGrid({ report }) {
  return <div className="stats-grid">{statConfig.map(([label, field, Icon, color, formatter, caption]) => <Card className="stat-card" key={field}><div className={`stat-icon ${color}`}><Icon size={26} /></div><div><h3>{label}</h3><strong>{report ? formatter(report[field]) : "—"}</strong><p>{caption}</p></div></Card>)}</div>;
}

function ProductChart({ title, metric, products, color, theme }) {
  const data = products ? topProducts(products, metric) : [];
  const format = metric === "revenue" ? rupees : integer;
  const dark = theme === "dark";
  const labelColor = dark ? "#d9e4f8" : "#34415b";
  return <Card className="chart-card"><h2>{title}</h2><p>Top 10 products by total {metric}</p>{data.length ? <div className="chart-canvas"><ResponsiveContainer width="100%" height={220}><BarChart data={data} layout="vertical" margin={{ top: 4, right: 58, left: 6, bottom: 0 }} barCategoryGap="18%"><CartesianGrid horizontal={false} stroke={dark ? "#34435d" : "#e9edf5"} /><XAxis type="number" tickFormatter={(value) => value >= 1000 ? `${Math.round(value / 1000)}K` : value} tick={{ fill: dark ? "#aab8d2" : "#64708a", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="product" width={85} tick={{ fill: labelColor, fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => format(value)} cursor={{ fill: dark ? "#263750" : "#f5f7fb" }} contentStyle={dark ? { background: "#202e45", borderColor: "#465776", color: "#edf3ff" } : undefined} /><Bar dataKey="value" fill={color} radius={[0, 2, 2, 0]} maxBarSize={18} label={{ position: "right", formatter: format, fill: labelColor, fontSize: 11 }} /></BarChart></ResponsiveContainer></div> : <div className="chart-empty">Chart appears when a report is ready.</div>}</Card>;
}

function ProductBreakdownTable({ report }) {
  const [search, setSearch] = useState("");
  const products = [...(report?.products || [])].sort((a, b) => Number(b.revenue) - Number(a.revenue) || a.product.localeCompare(b.product));
  const filtered = filterProducts(products, search);
  const total = Number(report?.total_revenue || 0);
  return <Card className="table-card"><div className="table-heading"><h2>Product Breakdown</h2><label className="search"><Search size={16} /><input aria-label="Search products" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search products..." disabled={!report} /></label></div>
    {report ? <div className="table-scroll"><table><thead><tr><th>#</th><th>Product</th><th>Quantity</th><th>Revenue</th><th>% of Revenue</th></tr></thead><tbody>{filtered.map((item, index) => { const percent = total > 0 ? Number(item.revenue) / total * 100 : 0; return <tr key={item.product}><td>{index + 1}</td><td>{item.product}</td><td>{integer(item.quantity)}</td><td>{rupees(item.revenue)}</td><td><div className="share"><span>{percent.toFixed(1)}%</span><span className="share-track"><span style={{ width: `${Math.min(100, percent)}%` }} /></span></div></td></tr>; })}</tbody></table>{!filtered.length && <p className="table-empty">No matching products.</p>}</div> : <div className="table-empty">Your product breakdown will appear after processing.</div>}
  </Card>;
}

function JobDetailsCard({ job }) {
  const rows = [["Job ID", job?.job_id], ["File name", job?.filename], ["File size", fileSize(job?.file_size_bytes)], ["Created at", dateTime(job?.created_at)], ["Updated at", dateTime(job?.updated_at)], ["Status", job?.status], ["Processing time", duration(job?.created_at, job?.completed_at || job?.failed_at)]];
  return <Card className="side-card"><div className="side-title"><h2>Job Details</h2>{job && <Badge status={job.status} />}</div><dl className="details">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={value || "Not yet"}>{label === "Status" && job ? <Badge status={value} /> : value || "Not yet"}</dd></div>)}</dl></Card>;
}

function TopProductsCard({ report }) {
  const revenue = report?.products?.length ? topProducts(report.products, "revenue")[0] : null;
  const quantity = report?.products?.length ? topProducts(report.products, "quantity")[0] : null;
  return <Card className="side-card"><h2 className="with-icon"><Trophy size={20} color="#f29911" /> Top Products</h2><div className="top-product orange-tint"><Trophy size={22} /><div><span>Highest Revenue</span><strong>{revenue?.product || "Awaiting report"}</strong></div><b>{revenue ? rupees(revenue.revenue) : "—"}</b></div><div className="top-product purple-tint"><Package size={22} /><div><span>Highest Quantity</span><strong>{quantity?.product || "Awaiting report"}</strong></div><b>{quantity ? `${integer(quantity.quantity)} units` : "—"}</b></div></Card>;
}

function ReportActionsCard({ report, job, onReset }) {
  const [open, setOpen] = useState(false);
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `report-${job.job_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <Card className="side-card"><h2>Actions</h2><div className="action-list"><button className="primary" disabled={!report} onClick={download}><Download size={17} />Download Report (JSON)</button><button className="secondary" disabled={!report} onClick={() => setOpen(true)}><Code2 size={17} />View Raw JSON</button><button className="secondary" onClick={onReset}><Upload size={17} />Upload Another CSV</button></div>
    {open && <div className="modal-backdrop" onClick={() => setOpen(false)}><div className="json-modal" role="dialog" aria-modal="true" aria-label="Raw report JSON" onClick={(event) => event.stopPropagation()}><div className="modal-head"><h2>Raw report JSON</h2><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close raw JSON"><X size={20} /></button></div><pre>{JSON.stringify(report, null, 2)}</pre></div></div>}
  </Card>;
}

function ExpectedCsvFormatCard() {
  return <Card className="format-card"><FileText size={26} /><div><h3>Expected CSV Format</h3><p>Your CSV must contain these columns:</p><code>product, quantity, price</code><small>Extra columns are allowed and will be ignored.</small></div></Card>;
}

export function Dashboard(props) {
  const { file, onFileChange, onSubmit, onReset, job, report, phase, error, uploadFinished, view, onViewChange, theme, onThemeChange, history, historyLoading, historyError, historyOpeningId, onHistoryRefresh, onHistoryOpen } = props;
  return <div id="dashboard" className="app-shell"><Header view={view} onViewChange={onViewChange} theme={theme} onThemeChange={onThemeChange} busy={["restoring", "creating", "uploading"].includes(phase)} />{view === "history" ? <HistoryPage jobs={history} loading={historyLoading} error={historyError} openingId={historyOpeningId} onRefresh={onHistoryRefresh} onOpen={onHistoryOpen} /> : <main className="dashboard-grid"><div className="main-column"><CsvUploadPanel file={file} onFileChange={onFileChange} onSubmit={onSubmit} phase={phase} error={error} job={job} /><JobStatusCard job={job} phase={phase} error={error} uploadFinished={uploadFinished} /><StatsGrid report={report} /><div className="charts-grid"><ProductChart title="Revenue by Product" metric="revenue" products={report?.products} color="#4d88f7" theme={theme} /><ProductChart title="Quantity by Product" metric="quantity" products={report?.products} color="#9975e8" theme={theme} /></div><ProductBreakdownTable report={report} /></div><aside className="sidebar"><JobDetailsCard job={job} /><TopProductsCard report={report} /><ReportActionsCard report={report} job={job} onReset={onReset} /><ExpectedCsvFormatCard /></aside></main>}</div>;
}
