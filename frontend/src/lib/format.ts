// Money arrives from the API as a decimal string ("809556.70") — never a
// float. Keep it a string all the way to the screen.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "809556.70" -> "8,09,556.70" (Indian digit grouping). */
export function groupInr(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  const negative = String(value).trim().startsWith('-')
  const [whole = '0', decimals = '00'] = String(value).replace('-', '').split('.')
  let head = whole
  let out = ''
  if (head.length > 3) {
    out = head.slice(-3)
    head = head.slice(0, -3)
    while (head.length > 2) {
      out = `${head.slice(-2)},${out}`
      head = head.slice(0, -2)
    }
    if (head) out = `${head},${out}`
  } else {
    out = head
  }
  return `${negative ? '-' : ''}${out}.${decimals.padEnd(2, '0').slice(0, 2)}`
}

/** "809556.70" -> "₹8,09,556.70" */
export function rupees(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return `₹${groupInr(value)}`
}

/** 809556.7 -> "₹8.1L", 48144 -> "₹48.1k" — stat tiles only. */
export function compactRupees(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const abs = Math.abs(value)
  if (abs >= 1_00_00_000) return `₹${(value / 1_00_00_000).toFixed(2)}Cr`
  if (abs >= 1_00_000) return `₹${(value / 1_00_000).toFixed(1)}L`
  if (abs >= 1_000) return `₹${(value / 1_000).toFixed(1)}k`
  return `₹${Math.round(value)}`
}

/** "2026-02-12T10:30:00" or "2026-02-12" -> "12 Feb 2026" */
export function shortDate(value: string | null | undefined): string {
  if (!value) return '—'
  const [datePart] = String(value).split('T')
  const [y, m, d] = datePart.split('-').map(Number)
  if (!y || !m || !d) return String(value)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

/** Human gap between an ISO timestamp and now, for timelines. */
export function relativeDays(value: string | null | undefined): string {
  if (!value) return ''
  const then = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(then.getTime())) return ''
  const days = Math.round((Date.now() - then.getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 31) return `${days} days ago`
  const months = Math.round(days / 30)
  return months === 1 ? '1 month ago' : `${months} months ago`
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return ''
  return String(value)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Days until a due date; negative = overdue. */
export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null
  const due = new Date(`${String(value).split('T')[0]}T00:00:00`)
  if (Number.isNaN(due.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86_400_000)
}
