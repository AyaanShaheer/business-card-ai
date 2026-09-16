import type {
  JobResponse,
  JobStatusResponse,
  BulkUploadResponse,
  LeadListResponse,
} from './types';

const BASE = '/api';

export async function createJob(totalDocuments: number): Promise<JobResponse> {
  const res = await fetch(`${BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ total_documents: totalDocuments }),
  });
  if (!res.ok) throw new Error(`Failed to create job: ${res.statusText}`);
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get job: ${res.statusText}`);
  return res.json();
}

export async function uploadDocumentsBulk(
  jobId: string,
  files: File[],
): Promise<BulkUploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));

  const res = await fetch(`${BASE}/jobs/${jobId}/documents/bulk`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function getLeads(jobId: string): Promise<LeadListResponse> {
  const res = await fetch(`${BASE}/jobs/${jobId}/leads`);
  if (!res.ok) throw new Error(`Failed to get leads: ${res.statusText}`);
  return res.json();
}

export function getExportUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/export/xlsx`;
}
