import { useState, useCallback, useEffect, useRef } from 'react';
import {
  createJob,
  getJobStatus,
  uploadDocumentsBulk,
  getLeads,
  getExportUrl,
} from './api';
import type {
  JobStatusResponse,
  BulkUploadResponse,
  LeadResponse,
} from './types';
import './index.css';

/* ─── Step type ─── */
type Step = 'setup' | 'upload' | 'dashboard';

/* ─── Setup Screen ─── */
function SetupScreen({ onJobCreated }: { onJobCreated: (jobId: string, total: number) => void }) {
  const [count, setCount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    const n = parseInt(count, 10);
    if (!n || n <= 0 || n > 50) {
      setError('Enter a number between 1 and 50');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const job = await createJob(n);
      onJobCreated(job.job_id, n);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create job');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="setup-section fade-in">
      <div className="card setup-card">
        <div className="card-header">
          <span className="card-icon">🚀</span>
          <span className="card-title">New Extraction Job</span>
        </div>
        <p className="setup-description">
          Upload business card images and our AI will extract structured contact 
          information including name, title, company, location, phone, and email.
        </p>
        {error && <div className="alert-error">⚠️ {error}</div>}
        <div className="form-group">
          <label className="form-label">Number of Business Cards</label>
          <input
            type="number"
            className="form-input"
            placeholder="e.g. 10"
            min={1}
            max={50}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        <button
          className="btn btn-primary btn-full"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? <><span className="spinner" /> Creating...</> : '✨ Create Job'}
        </button>
      </div>
    </div>
  );
}

