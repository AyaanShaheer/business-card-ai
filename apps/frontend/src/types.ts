export interface JobResponse {
  job_id: string;
  status: string;
  total_documents: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  total_documents: number;
  processed_documents: number;
  successful_documents: number;
  failed_documents: number;
  review_documents: number;
  progress_percent: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BulkUploadFileResult {
  filename: string;
  success: boolean;
  document_id: string | null;
  error: string | null;
}

export interface BulkUploadResponse {
  job_id: string;
  accepted: number;
  rejected: number;
  results: BulkUploadFileResult[];
}

export interface LeadResponse {
  lead_id: string;
  document_id: string;
  first_name: string | null;
  last_name: string | null;
  job_title: string | null;
  company: string | null;
  location: string | null;
  phone_number: string | null;
  email_address: string | null;
}

export interface LeadListResponse {
  job_id: string;
  total: number;
  items: LeadResponse[];
}
