import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Banknote,
  CheckCircle,
  CircleDot,
  FileText,
  Lightbulb,
  PlusCircle,
  ReceiptText,
  ScrollText,
  Sparkles,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import {
  Badge,
  Button,
  Empty,
  ErrorNote,
  PdfLink,
  RecordRow,
  Section,
  SkeletonRows,
  Working,
  docTone,
  jobTone,
} from '../components/ui'
import { api } from '../lib/api'
import { relativeDays, rupees, shortDate, titleCase } from '../lib/format'
import type { JobDetail as JobDetailData } from '../lib/types'

// One colour per artifact kind, so the spine tells you what a row is.
const STRIPE = {
  quotation: '#DCE8F0', // carbon
  invoice: '#DEE9DF', // ledger
  certificate: '#F1E5CE', // manila
  document: '#E5E2DA', // rule
}

const EVENT_ICON: Record<string, LucideIcon> = {
  job_created: PlusCircle,
  quotation_generated: ScrollText,
  quotation_approved: CheckCircle,
  invoice_created: ReceiptText,
  invoice_paid: Banknote,
  certificate_issued: BadgeCheck,
  status_changed: ArrowRight,
}

type BusyAction = 'quotation' | 'approve' | 'complete' | 'certificate' | null

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const [job, setJob] = useState<JobDetailData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<BusyAction>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!id) return
    try {
      setJob(await api.getJob(id))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  // Every action reloads the job, so the timeline and artifact lists stay
  // truthful rather than being patched optimistically.
  async function run(label: Exclude<BusyAction, null>, fn: () => Promise<unknown>) {
    setBusy(label)
    setError(null)
    try {
      await fn()
      await load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (loading) {
    return (
      <Page>
        <div className="max-w-4xl mx-auto">
          <div className="skeleton h-7 w-2/5 mb-3" />
          <div className="skeleton h-4 w-1/4 mb-8" />
          <SkeletonRows count={5} />
        </div>
      </Page>
    )
  }
  if (!job) {
    return (
      <Page>
        <div className="max-w-4xl mx-auto">
          <ErrorNote error={error ?? 'Job not found'} />
          <Link to="/jobs" className="text-body-md text-action hover:underline">
            Back to jobs
          </Link>
        </div>
      </Page>
    )
  }

  const draftQuotation = job.quotations.find((q) => q.status === 'draft')
  const isCompleted = job.status === 'completed'
  const latestInvoice = job.invoices[job.invoices.length - 1]

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <Link
          to="/jobs"
          className="text-body-md text-ink-muted hover:text-ink inline-flex items-center gap-1 mb-4"
        >
          <ArrowLeft size={16} />
          Jobs
        </Link>

        {/* ---- header ---- */}
        <div className="mb-6">
          <div className="flex items-baseline gap-4 mb-2 flex-wrap">
            <h1 className="text-headline-lg text-ink m-0">{job.title}</h1>
            <Badge tone={jobTone(job.status)}>{titleCase(job.status)}</Badge>
          </div>
          <p className="text-body-lg text-ink-muted m-0">
            {job.job_number} · {job.customer.name}
            {job.site_address ? ` · ${job.site_address}` : ''}
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {/* ---- actions ---- */}
        <div className="rule-all p-4 mb-6 flex flex-wrap items-center gap-3 bg-white">
          <Button
            variant="primary"
            icon={Sparkles}
            disabled={Boolean(busy)}
            onClick={() => void run('quotation', () => api.generateQuotation(job.id))}
          >
            {busy === 'quotation' ? 'Writing quotation…' : 'Generate quotation'}
          </Button>

          <Button
            icon={CheckCircle}
            disabled={Boolean(busy) || !draftQuotation}
            title={draftQuotation ? undefined : 'No draft quotation to approve'}
            onClick={() =>
              void run('approve', () => api.approveQuotation(draftQuotation!.id))
            }
          >
            {busy === 'approve' ? 'Approving…' : 'Approve → invoice'}
          </Button>

          {!isCompleted && (
            <Button
              icon={CircleDot}
              disabled={Boolean(busy)}
              onClick={() => void run('complete', () => api.patchJob(job.id, { status: 'completed' }))}
            >
              {busy === 'complete' ? 'Marking…' : 'Mark complete'}
            </Button>
          )}

          <Button
            icon={BadgeCheck}
            disabled={Boolean(busy) || !isCompleted}
            title={isCompleted ? undefined : 'Job must be completed first'}
            onClick={() => void run('certificate', () => api.generateCertificate(job.id))}
          >
            {busy === 'certificate' ? 'Writing certificate…' : 'Generate certificate'}
          </Button>
        </div>

        {busy === 'quotation' && (
          <Working label="Gemini is reading the job and pricing line items. This takes 5–15 seconds." />
        )}
        {busy === 'certificate' && <Working label="Gemini is drafting the completion wording…" />}
        {busy === 'approve' && <Working label="Copying line items into an invoice…" />}

        {/* ---- customer + description ---- */}
        <div className="grid sm:grid-cols-2 gap-4 mb-6">
          <div className="rule-all p-4">
            <div className="text-label-caps text-ink-muted mb-2">Customer</div>
            <div className="text-body-lg font-semibold text-ink">{job.customer.name}</div>
            {job.customer.address && (
              <div className="text-body-md text-ink-muted">{job.customer.address}</div>
            )}
            {job.customer.gstin && (
              <div className="text-body-md text-ink-muted">GSTIN: {job.customer.gstin}</div>
            )}
            {job.customer.phone && (
              <div className="text-body-md text-ink-muted">Ph: {job.customer.phone}</div>
            )}
          </div>
          <div className="rule-all p-4">
            <div className="text-label-caps text-ink-muted mb-2">Job</div>
            <div className="text-raw-message text-ink">{job.description || 'No description.'}</div>
            <div className="text-body-md text-ink-muted mt-2">
              Created {shortDate(job.created_at)}
              {job.completed_on ? ` · Completed ${shortDate(job.completed_on)}` : ''}
            </div>
          </div>
        </div>

        {/* ---- quotations ---- */}
        <Section title="Quotations" count={job.quotations.length}>
          {job.quotations.length === 0 && <Empty>No quotation yet. Generate one above.</Empty>}
          <Stack>
            {job.quotations.map((q) => (
              <Item key={q.id}>
                <RecordRow stripe={STRIPE.quotation}>
                  <div className="flex gap-4 flex-1 min-w-0 items-start">
                    <ScrollText size={18} className="text-ink-muted mt-1 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-body-lg font-semibold text-ink">
                          {q.quotation_number}
                        </span>
                        <span className="text-currency-md text-ink">{rupees(q.total)}</span>
                        <Badge tone={docTone(q.status)}>{q.status}</Badge>
                      </div>
                      <div className="text-body-md text-ink-muted">
                        {q.line_items.length} line items · {shortDate(q.created_at)} · GST{' '}
                        {q.gst_rate}% ({rupees(q.gst_amount)})
                      </div>
                    </div>
                  </div>
                  <div className="sm:shrink-0 flex items-center gap-4">
                    <PdfLink url={q.pdf_url} />
                    {q.status === 'draft' && (
                      <Button
                        disabled={Boolean(busy)}
                        onClick={() => void run('approve', () => api.approveQuotation(q.id))}
                      >
                        Approve
                      </Button>
                    )}
                  </div>
                </RecordRow>
              </Item>
            ))}
          </Stack>
        </Section>

        {/* ---- invoices ---- */}
        <Section title="Invoices" count={job.invoices.length}>
          {job.invoices.length === 0 && (
            <Empty>No invoice yet. Approving a quotation creates one instantly.</Empty>
          )}
          <Stack>
            {job.invoices.map((inv) => (
              <Item key={inv.id}>
                <RecordRow stripe={STRIPE.invoice}>
                  <div className="flex gap-4 flex-1 min-w-0 items-start">
                    <ReceiptText size={18} className="text-ink-muted mt-1 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-body-lg font-semibold text-ink">
                          {inv.invoice_number}
                        </span>
                        <span className="text-currency-md text-ink">{rupees(inv.total)}</span>
                        <Badge tone={docTone(inv.status)}>{inv.status}</Badge>
                      </div>
                      <div className="text-body-md text-ink-muted">
                        {inv.line_items.length} line items · raised {shortDate(inv.created_at)} ·
                        due {shortDate(inv.due_date)}
                      </div>
                    </div>
                  </div>
                  <div className="sm:shrink-0">
                    <PdfLink url={inv.pdf_url} />
                  </div>
                </RecordRow>
              </Item>
            ))}
          </Stack>
        </Section>

        {/* ---- certificates ---- */}
        <Section title="Certificates" count={job.certificates.length}>
          {job.certificates.length === 0 && (
            <Empty>
              {isCompleted
                ? 'Job is complete — generate the certificate above.'
                : 'Mark the job complete to issue a certificate.'}
            </Empty>
          )}
          <Stack>
            {job.certificates.map((cert) => (
              <Item key={cert.id}>
                <RecordRow stripe={STRIPE.certificate} className="sm:items-start">
                  <div className="flex gap-4 flex-1 min-w-0 items-start">
                    <BadgeCheck size={18} className="text-ink-muted mt-1 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-body-lg font-semibold text-ink">
                          {cert.certificate_number}
                        </span>
                        <Badge tone="done">issued {shortDate(cert.issued_on)}</Badge>
                      </div>
                      {cert.scope_summary && (
                        <div className="text-raw-message text-ink-muted bg-[#F4F3F1] p-2 rounded mt-1">
                          {cert.scope_summary}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="sm:shrink-0">
                    <PdfLink url={cert.pdf_url} />
                  </div>
                </RecordRow>
              </Item>
            ))}
          </Stack>
        </Section>

        {/* ---- documents ---- */}
        {job.documents.length > 0 && (
          <Section title="Documents" count={job.documents.length}>
            <Stack>
              {job.documents.map((doc) => (
                <Item key={doc.id}>
                  <RecordRow stripe={STRIPE.document}>
                    <div className="flex gap-4 flex-1 min-w-0 items-start">
                      <FileText size={18} className="text-ink-muted mt-1 shrink-0" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-body-lg font-semibold text-ink truncate">
                            {doc.filename}
                          </span>
                          {doc.total_amount && (
                            <span className="text-currency-md text-ink">
                              {rupees(doc.total_amount)}
                            </span>
                          )}
                          <Badge tone={docTone(doc.status)}>{doc.status}</Badge>
                        </div>
                        <div className="text-body-md text-ink-muted">
                          {doc.vendor_name ?? 'Vendor unknown'} · {shortDate(doc.document_date)}
                        </div>
                      </div>
                    </div>
                  </RecordRow>
                </Item>
              ))}
            </Stack>
          </Section>
        )}

        {/* ---- timeline ---- */}
        <Section title="Timeline" count={job.events.length}>
          <Stack>
            {job.events.map((event) => {
              const EventIcon = EVENT_ICON[event.event_type] ?? CircleDot
              return (
                <Item key={event.id}>
                  <div className="relative pl-6 py-3 rule-b flex gap-4 items-start">
                    <div className="provenance-strip" style={{ backgroundColor: '#E5E2DA' }} />
                    <EventIcon size={16} className="text-ink-muted mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-body-md text-ink">{event.detail}</div>
                      <div className="text-label-caps text-ink-muted mt-0.5">
                        {titleCase(event.event_type)} · {shortDate(event.created_at)} ·{' '}
                        {relativeDays(event.created_at)}
                      </div>
                    </div>
                  </div>
                </Item>
              )
            })}
          </Stack>
        </Section>

        {latestInvoice && (
          <div className="rule-all p-4 bg-white flex items-center gap-3">
            <Lightbulb size={18} className="text-ink shrink-0" />
            <p className="text-body-lg text-ink m-0">
              This job was entered once. Everything below it — {job.quotations.length} quotation
              {job.quotations.length === 1 ? '' : 's'}, {job.invoices.length} invoice
              {job.invoices.length === 1 ? '' : 's'}
              {job.certificates.length ? ` and ${job.certificates.length} certificate` : ''} worth{' '}
              <span className="text-currency-md">{rupees(latestInvoice.total)}</span> — generated
              itself.
            </p>
          </div>
        )}
      </div>
    </Page>
  )
}