/* ─── Upload Screen ─── */
function UploadScreen({
  jobId,
  expectedCount,
  onUploadComplete,
}: {
  jobId: string;
  expectedCount: number;
  onUploadComplete: () => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkUploadResponse | null>(null);
  const [error, setError] = useState('');

  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    setSelectedFiles(Array.from(files));
    setResult(null);
    setError('');
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setError('');
    try {
      const res = await uploadDocumentsBulk(jobId, selectedFiles);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="setup-section fade-in">
      <div className="card setup-card" style={{ maxWidth: 560 }}>
        <div className="card-header">
          <span className="card-icon">📤</span>
          <span className="card-title">Upload Business Cards</span>
        </div>
        <p className="setup-description">
          Select up to {expectedCount} business card images (JPEG, PNG, WebP).
          Each image will be processed by our Qwen Vision-Language Model.
        </p>

        {error && <div className="alert-error">⚠️ {error}</div>}

        <div
          className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        >
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <div className="upload-icon">📷</div>
          <div className="upload-title">
            {dragOver ? 'Drop files here' : 'Drag & drop or click to browse'}
          </div>
          <div className="upload-hint">Supports JPEG, PNG, WebP</div>
        </div>

        {selectedFiles.length > 0 && !result && (
          <div className="file-count-badge">
            📎 {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected
          </div>
        )}

        {result && (
          <div className="upload-results fade-in">
            {result.results.map((r, i) => (
              <div key={i} className={`upload-result-item ${r.success ? 'success' : 'error'}`}>
                <span>{r.success ? '✅' : '❌'}</span>
                <span style={{ flex: 1 }}>{r.filename}</span>
                {r.error && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{r.error}</span>}
              </div>
            ))}
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-secondary)' }}>
              {result.accepted} accepted · {result.rejected} rejected
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
          {!result ? (
            <button
              className="btn btn-primary btn-full"
              onClick={handleUpload}
              disabled={uploading || selectedFiles.length === 0}
            >
              {uploading ? <><span className="spinner" /> Uploading...</> : `⬆️ Upload ${selectedFiles.length} File${selectedFiles.length !== 1 ? 's' : ''}`}
            </button>
          ) : (
            <button className="btn btn-success btn-full" onClick={onUploadComplete}>
              📊 View Processing Dashboard →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Dashboard ─── */
function Dashboard({ jobId, onNewJob }: { jobId: string; onNewJob: () => void }) {
  const [status, setStatus] = useState<JobStatusResponse | null>(null);
  const [leads, setLeads] = useState<LeadResponse[]>([]);
  const [error, setError] = useState('');
  const intervalRef = useRef<number | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getJobStatus(jobId);
      setStatus(s);

      // Fetch leads whenever at least one document has succeeded,
      // so extracted contacts appear dynamically in real time
      if (s.successful_documents > 0) {
        const l = await getLeads(jobId);
        setLeads(l.items);
      }

      if (['completed', 'completed_with_errors', 'failed'].includes(s.status)) {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status');
    }
  }, [jobId]);

  useEffect(() => {
    fetchStatus();
    intervalRef.current = window.setInterval(fetchStatus, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchStatus]);

  const isComplete = status && ['completed', 'completed_with_errors', 'failed'].includes(status.status);

  const badgeClass = status ? `badge badge-${status.status}` : 'badge';
  const statusLabel = status?.status?.replace(/_/g, ' ') || '';

  return (
    <div className="dashboard fade-in">
      {error && <div className="alert-error">⚠️ {error}</div>}

      {/* Status Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-icon">📋</span>
          <span className="card-title">Job Status</span>
          {status && (
            <span className={badgeClass} style={{ marginLeft: 'auto' }}>
              {!isComplete && <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5, marginRight: 6 }} />}
              {statusLabel}
            </span>
          )}
        </div>

        {status && (
          <>
            <div className="status-grid">
              <div className="stat-item">
                <div className="stat-value info">{status.total_documents}</div>
                <div className="stat-label">Total</div>
              </div>
              <div className="stat-item">
                <div className="stat-value success">{status.successful_documents}</div>
                <div className="stat-label">Successful</div>
              </div>
              <div className="stat-item">
                <div className="stat-value danger">{status.failed_documents}</div>
                <div className="stat-label">Failed</div>
              </div>
              <div className="stat-item">
                <div className="stat-value warning">{status.processed_documents}</div>
                <div className="stat-label">Processed</div>
              </div>
            </div>

            <div className="progress-section">
              <div className="progress-header">
                <span className="progress-label">Processing Progress</span>
                <span className="progress-value">{status.progress_percent}%</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${status.progress_percent}%` }}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Leads Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-icon">👥</span>
          <span className="card-title">Extracted Leads</span>
          {leads.length > 0 && (
            <span style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--text-muted)' }}>
              {leads.length} lead{leads.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {leads.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">{isComplete ? '📭' : '⏳'}</div>
            <div className="empty-state-text">
              {isComplete ? 'No leads extracted' : 'Waiting for processing to complete...'}
            </div>
          </div>
        ) : (
          <div className="table-container">
            <table className="lead-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>First Name</th>
                  <th>Last Name</th>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Phone</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead, idx) => (
                  <tr key={lead.lead_id}>
                    <td style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                    <td className={lead.first_name ? '' : 'empty-cell'}>{lead.first_name || '—'}</td>
                    <td className={lead.last_name ? '' : 'empty-cell'}>{lead.last_name || '—'}</td>
                    <td className={lead.job_title ? '' : 'empty-cell'}>{lead.job_title || '—'}</td>
                    <td className={lead.company ? '' : 'empty-cell'}>{lead.company || '—'}</td>
                    <td className={lead.location ? '' : 'empty-cell'}>{lead.location || '—'}</td>
                    <td className={lead.phone_number ? '' : 'empty-cell'}>{lead.phone_number || '—'}</td>
                    <td className={lead.email_address ? '' : 'empty-cell'}>{lead.email_address || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {leads.length > 0 && (
          <div className="export-section" style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <a
              href={getExportUrl(jobId)}
              className="btn btn-success"
              download
            >
              📥 Download Excel (.xlsx)
            </a>
            <button
              className="btn btn-primary"
              onClick={onNewJob}
            >
              ✨ Process New Cards
            </button>
          </div>
        )}

        {isComplete && leads.length === 0 && (
          <div style={{ marginTop: 20, textAlign: 'center' }}>
            <button
              className="btn btn-primary"
              onClick={onNewJob}
            >
              ✨ Try Again / New Job
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── App Root ─── */
export default function App() {
  const [step, setStep] = useState<Step>('setup');
  const [jobId, setJobId] = useState('');
  const [expectedCount, setExpectedCount] = useState(0);

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-logo">🤖</span>
        <span className="app-title">Business Card AI</span>
        <span className="app-subtitle">Qwen VLM Lead Extraction</span>
      </header>

      <main className="main-content">
        {step === 'setup' && (
          <SetupScreen
            onJobCreated={(id, total) => {
              setJobId(id);
              setExpectedCount(total);
              setStep('upload');
            }}
          />
        )}

        {step === 'upload' && (
          <UploadScreen
            jobId={jobId}
            expectedCount={expectedCount}
            onUploadComplete={() => setStep('dashboard')}
          />
        )}

        {step === 'dashboard' && (
          <Dashboard
            jobId={jobId}
            onNewJob={() => {
              setJobId('');
              setExpectedCount(0);
              setStep('setup');
            }}
          />
        )}
      </main>
    </div>
  );
}
