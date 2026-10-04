import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './Button'

interface PaginationProps {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}

export function Pagination({ total, limit, offset, onChange }: PaginationProps) {
  if (total <= 0) return null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-600"
    >
      <p>
        Showing <span className="font-medium text-slate-900">{from}</span>–
        <span className="font-medium text-slate-900">{to}</span> of{' '}
        <span className="font-medium text-slate-900">{total}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={ChevronLeft}
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={offset === 0}
          aria-label="Previous page"
        >
          Prev
        </Button>
        <span className="tabular-nums">
          Page {page} / {pages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onChange(offset + limit)}
          disabled={to >= total}
          aria-label="Next page"
        >
          Next
          <ChevronRight size={14} aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}
