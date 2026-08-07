// Upload a bill/receipt; Gemini extracts it in the background. This screen
// polls while anything is still "uploaded" so rows flip to extracted on
// their own.
import { CloudUpload, FileText, TriangleAlert } from 'lucide-react'
import type { ChangeEvent, DragEvent } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import { Badge, Empty, ErrorNote, RecordRow, SkeletonRows, docTone } from '../components/ui'
import { api } from '../lib/api'
import { rupees, shortDate, titleCase } from '../lib/format'
import type { Doc } from '../lib/types'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp'
const POLL_MS = 2500

export default function Documents() {
  const [docs, setDocs] = useState<Doc[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const load = useCallback(async () => {
    try {
      const data = await api.listDocuments()
      setDocs(data.items)
      // Keep polling while extraction is running on any row.
      if (data.items.some((d) => d.status === 'uploaded')) {
        clearTimeout(timer.current)
        timer.current = setTimeout(() => void load(), POLL_MS)
      }
    } catch (err) {
      setError((err as Error).message)
    }
  }, [])

  useEffect(() => {
    void load()
    return () => clearTimeout(timer.current)
  }, [load])

  async function upload(files: FileList | File[]) {
    setUploading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await api.uploadDocument(file)
      }
      await load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragOver(false)
    if (event.dataTransfer.files.length) void upload(event.dataTransfer.files)
  }

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files?.length) void upload(event.target.files)
    event.target.value = ''
  }

  const extracting = docs?.filter((d) => d.status === 'uploaded').length ?? 0

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-headline-lg text-ink m-0 mb-2">Documents</h1>
          <p className="text-body-lg text-ink-muted m-0">
            Drop in bills and receipts — Gemini reads them, no retyping.
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {/* ---- upload zone ---- */}
        <button
          type="button"
          className={`w-full rule-all p-8 mb-2 flex flex-col items-center gap-2 rounded transition-colors ${
            dragOver ? 'bg-carbon/60' : 'bg-white hover:bg-carbon/30'
          }`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(event) => {
            event.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          disabled={uploading}
        >
          <CloudUpload size={28} className="text-action" />
          <div className="text-body-lg font-semibold text-ink">
            {uploading ? 'Uploading…' : 'Drop a PDF or photo here, or click to choose'}
          </div>
          <div className="text-body-md text-ink-muted">
            PDF, PNG, JPEG or WebP — extraction takes a few seconds
          </div>
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            onChange={onPick}
          />
        </button>
        {extracting > 0 && (
          <div className="mb-6">
            <div className="working-rule mb-1" />
            <div className="text-body-md text-ink-muted">
              Extracting {extracting} document{extracting === 1 ? '' : 's'}…
            </div>
          </div>
        )}

        {/* ---- list ---- */}
        <div className="mt-6">
          {!docs ? (
            <SkeletonRows count={4} />
          ) : docs.length === 0 ? (
            <div className="rule-t">
              <Empty>Nothing uploaded yet.</Empty>
            </div>
          ) : (
            <Stack className="rule-t">
              {docs.map((doc) => {
                const warnings = (doc.extracted_json?.validation_warnings as string[] | undefined) ?? []
                const failure = doc.extracted_json?.error as string | undefined
                return (
                  <Item key={doc.id}>
                    <RecordRow
                      stripe={
                        doc.status === 'failed'
                          ? '#F5DFE1'
                          : doc.status === 'extracted'
                            ? '#DEE9DF'
                            : '#E5E2DA'
                      }
                      className="sm:items-start"
                    >
                      <div className="flex gap-4 flex-1 min-w-0 items-start">
                        <FileText size={18} className="text-ink-muted mt-1 shrink-0" />
                        <div className="min-w-0 flex-1">
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
                            {doc.doc_type && doc.doc_type !== 'other' && (
                              <Badge tone="info">{doc.doc_type}</Badge>
                            )}
                          </div>

                          {doc.status === 'extracted' && (
                            <>
                              <div className="text-body-md text-ink-muted">
                                {doc.vendor_name ?? 'Vendor unknown'} ·{' '}
                                {shortDate(doc.document_date)}
                                {doc.expense_category
                                  ? ` · ${titleCase(doc.expense_category)}`
                                  : ''}
                                {doc.due_date ? ` · due ${shortDate(doc.due_date)}` : ''}
                              </div>
                              {doc.summary && (
                                <div className="text-raw-message text-ink-muted bg-[#F4F3F1] p-2 rounded mt-1 inline-block">
                                  {doc.summary}
                                </div>
                              )}
                              {warnings.length > 0 && (
                                <div className="flex items-start gap-2 mt-2 text-body-md text-ink">
                                  <TriangleAlert size={14} className="mt-0.5 text-[#8a6d1a] shrink-0" />
                                  <span>{warnings.join('; ')}</span>
                                </div>
                              )}
                            </>
                          )}
                          {doc.status === 'failed' && (
                            <div className="text-body-md text-ink-muted">
                              {failure ?? 'Extraction failed — try uploading again.'}
                            </div>
                          )}
                          {doc.status === 'uploaded' && (
                            <div className="text-body-md text-ink-muted">Reading the document…</div>
                          )}
                        </div>
                      </div>
                      {doc.job_id && (
                        <Link
                          to={`/jobs/${doc.job_id}`}
                          className="text-body-md text-action font-semibold hover:underline sm:shrink-0"
                        >
                          Job
                        </Link>
                      )}
                    </RecordRow>
                  </Item>
                )
              })}
            </Stack>
          )}
        </div>
      </div>
    </Page>
  )
}
