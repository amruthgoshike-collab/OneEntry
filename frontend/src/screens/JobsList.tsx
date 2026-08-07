import { BadgeCheck, Briefcase } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Item, Page, Stack } from '../components/motion'
import { Badge, ErrorNote, RecordRow, SkeletonRows, jobTone } from '../components/ui'
import { api } from '../lib/api'
import { shortDate, titleCase } from '../lib/format'
import type { JobSummary } from '../lib/types'

export default function JobsList() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listJobs()
      .then((data) => setJobs(data.items))
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-headline-lg text-ink m-0 mb-2">Jobs</h1>
          <p className="text-body-lg text-ink-muted m-0">
            {jobs ? `${jobs.length} jobs. Everything else hangs off these.` : 'Loading…'}
          </p>
        </div>

        <ErrorNote error={error} onDismiss={() => setError(null)} />

        {!jobs ? (
          <SkeletonRows count={6} />
        ) : (
          <Stack className="rule-t">
            {jobs.map((job) => (
              <Item key={job.id}>
                <RecordRow stripe={job.has_certificate ? '#DEE9DF' : '#DCE8F0'}>
                  <div className="flex gap-4 flex-1 min-w-0 items-start">
                    <Briefcase size={18} className="text-ink-muted mt-1 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <Link
                          to={`/jobs/${job.id}`}
                          className="text-body-lg font-semibold text-ink hover:text-action"
                        >
                          {job.title}
                        </Link>
                        <Badge tone={jobTone(job.status)}>{titleCase(job.status)}</Badge>
                      </div>
                      <div className="text-body-md text-ink-muted">
                        {job.job_number} · {job.customer_name} · {shortDate(job.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="sm:shrink-0 flex items-center gap-4 text-body-md text-ink-muted">
                    <span>{job.quotation_count} qtn</span>
                    <span>{job.invoice_count} inv</span>
                    {job.has_certificate && <BadgeCheck size={16} className="text-action" />}
                    <Link
                      to={`/jobs/${job.id}`}
                      className="text-action font-semibold hover:underline"
                    >
                      Open
                    </Link>
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
