import { BedDouble, Cpu, X } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { allocateBeds, listBeds } from '../api/beds'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DataTable, type Column } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState, InlineAlert } from '../components/ErrorState'
import { PageHeader } from '../components/PageHeader'
import { ProgressBar } from '../components/ProgressBar'
import { Skeleton } from '../components/Skeleton'
import { useAuth } from '../context/authContext'
import { useLastUpdated } from '../context/pageMeta'
import { useAsync } from '../hooks/useAsync'
import type { Bed, BedAllocateResponse, BedAssignment, BedStatus } from '../types'
import { BED_STATUSES } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { formatNumber, formatPct, humanize } from '../utils/format'
import { selectClass } from '../utils/styles'
import { bedTileClass, severityScoreTone, utilizationTone } from '../utils/tones'

// The whole bed inventory (~200 beds) fits in one request; filtering happens client-side so
// the ward summary cards always reflect the full hospital.
const BED_LIMIT = 500

const assignmentColumns: Column<BedAssignment>[] = [
  { key: 'patient', header: 'Patient', render: (a) => (
    <div>
      <p className="font-medium text-slate-900">{a.patient_name}</p>
      <p className="font-mono text-xs text-slate-500">{a.patient_id}</p>
    </div>
  ) },
  { key: 'severity', header: 'Severity', render: (a) => <Badge tone={severityScoreTone(a.severity_score)}>{formatNumber(a.severity_score, 1)}</Badge> },
  { key: 'bed', header: 'Assigned bed', render: (a) => <span className="font-mono text-xs">{a.assigned_bed}</span> },
  { key: 'ward', header: 'Ward', render: (a) => a.ward },
]

function bedLabel(bed: Bed): string {
  const parts = [bed.bed_id, humanize(bed.occupancy_status), humanize(bed.bed_type)]
  if (bed.patient_name) parts.push(`${bed.patient_name}${bed.patient_id ? ` (${bed.patient_id})` : ''}`)
  return parts.join(' · ')
}

function shortBedId(bedId: string): string {
  const m = /(\d+)$/.exec(bedId)
  return m ? m[1] : bedId.slice(-3)
}

