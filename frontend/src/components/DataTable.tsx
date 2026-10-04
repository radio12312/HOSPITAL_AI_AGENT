import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { tableCellClass, tableHeadClass } from '../utils/styles'
import { EmptyState } from './EmptyState'
import { ErrorState, InlineAlert } from './ErrorState'
import { Skeleton } from './Skeleton'

export interface Column<T> {
  key: string
  header: ReactNode
  render: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  className?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[] | null
  rowKey: (row: T) => string | number
  caption: string
  loading?: boolean
  refreshing?: boolean
  error?: string | null
  onRetry?: () => void
  emptyTitle?: string
  emptyDescription?: string
  emptyIcon?: LucideIcon
  skeletonRows?: number
}

const alignClass = { left: 'text-left', right: 'text-right', center: 'text-center' } as const

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  loading = false,
  refreshing = false,
  error,
  onRetry,
  emptyTitle = 'No records found',
  emptyDescription,
  emptyIcon,
  skeletonRows = 6,
}: DataTableProps<T>) {
  if (error && !rows) return <ErrorState message={error} onRetry={onRetry} />

  const showSkeleton = loading && !rows

  return (
    <div>
      {error && rows && (
        <div className="px-4 pt-4">
          <InlineAlert message={`Refresh failed: ${error}`} onRetry={onRetry} />
        </div>
      )}
      <div className={`overflow-x-auto transition-opacity ${refreshing ? 'opacity-60' : ''}`} aria-busy={loading || refreshing}>
        <table className="min-w-full divide-y divide-slate-200">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-slate-50">
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={`${tableHeadClass} ${alignClass[c.align ?? 'left']}`}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {showSkeleton &&
              Array.from({ length: skeletonRows }, (_, i) => (
                <tr key={`sk-${i}`}>
                  {columns.map((c) => (
                    <td key={c.key} className="px-4 py-3">
                      <Skeleton className="h-4 w-full max-w-32" />
                    </td>
                  ))}
                </tr>
              ))}
            {rows?.map((row) => (
              <tr key={rowKey(row)} className="hover:bg-slate-50/70">
                {columns.map((c) => (
                  <td key={c.key} className={`${tableCellClass} ${alignClass[c.align ?? 'left']} ${c.className ?? ''}`}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && rows.length === 0 && (
        <EmptyState title={emptyTitle} description={emptyDescription} icon={emptyIcon} />
      )}
    </div>
  )
}
