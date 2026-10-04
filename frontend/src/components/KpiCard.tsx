import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Skeleton } from './Skeleton'

type Accent = 'primary' | 'danger' | 'warning' | 'info'

interface KpiCardProps {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon: LucideIcon
  accent?: Accent
  loading?: boolean
}

const accentClass: Record<Accent, { icon: string; border: string }> = {
  primary: { icon: 'bg-teal-50 text-teal-700', border: 'border-slate-200' },
  info: { icon: 'bg-sky-50 text-sky-700', border: 'border-slate-200' },
  warning: { icon: 'bg-amber-50 text-amber-700', border: 'border-amber-200' },
  danger: { icon: 'bg-red-50 text-red-600', border: 'border-red-300 ring-1 ring-red-200' },
}

export function KpiCard({ label, value, sub, icon: Icon, accent = 'primary', loading = false }: KpiCardProps) {
  const a = accentClass[accent]
  return (
    <div className={`rounded-xl border bg-white p-5 shadow-sm ${a.border}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${a.icon}`}>
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
      {loading ? (
        <div className="mt-2 space-y-2" role="status" aria-label={`Loading ${label}`}>
          <Skeleton className="h-7 w-20" />
          <Skeleton className="h-3 w-28" />
        </div>
      ) : (
        <>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
          {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
        </>
      )}
    </div>
  )
}
