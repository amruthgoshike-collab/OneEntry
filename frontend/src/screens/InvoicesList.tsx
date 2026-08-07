import { ReceiptText } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import { Badge, Empty, ErrorNote, PdfLink, RecordRow, SkeletonRows, docTone } from '../components/ui'
import { api } from '../lib/api'
import { compactRupees, daysUntil, rupees, shortDate } from '../lib/format'
import type { InvoiceSummary } from '../lib/types'

export default function InvoicesList() {
  const [rows, setRows] = useState<InvoiceSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listInvoices()
      .then((data) => setRows(data.items))
      .catch((err: Error) => setError(err.message))
  }, [])

  const outstanding = useMemo(() => {
    if (!rows) return 0
    return rows
      .filter((inv) => inv.status === 'unpaid')
      .reduce((acc, inv) => acc + Number(inv.total), 0)
  }, [rows])

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-headline-lg text-ink m-0 mb-2">Invoices</h1>
          <p className="text-body-lg text-ink-muted m-0">
            {rows
              ? `${rows.length} invoices · ${compactRupees(outstanding)} outstanding.`
              : 'Loading…'}
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {!rows ? (
          <SkeletonRows count={6} />
        ) : rows.length === 0 ? (
          <div className="rule-t">
            <Empty>No invoices yet. Approve a quotation and one appears here instantly.</Empty>
          </div>
        ) : (
          <Stack className="rule-t">
            {rows.map((inv) => {
              const days = daysUntil(inv.due_date)
              const overdue = inv.status === 'unpaid' && days !== null && days < 0
              return (
                <Item key={inv.id}>
                  <RecordRow stripe={overdue ? '#F5DFE1' : inv.status === 'paid' ? '#DEE9DF' : '#DCE8F0'}>
                    <div className="flex gap-4 flex-1 min-w-0 items-start">
                      <ReceiptText size={18} className="text-ink-muted mt-1 shrink-0" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-body-lg font-semibold text-ink">
                            {inv.invoice_number}
                          </span>
                          <span className="text-currency-md text-ink">{rupees(inv.total)}</span>
                          <Badge tone={docTone(inv.status)}>{inv.status}</Badge>
                          {overdue && <Badge tone="overdue">{Math.abs(days!)} days late</Badge>}
                        </div>
                        <div className="text-body-md text-ink-muted">
                          <Link
                            to={`/jobs/${inv.job_id}`}
                            className="hover:text-action hover:underline"
                          >
                            {inv.job_number} — {inv.job_title}
                          </Link>{' '}
                          · {inv.customer_name}
                          {inv.quotation_number ? ` · from ${inv.quotation_number}` : ''} · due{' '}
                          {shortDate(inv.due_date)}
                        </div>
                      </div>
                    </div>
                    <div className="sm:shrink-0">
                      <PdfLink url={inv.pdf_url} />
                    </div>
                  </RecordRow>
                </Item>
              )
            })}
          </Stack>
        )}
      </div>
    </Page>
  )
}
