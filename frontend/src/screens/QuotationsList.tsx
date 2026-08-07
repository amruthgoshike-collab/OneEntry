import { ScrollText } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import {
  Badge,
  Button,
  Empty,
  ErrorNote,
  PdfLink,
  RecordRow,
  SkeletonRows,
  docTone,
} from '../components/ui'
import { api } from '../lib/api'
import { rupees, shortDate } from '../lib/format'
import type { QuotationSummary } from '../lib/types'

export default function QuotationsList() {
  const [rows, setRows] = useState<QuotationSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [approving, setApproving] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .listQuotations()
      .then((data) => setRows(data.items))
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function approve(id: string) {
    setApproving(id)
    setError(null)
    try {
      await api.approveQuotation(id)
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setApproving(null)
    }
  }

  const drafts = rows?.filter((q) => q.status === 'draft').length ?? 0

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-headline-lg text-ink m-0 mb-2">Quotations</h1>
          <p className="text-body-lg text-ink-muted m-0">
            {rows
              ? `${rows.length} quotations, ${drafts} awaiting approval. Approval raises the invoice instantly.`
              : 'Loading…'}
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {!rows ? (
          <SkeletonRows count={6} />
        ) : rows.length === 0 ? (
          <div className="rule-t">
            <Empty>No quotations yet. Generate one from a job page.</Empty>
          </div>
        ) : (
          <Stack className="rule-t">
            {rows.map((q) => (
              <Item key={q.id}>
                <RecordRow stripe={q.status === 'draft' ? '#F1E5CE' : '#DCE8F0'}>
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
                        <Link to={`/jobs/${q.job_id}`} className="hover:text-action hover:underline">
                          {q.job_number} — {q.job_title}
                        </Link>{' '}
                        · {q.customer_name} · {q.line_item_count} items · {shortDate(q.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="sm:shrink-0 flex items-center gap-4">
                    <PdfLink url={q.pdf_url} />
                    {q.status === 'draft' && (
                      <Button
                        disabled={Boolean(approving)}
                        onClick={() => void approve(q.id)}
                      >
                        {approving === q.id ? 'Approving…' : 'Approve'}
                      </Button>
                    )}
                  </div>
                </RecordRow>
              </Item>
            ))}
          </Stack>
        )}
      </div>
    </Page>
  )
}
