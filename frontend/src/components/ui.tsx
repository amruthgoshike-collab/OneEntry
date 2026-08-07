// Primitives in the mockup's visual language: flat, ruled, no shadows.
import type { LucideIcon } from 'lucide-react'
import { AlertCircle, FileDown, X } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { motion } from 'framer-motion'
import { api } from '../lib/api'

type ButtonVariant = 'primary' | 'secondary' | 'quiet'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  icon?: LucideIcon
  children?: ReactNode
}

export function Button({ variant = 'secondary', icon: IconCmp, children, className = '', ...props }: ButtonProps) {
  const base =
    'text-body-md font-semibold py-2 px-4 rounded inline-flex items-center justify-center gap-2 ' +
    'transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
  const variants: Record<ButtonVariant, string> = {
    primary: 'bg-action text-white hover:bg-action-hover',
    secondary: 'bg-transparent rule-all text-ink hover:bg-white',
    quiet: 'bg-transparent text-ink-muted hover:text-ink underline',
  }
  return (
    <motion.div whileTap={{ scale: 0.98 }} className="inline-flex">
      <button className={`${base} ${variants[variant]} ${className}`} {...props}>
        {IconCmp && <IconCmp size={16} strokeWidth={2.25} />}
        {children}
      </button>
    </motion.div>
  )
}

/** Status chips. Tone maps to the paper-stock colours. */
export type Tone = 'neutral' | 'info' | 'attention' | 'done' | 'overdue'

const TONES: Record<Tone, string> = {
  neutral: 'bg-[#F4F3F1] text-ink-muted',
  info: 'bg-carbon text-ink',
  attention: 'bg-manila text-ink',
  done: 'bg-ledger text-ink',
  overdue: 'bg-duplicate text-ink',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`${TONES[tone]} px-2 py-0.5 rounded text-label-caps lowercase whitespace-nowrap`}>
      {children}
    </span>
  )
}

const JOB_TONES: Record<string, Tone> = {
  enquiry: 'neutral',
  quoted: 'info',
  approved: 'attention',
  in_progress: 'attention',
  completed: 'done',
}
const DOC_TONES: Record<string, Tone> = {
  draft: 'neutral',
  approved: 'done',
  unpaid: 'overdue',
  paid: 'done',
  issued: 'done',
  uploaded: 'neutral',
  extracted: 'done',
  failed: 'overdue',
}

export const jobTone = (status: string): Tone => JOB_TONES[status] ?? 'neutral'
export const docTone = (status: string): Tone => DOC_TONES[status] ?? 'neutral'

/** A ruled section with a small caps heading. */
export function Section({
  title,
  count,
  action,
  children,
}: {
  title: string
  count?: number
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-label-caps text-ink-muted m-0">
          {title}
          {count !== undefined && <span className="ml-2 opacity-70">{count}</span>}
        </h2>
        {action}
      </div>
      <div className="rule-t">{children}</div>
    </section>
  )
}

/** A record row with the coloured provenance spine. */
export function RecordRow({
  stripe = '#DCE8F0',
  children,
  className = '',
}: {
  stripe?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`relative pl-6 py-4 rule-b flex flex-col sm:flex-row sm:items-center justify-between gap-4 row-hover ${className}`}
    >
      <div className="provenance-strip" style={{ backgroundColor: stripe }} />
      {children}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-4 pl-6 rule-b text-body-md text-ink-muted">{children}</div>
}

export function ErrorNote({ error, onDismiss }: { error: string | null; onDismiss?: () => void }) {
  if (!error) return null
  return (
    <div className="rule-all bg-duplicate/40 p-4 mb-6 flex items-start gap-3">
      <AlertCircle size={18} className="text-[#ba1a1a] mt-0.5 shrink-0" />
      <div className="flex-1">
        <div className="text-label-caps text-ink mb-1">Something went wrong</div>
        <div className="text-body-md text-ink">{error}</div>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} className="text-ink-muted hover:text-ink" aria-label="Dismiss">
          <X size={16} />
        </button>
      )}
    </div>
  )
}

/** Indeterminate bar for the 5-15s AI calls. */
export function Working({ label }: { label: string }) {
  return (
    <div className="mb-6">
      <div className="working-rule mb-2" />
      <div className="text-body-md text-ink-muted">{label}</div>
    </div>
  )
}

/** Skeleton list rows while data loads. */
export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div className="rule-t" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="relative pl-6 py-4 rule-b flex items-center justify-between gap-4">
          <div className="provenance-strip" style={{ backgroundColor: '#EFEEEB' }} />
          <div className="flex gap-4 flex-1 items-center">
            <div className="skeleton w-5 h-5" />
            <div className="flex-1">
              <div className="skeleton h-4 mb-2" style={{ width: `${55 - i * 7}%` }} />
              <div className="skeleton h-3" style={{ width: `${35 - i * 4}%` }} />
            </div>
          </div>
          <div className="skeleton h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

/** Dashboard stat tile. */
export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: string
}) {
  return (
    <div className="rule-all p-4 bg-white relative overflow-hidden">
      {tone && <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: tone }} />}
      <div className="text-label-caps text-ink-muted mb-1">{label}</div>
      <div className="text-currency-lg text-ink">{value}</div>
      {hint && <div className="text-body-md text-ink-muted mt-1">{hint}</div>}
    </div>
  )
}

/** PDF link that resolves the API-relative pdf_url. */
export function PdfLink({ url, children = 'PDF' }: { url: string | null; children?: ReactNode }) {
  const href = api.fileUrl(url)
  if (!href) return <span className="text-body-md text-ink-muted">PDF pending</span>
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-body-md text-action font-semibold inline-flex items-center gap-1 hover:underline"
    >
      <FileDown size={16} />
      {children}
    </a>
  )
}
