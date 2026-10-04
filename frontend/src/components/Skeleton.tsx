import { Loader2 } from 'lucide-react'

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-200 ${className}`} aria-hidden="true" />
}

export function Spinner({ label = 'Loading', size = 20 }: { label?: string; size?: number }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-500">
      <Loader2 size={size} className="animate-spin text-teal-700" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  )
}

const BAR_HEIGHTS = [40, 70, 55, 85, 60, 75, 45, 65]

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div role="status" aria-label="Loading chart" style={{ height }} className="flex items-end gap-3 px-2">
      {BAR_HEIGHTS.map((h, i) => (
        <div key={i} className="flex-1" style={{ height: `${h}%` }}>
          <Skeleton className="h-full w-full" />
        </div>
      ))}
    </div>
  )
}

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  )
}
