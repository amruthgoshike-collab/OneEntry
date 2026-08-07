// Response shapes from api_contract.md. Money is always a decimal string
// ("809556.70") — never a number — so it can't drift through float maths.

export interface Entity {
  id: string
  name: string
  type: 'customer' | 'vendor'
  gstin: string | null
  phone: string | null
  email: string | null
  address: string | null
  created_at: string
}

export interface LineItem {
  id: string
  position: number
  description: string
  hsn_sac: string | null
  quantity: string
  unit: string | null
  rate: string
  tax_rate: string
  amount: string
}

export interface Quotation {
  id: string
  job_id: string
  quotation_number: string
  status: 'draft' | 'approved'
  notes: string | null
  subtotal: string
  gst_rate: string
  gst_amount: string
  total: string
  created_at: string
  line_items: LineItem[]
  pdf_url: string | null
}

export interface Invoice {
  id: string
  job_id: string
  quotation_id: string | null
  invoice_number: string
  status: 'unpaid' | 'paid'
  subtotal: string
  gst_rate: string
  gst_amount: string
  total: string
  due_date: string | null
  created_at: string
  line_items: LineItem[]
  pdf_url: string | null
}

export interface Certificate {
  id: string
  job_id: string
  certificate_number: string
  scope_summary: string | null
  issued_on: string | null
  created_at: string
  pdf_url: string | null
}

export interface Doc {
  id: string
  job_id: string | null
  filename: string
  status: 'uploaded' | 'extracted' | 'failed'
  doc_type: string | null
  vendor_name: string | null
  total_amount: string | null
  document_date: string | null
  due_date: string | null
  expense_category: string | null
  summary: string | null
  extracted_json: Record<string, unknown> | null
  created_at: string
}

export interface JobEvent {
  id: string
  job_id: string
  event_type: string
  detail: string | null
  created_at: string
}

export type JobStatus = 'enquiry' | 'quoted' | 'approved' | 'in_progress' | 'completed'

export interface JobSummary {
  id: string
  job_number: string
  customer_id: string
  title: string
  description: string | null
  site_address: string | null
  status: JobStatus
  completed_on: string | null
  created_at: string
  customer_name: string
  quotation_count: number
  invoice_count: number
  has_certificate: boolean
}

export interface JobDetail extends Omit<JobSummary, 'customer_name' | 'quotation_count' | 'invoice_count' | 'has_certificate'> {
  customer: Entity
  quotations: Quotation[]
  invoices: Invoice[]
  certificates: Certificate[]
  documents: Doc[]
  events: JobEvent[]
}

export interface QuotationSummary {
  id: string
  job_id: string
  quotation_number: string
  status: 'draft' | 'approved'
  total: string
  created_at: string
  job_number: string
  job_title: string
  customer_name: string
  line_item_count: number
  pdf_url: string | null
}

export interface InvoiceSummary {
  id: string
  job_id: string
  invoice_number: string
  quotation_number: string | null
  status: 'unpaid' | 'paid'
  total: string
  due_date: string | null
  created_at: string
  job_number: string
  job_title: string
  customer_name: string
  pdf_url: string | null
}

export interface SearchResponse {
  mode: 'structured' | 'semantic'
  answer: string
  sql: string | null
  results: Record<string, unknown>[]
}

export interface ApproveResponse {
  quotation: Quotation
  invoice: Invoice
}
