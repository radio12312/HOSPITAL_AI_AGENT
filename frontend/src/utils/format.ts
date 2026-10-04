// Formatting helpers. Backend timestamps are ISO-8601 without offset (treated as local time);
// date-only strings (YYYY-MM-DD) are parsed manually so they are not shifted by UTC parsing.

const EMPTY = '—'

function parseDateOnly(value: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

export function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = parseDateOnly(value) ?? new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDate(value: string | null | undefined): string {
  const d = toDate(value)
  return d ? d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : EMPTY
}

export function formatShortDate(value: string | null | undefined): string {
  const d = toDate(value)
  return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : EMPTY
}

export function formatTime(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : toDate(value)
  return d ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : EMPTY
}

export function formatClock(value: Date): string {
  return value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(value: string | null | undefined): string {
  const d = toDate(value)
  return d
    ? d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : EMPTY
}

/** "12 min ago", "3 h ago" relative to now. */
export function formatRelative(value: string | null | undefined, now: Date = new Date()): string {
  const d = toDate(value)
  if (!d) return EMPTY
  const diffMin = Math.round((now.getTime() - d.getTime()) / 60_000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin} min ago`
  const h = Math.floor(diffMin / 60)
  if (h < 24) return `${h} h ago`
  return `${Math.floor(h / 24)} d ago`
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY
  return `${value.toFixed(digits)}%`
}

export function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY
  const rounded = Math.round(value)
  if (rounded < 60) return `${rounded} min`
  const h = Math.floor(rounded / 60)
  const m = rounded % 60
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

/** Local date as YYYY-MM-DD (not UTC). */
export function todayISO(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** snake_case / identifiers to "Sentence case". */
export function humanize(value: string): string {
  const spaced = value.replace(/_/g, ' ').trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return EMPTY
  if (typeof value === 'number') return formatNumber(value, 2)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}
