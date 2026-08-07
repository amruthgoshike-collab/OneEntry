// Plain-English search. Structured questions become SQL against v_search;
// fuzzy recall goes to the vector index. The SQL is shown behind a toggle.
import { ChevronDown, ChevronRight, Search as SearchIcon, Sparkles } from 'lucide-react'
import type { FormEvent } from 'react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Page, Reveal } from '../components/motion'
import { Badge, ErrorNote, Working } from '../components/ui'
import { api } from '../lib/api'
import { groupInr } from '../lib/format'
import type { SearchResponse } from '../lib/types'

const EXAMPLES = [
  'unpaid invoices',
  'invoices above 20000',
  'how many jobs are completed',
  'which customer gave us the most business',
  'that painting job',
]

const MONEY_KEYS = new Set(['amount', 'total', 'total_business', 'sum', 'value'])

function cell(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  const text = String(value)
  if (MONEY_KEYS.has(key.toLowerCase()) && !Number.isNaN(Number(text))) return `₹${groupInr(text)}`
  return text.length > 60 ? `${text.slice(0, 59)}…` : text
}

export default function SearchScreen() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [showSql, setShowSql] = useState(false)

  const run = useCallback(async (question: string) => {
    if (!question.trim()) return
    setRunning(true)
    setError(null)
    setShowSql(false)
    try {
      setResult(await api.search(question.trim()))
    } catch (err) {
      setError((err as Error).message)
      setResult(null)
    } finally {
      setRunning(false)
    }
  }, [])

  // The topbar navigates here with ?q= — run it once on arrival.
  useEffect(() => {
    const fromUrl = params.get('q')
    if (fromUrl) {
      setQ(fromUrl)
      void run(fromUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function submit(event: FormEvent) {
    event.preventDefault()
    setParams(q.trim() ? { q: q.trim() } : {})
    void run(q)
  }

  const columns = result?.results.length ? Object.keys(result.results[0]) : []

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-headline-lg text-ink m-0 mb-2">Search</h1>
          <p className="text-body-lg text-ink-muted m-0">
            Ask in plain English. Numbers and filters become SQL; memories go to
            semantic recall.
          </p>
        </div>

        {/* ---- ask anything ---- */}
        <form onSubmit={submit} className="mb-4">
          <div className="rule-all bg-white flex items-center gap-3 px-4 py-3 focus-within:border-action transition-colors">
            <SearchIcon size={18} className="text-ink-muted shrink-0" />
            <input
              autoFocus
              className="flex-1 bg-transparent border-none outline-none text-body-lg text-ink placeholder:text-ink-muted"
              placeholder="Ask anything"
              value={q}
              onChange={(event) => setQ(event.target.value)}
            />
            <button
              type="submit"
              disabled={running || !q.trim()}
              className="bg-action text-white text-body-md font-semibold px-4 py-1.5 rounded hover:bg-action-hover disabled:opacity-50"
            >
              Ask
            </button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2 mb-8">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              className="rule-all rounded px-3 py-1 text-body-md text-ink-muted hover:text-ink hover:bg-white transition-colors"
              onClick={() => {
                setQ(example)
                setParams({ q: example })
                void run(example)
              }}
            >
              {example}
            </button>
          ))}
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />
        {running && <Working label="Reading the question, querying the book…" />}

        {/* ---- answer ---- */}
        {result && !running && (
          <>
            <div className="rule-all bg-white p-4 mb-4 flex items-start gap-3">
              <Sparkles size={18} className="text-action mt-1 shrink-0" />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-label-caps text-ink-muted">Answer</span>
                  <Badge tone={result.mode === 'structured' ? 'info' : 'attention'}>
                    {result.mode}
                  </Badge>
                </div>
                <p className="text-body-lg text-ink m-0">{result.answer}</p>

                {result.sql && (
                  <div className="mt-3">
                    <button
                      className="text-body-md text-ink-muted hover:text-ink inline-flex items-center gap-1"
                      onClick={() => setShowSql((v) => !v)}
                    >
                      {showSql ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      {showSql ? 'Hide the SQL' : 'Show the SQL it wrote'}
                    </button>
                    <Reveal open={showSql}>
                      <pre className="text-raw-message bg-[#1E2A2E] text-[#DCE8F0] p-3 rounded mt-2 overflow-x-auto whitespace-pre-wrap">
                        {result.sql}
                      </pre>
                    </Reveal>
                  </div>
                )}
              </div>
            </div>

            {/* ---- results table ---- */}
            {result.results.length > 0 && (
              <div className="rule-all bg-white overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="rule-b bg-[#F4F3F1]">
                      {columns.map((col) => (
                        <th
                          key={col}
                          className="text-label-caps text-ink-muted text-left px-4 py-2 whitespace-nowrap"
                        >
                          {col.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((row, index) => {
                      const jobId = (row.job_id ?? '') as string
                      return (
                        <tr key={index} className="rule-b hover:bg-paper transition-colors">
                          {columns.map((col) => (
                            <td key={col} className="px-4 py-2 text-body-md text-ink whitespace-nowrap">
                              {col === 'number' && jobId ? (
                                <Link
                                  to={`/jobs/${jobId}`}
                                  className="text-action font-semibold hover:underline"
                                >
                                  {cell(col, row[col])}
                                </Link>
                              ) : (
                                cell(col, row[col])
                              )}
                            </td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {result.results.length === 0 && (
              <div className="text-body-md text-ink-muted">No rows came back.</div>
            )}
          </>
        )}
      </div>
    </Page>
  )
}
