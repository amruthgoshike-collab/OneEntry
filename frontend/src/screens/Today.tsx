// The morning screen: what came in, what needs you, how the book looks.
// Everything is computed client-side from the four list endpoints.
import { ArrowRight, CircleAlert, FileClock, Lightbulb, ScrollText } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import { Badge, ErrorNote, RecordRow, Section, SkeletonRows, Stat } from '../components/ui'
import { api } from '../lib/api'
import { compactRupees, daysUntil, rupees, shortDate } from '../lib/format'
import type { Doc, InvoiceSummary, JobSummary, QuotationSummary } from '../lib/types'

const DATE_LINE = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  weekday: 'long',
}).format(new Date())

export default function Today() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [quotations, setQuotations] = useState<QuotationSummary[] | null>(null)
  const [invoices, setInvoices] = useState<InvoiceSummary[] | null>(null)
  const [documents, setDocuments] = useState<Doc[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.listJobs(), api.listQuotations(), api.listInvoices(), api.listDocuments()])
      .then(([j, q, i, d]) => {
        setJobs(j.items)
        setQuotations(q.items)
        setInvoices(i.items)
        setDocuments(d.items)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  const loading = !jobs || !quotations || !invoices || !documents

  const view = useMemo(() => {
    if (loading) return null
    const unpaid = invoices!.filter((inv) => inv.status === 'unpaid')
    const drafts = quotations!.filter((q) => q.status === 'draft')
    const failedDocs = documents!.filter((d) => d.status === 'failed')
    const active = jobs!.filter((j) => j.status !== 'completed')

    const sum = (rows: { total: string }[]) => rows.reduce((acc, r) => acc + Number(r.total), 0)

    const byCustomer = new Map<string, number>()
    for (const inv of invoices!) {
      byCustomer.set(inv.customer_name, (byCustomer.get(inv.customer_name) ?? 0) + Number(inv.total))
    }
    const topCustomer = [...byCustomer.entries()].sort((a, b) => b[1] - a[1])[0]

    return {
      unpaid,
      drafts,
      failedDocs,
      active,
      unpaidTotal: sum(unpaid),
      draftTotal: sum(drafts),
      paidTotal: sum(invoices!.filter((inv) => inv.status === 'paid')),
      topCustomer,
      needsYou: drafts.length + unpaid.length + failedDocs.length,
      recentJobs: jobs!.slice(0, 4),
    }
  }, [loading, jobs, quotations, invoices, documents])

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <div className="flex items-baseline gap-4 mb-2">
            <h1 className="text-headline-lg text-ink m-0">Today</h1>
            <span className="text-body-md text-ink-muted">{DATE_LINE}</span>
          </div>
          <p className="text-body-lg text-ink-muted m-0">
            {loading || !view
              ? 'Opening the book…'
              : view.needsYou > 0
                ? `${view.needsYou} thing${view.needsYou === 1 ? '' : 's'} need${view.needsYou === 1 ? 's' : ''} you.`
                : 'All caught up. Nothing needs you.'}
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {loading || !view ? (
          <SkeletonRows count={6} />
        ) : (
          <>
            {/* ---- the book at a glance ---- */}
            <Stack className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <Item>
                <Stat
                  label="Active jobs"
                  value={view.active.length}
                  hint={`${jobs!.length} total`}
                  tone="#DCE8F0"
                />
              </Item>
              <Item>
                <Stat
                  label="Outstanding"
                  value={compactRupees(view.unpaidTotal)}
                  hint={`${view.unpaid.length} unpaid invoice${view.unpaid.length === 1 ? '' : 's'}`}
                  tone="#F5DFE1"
                />
              </Item>
              <Item>
                <Stat
                  label="Awaiting approval"
                  value={compactRupees(view.draftTotal)}
                  hint={`${view.drafts.length} draft quotation${view.drafts.length === 1 ? '' : 's'}`}
                  tone="#F1E5CE"
                />
              </Item>
              <Item>
                <Stat
                  label="Collected"
                  value={compactRupees(view.paidTotal)}
                  hint="paid invoices"
                  tone="#DEE9DF"
                />
              </Item>
            </Stack>

            {/* ---- needs you ---- */}
            <Section title="Needs you" count={view.needsYou}>
              {view.needsYou === 0 && (
                <div className="py-4 pl-6 rule-b bg-ledger/60 text-body-md text-ink-muted">
                  Nothing waiting. Enquiries turn into quotations from the job page.
                </div>
              )}
              <Stack>
                {view.drafts.map((q) => (
                  <Item key={q.id}>
                    <RecordRow stripe="#F1E5CE">
                      <div className="flex gap-4 flex-1 min-w-0 items-start">
                        <ScrollText size={18} className="text-ink-muted mt-1 shrink-0" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-body-lg font-semibold text-ink">
                              {q.quotation_number} awaiting customer approval
                            </span>
                            <span className="text-currency-md text-ink">{rupees(q.total)}</span>
                          </div>
                          <div className="text-body-md text-ink-muted">
                            {q.job_title} · {q.customer_name}
                          </div>
                        </div>
                      </div>
                      <Link
                        to={`/jobs/${q.job_id}`}
                        className="text-body-md text-action font-semibold hover:underline inline-flex items-center gap-1 sm:shrink-0"
                      >
                        Open job <ArrowRight size={14} />
                      </Link>
                    </RecordRow>
                  </Item>
                ))}
                {view.unpaid.map((inv) => {
                  const days = daysUntil(inv.due_date)
                  const overdue = days !== null && days < 0
                  return (
                    <Item key={inv.id}>
                      <RecordRow stripe={overdue ? '#F5DFE1' : '#DCE8F0'}>
                        <div className="flex gap-4 flex-1 min-w-0 items-start">
                          <FileClock size={18} className="text-ink-muted mt-1 shrink-0" />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="text-body-lg font-semibold text-ink">
                                {inv.invoice_number} unpaid
                              </span>
                              <span className="text-currency-md text-ink">{rupees(inv.total)}</span>
                              {overdue ? (
                                <Badge tone="overdue">{Math.abs(days!)} days late</Badge>
                              ) : (
                                days !== null && <Badge tone="info">due in {days} days</Badge>
                              )}
                            </div>
                            <div className="text-body-md text-ink-muted">
                              {inv.customer_name} · due {shortDate(inv.due_date)}
                            </div>
                          </div>
                        </div>
                        <Link
                          to={`/jobs/${inv.job_id}`}
                          className="text-body-md text-action font-semibold hover:underline inline-flex items-center gap-1 sm:shrink-0"
                        >
                          Open job <ArrowRight size={14} />
                        </Link>
                      </RecordRow>
                    </Item>
                  )
                })}
                {view.failedDocs.map((doc) => (
                  <Item key={doc.id}>
                    <RecordRow stripe="#F5DFE1">
                      <div className="flex gap-4 flex-1 min-w-0 items-start">
                        <CircleAlert size={18} className="text-ink-muted mt-1 shrink-0" />
                        <div className="min-w-0">
                          <div className="text-body-lg font-semibold text-ink mb-1">
                            {doc.filename} failed extraction
                          </div>
                          <div className="text-body-md text-ink-muted">Re-upload it from Documents.</div>
                        </div>
                      </div>
                      <Link
                        to="/documents"
                        className="text-body-md text-action font-semibold hover:underline sm:shrink-0"
                      >
                        Documents
                      </Link>
                    </RecordRow>
                  </Item>
                ))}
              </Stack>
            </Section>

            {/* ---- recent jobs ---- */}
            <Section title="Recent jobs" action={
              <Link to="/jobs" className="text-body-md text-action font-semibold hover:underline">
                All jobs
              </Link>
            }>
              <Stack>
                {view.recentJobs.map((job) => (
                  <Item key={job.id}>
                    <RecordRow stripe={job.has_certificate ? '#DEE9DF' : '#DCE8F0'}>
                      <div className="min-w-0 flex-1">
                        <Link
                          to={`/jobs/${job.id}`}
                          className="text-body-lg font-semibold text-ink hover:text-action"
                        >
                          {job.title}
                        </Link>
                        <div className="text-body-md text-ink-muted">
                          {job.job_number} · {job.customer_name} · {shortDate(job.created_at)}
                        </div>
                      </div>
                      <Badge tone={job.status === 'completed' ? 'done' : 'info'}>
                        {job.status.replace('_', ' ')}
                      </Badge>
                    </RecordRow>
                  </Item>
                ))}
              </Stack>
            </Section>

            {/* ---- insight ---- */}
            {view.topCustomer && (
              <div className="rule-all p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex gap-3 items-start">
                  <Lightbulb size={18} className="text-ink mt-0.5 shrink-0" />
                  <p className="text-body-lg text-ink m-0">
                    <span className="font-semibold">{view.topCustomer[0]}</span> is your biggest
                    customer — <span className="text-currency-md">{rupees(view.topCustomer[1].toFixed(2))}</span>{' '}
                    invoiced across {invoices!.filter((i) => i.customer_name === view.topCustomer![0]).length}{' '}
                    invoices.
                  </p>
                </div>
                <Link
                  to={`/search?q=${encodeURIComponent('which customer gave us the most business')}`}
                  className="text-body-md text-ink font-semibold underline hover:text-action sm:shrink-0"
                >
                  Ask the data
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </Page>
  )
}