export function BedsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [ward, setWard] = useState('')
  const [status, setStatus] = useState<BedStatus | ''>('')

  const fetcher = useCallback(() => listBeds({ limit: BED_LIMIT }), [])
  const { data, error, loading, refreshing, updatedAt, reload } = useAsync(fetcher)
  useLastUpdated(updatedAt)

  const [allocating, setAllocating] = useState(false)
  const [allocError, setAllocError] = useState<string | null>(null)
  const [result, setResult] = useState<BedAllocateResponse | null>(null)

  const wards = useMemo(() => data?.summary.map((s) => s.ward) ?? [], [data])

  const groupedBeds = useMemo(() => {
    const filtered = (data?.items ?? []).filter(
      (b) => (!ward || b.ward === ward) && (!status || b.occupancy_status === status),
    )
    const groups = new Map<string, Bed[]>()
    for (const b of filtered) {
      const list = groups.get(b.ward) ?? []
      list.push(b)
      groups.set(b.ward, list)
    }
    return [...groups.entries()]
  }, [data, ward, status])

  async function runOptimizer() {
    setAllocating(true)
    setAllocError(null)
    try {
      const res = await allocateBeds({ patient_ids: null })
      setResult(res)
      void reload()
    } catch (err) {
      setAllocError(getErrorMessage(err))
    } finally {
      setAllocating(false)
    }
  }

  if (error && !data) {
    return (
      <Card>
        <ErrorState message={error} onRetry={() => void reload()} />
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        description={
          isAdmin
            ? 'Live bed status by ward. Run the optimizer to assign beds to admitted patients without one.'
            : 'Live bed status by ward (read-only).'
        }
        actions={
          isAdmin && (
            <Button icon={Cpu} loading={allocating} onClick={() => void runOptimizer()}>
              Run bed optimizer
            </Button>
          )
        }
      />

      {error && data && <InlineAlert message={`Refresh failed: ${error}`} onRetry={() => void reload()} />}
      {allocError && <InlineAlert message={`Bed optimizer failed: ${allocError}`} />}

      {result && (
        <Card
          title="Bed optimizer result"
          description={`Recommendation #${result.recommendation_id}`}
          actions={
            <button
              type="button"
              onClick={() => setResult(null)}
              aria-label="Dismiss optimizer result"
              className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X size={16} aria-hidden="true" />
            </button>
          }
          bodyClassName="p-0"
        >
          <div className="grid grid-cols-2 gap-4 border-b border-slate-100 p-5 sm:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">Utilization score</p>
              <p className="text-xl font-semibold tabular-nums text-slate-900">{formatNumber(result.utilization_score)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Solver status</p>
              <Badge tone={result.solver_status === 'OPTIMAL' ? 'success' : result.solver_status === 'FEASIBLE' ? 'info' : 'warning'}>
                {result.solver_status}
              </Badge>
            </div>
            <div>
              <p className="text-xs text-slate-500">Assigned</p>
              <p className="text-xl font-semibold tabular-nums text-slate-900">{result.assignments.length}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Unassigned</p>
              <p className={`text-xl font-semibold tabular-nums ${result.unassigned.length ? 'text-amber-700' : 'text-slate-900'}`}>
                {result.unassigned.length}
              </p>
            </div>
          </div>
          <DataTable
            caption="Bed assignments"
            columns={assignmentColumns}
            rows={result.assignments}
            rowKey={(a) => `${a.patient_id}-${a.assigned_bed}`}
            emptyTitle="No assignments made"
            emptyDescription="Every admitted patient already has a bed, or no suitable beds were free."
          />
          {result.unassigned.length > 0 && (
            <div className="border-t border-slate-100 p-5">
              <h3 className="mb-2 text-sm font-semibold text-slate-900">Unassigned patients</h3>
              <ul className="space-y-1.5">
                {result.unassigned.map((u) => (
                  <li key={u.patient_id} className="flex flex-wrap gap-2 text-sm">
                    <span className="font-mono text-xs text-slate-900">{u.patient_id}</span>
                    <span className="text-slate-600">— {u.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      <section aria-label="Ward summary" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {loading && !data
          ? Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-16" />
                <Skeleton className="h-2 w-full" />
              </div>
            ))
          : data?.summary.map((s) => (
              <button
                key={s.ward}
                type="button"
                onClick={() => setWard((w) => (w === s.ward ? '' : s.ward))}
                aria-pressed={ward === s.ward}
                className={`cursor-pointer rounded-xl border bg-white p-4 text-left shadow-sm transition-colors hover:border-teal-700 ${
                  ward === s.ward ? 'border-teal-700 ring-1 ring-teal-700' : 'border-slate-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-700">{s.ward}</p>
                  <Badge tone={utilizationTone(s.occupancy_pct)}>{formatPct(s.occupancy_pct)}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  <span className="text-lg font-semibold text-slate-900 tabular-nums">{s.available}</span> available of {s.total}
                </p>
                <div className="mt-3">
                  <ProgressBar value={s.occupancy_pct} tone={utilizationTone(s.occupancy_pct)} label={`${s.ward} occupancy`} />
                </div>
              </button>
            ))}
      </section>

      <Card
        title="Bed map"
        description="Hover a bed for details"
        actions={
          <div className="flex flex-wrap gap-2">
            <label htmlFor="bed-ward" className="sr-only">
              Ward
            </label>
            <select id="bed-ward" value={ward} onChange={(e) => setWard(e.target.value)} className={`${selectClass} w-40`}>
              <option value="">All wards</option>
              {wards.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
            <label htmlFor="bed-status" className="sr-only">
              Status
            </label>
            <select
              id="bed-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as BedStatus | '')}
              className={`${selectClass} w-40`}
            >
              <option value="">All statuses</option>
              {BED_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <ul className="mb-4 flex flex-wrap gap-4 text-xs text-slate-600" aria-label="Legend">
          {BED_STATUSES.map((s) => (
            <li key={s.value} className="flex items-center gap-1.5">
              <span className={`h-3 w-3 rounded-sm ring-1 ${bedTileClass[s.value]}`} aria-hidden="true" />
              {s.label}
            </li>
          ))}
        </ul>

        {loading && !data ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(2.5rem,1fr))] gap-1.5" role="status" aria-label="Loading beds">
            {Array.from({ length: 48 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : groupedBeds.length === 0 ? (
          <EmptyState icon={BedDouble} title="No beds match these filters" description="Try another ward or status." />
        ) : (
          <div className={`space-y-5 transition-opacity ${refreshing ? 'opacity-60' : ''}`}>
            {groupedBeds.map(([wardName, beds]) => (
              <div key={wardName}>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  {wardName} <span className="font-normal normal-case">({beds.length})</span>
                </h3>
                <ul className="grid grid-cols-[repeat(auto-fill,minmax(2.5rem,1fr))] gap-1.5">
                  {beds.map((b) => (
                    <li
                      key={b.id}
                      title={bedLabel(b)}
                      aria-label={bedLabel(b)}
                      className={`flex h-10 items-center justify-center rounded-md text-[11px] font-medium tabular-nums ring-1 ${bedTileClass[b.occupancy_status]}`}
                    >
                      {shortBedId(b.bed_id)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {data && data.total > data.items.length && (
              <p className="text-xs text-slate-500">
                Showing {data.items.length} of {data.total} beds.
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
