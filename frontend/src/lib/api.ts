// Every backend call goes through here.
import type {
  ApproveResponse,
  Certificate,
  Doc,
  InvoiceSummary,
  JobDetail,
  JobSummary,
  Quotation,
  QuotationSummary,
  SearchResponse,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8080/api'
const ORIGIN = BASE.replace(/\/api\/?$/, '')

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isForm = options.body instanceof FormData
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: isForm
      ? options.headers
      : { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })

  if (!res.ok) {
    // The contract promises { "detail": "human readable message" } on failure.
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

export const api = {
  listJobs: () => request<{ items: JobSummary[] }>('/jobs'),
  getJob: (id: string) => request<JobDetail>(`/jobs/${id}`),
  patchJob: (id: string, patch: Record<string, unknown>) =>
    request<JobDetail>(`/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  // Takes 5-15s: Gemini writes the line items. Callers must show progress.
  generateQuotation: (jobId: string, notes?: string) =>
    request<Quotation>(`/jobs/${jobId}/quotation`, {
      method: 'POST',
      body: JSON.stringify(notes ? { notes } : {}),
    }),

  // No LLM: copies rows. Returns in well under a second.
  approveQuotation: (quotationId: string) =>
    request<ApproveResponse>(`/quotations/${quotationId}/approve`, { method: 'POST' }),

  generateCertificate: (jobId: string) =>
    request<Certificate>(`/jobs/${jobId}/certificate`, { method: 'POST' }),

  listQuotations: () => request<{ items: QuotationSummary[] }>('/quotations'),
  listInvoices: () => request<{ items: InvoiceSummary[] }>('/invoices'),

  search: (q: string) =>
    request<SearchResponse>('/search', { method: 'POST', body: JSON.stringify({ q }) }),

  listDocuments: () => request<{ items: Doc[] }>('/documents'),
  getDocument: (id: string) => request<Doc>(`/documents/${id}`),
  uploadDocument: (file: File, jobId?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (jobId) form.append('job_id', jobId)
    return request<{ id: string; status: string }>('/documents', { method: 'POST', body: form })
  },

  // pdf_url comes back as an API path like /api/quotations/{id}/pdf
  fileUrl: (pdfUrl: string | null) => (pdfUrl ? `${ORIGIN}${pdfUrl}` : null),
}
