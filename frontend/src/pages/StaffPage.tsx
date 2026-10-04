import { ArrowRight, CheckCircle2, Scale, UsersRound, X } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { listStaff, rebalanceStaff } from '../api/staff'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DataTable, type Column } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState, InlineAlert } from '../components/ErrorState'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { ProgressBar } from '../components/ProgressBar'
import { ChartSkeleton } from '../components/Skeleton'
import { useLastUpdated } from '../context/pageMeta'
import { useAsync } from '../hooks/useAsync'
import type { Shift, StaffDepartmentSummary, StaffMember, StaffRebalanceResponse } from '../types'
import { PAGE_SIZE, SHIFTS } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { formatNumber, humanize } from '../utils/format'
import { chartColors, selectClass } from '../utils/styles'
import { utilizationTone } from '../utils/tones'

// ~100 staff: load everything once so the department summary is always hospital-wide,
// and filter / paginate client-side.
const STAFF_LIMIT = 500
const axisTick = { fontSize: 12, fill: '#64748b' }

const staffColumns: Column<StaffMember>[] = [
  { key: 'id', header: 'Staff ID', render: (s) => <span className="font-mono text-xs">{s.staff_id}</span> },
  { key: 'name', header: 'Name', render: (s) => <span className="font-medium text-slate-900">{s.name}</span> },
  { key: 'role', header: 'Role', render: (s) => s.role },
  { key: 'department', header: 'Department', render: (s) => s.department },
  { key: 'shift', header: 'Shift', render: (s) => humanize(s.shift) },
  {
    key: 'duty',
    header: 'On duty',
    render: (s) => <Badge tone={s.on_duty ? 'success' : 'neutral'}>{s.on_duty ? 'On duty' : 'Off duty'}</Badge>,
  },
  {
    key: 'workload',
    header: 'Workload',
    className: 'min-w-40',
    render: (s) => (
      <ProgressBar value={s.workload_score} tone={utilizationTone(s.workload_score)} label={`${s.name} workload`} showValue />
    ),
  },
]

const summaryColumns: Column<StaffDepartmentSummary>[] = [
  { key: 'department', header: 'Department', render: (d) => <span className="font-medium text-slate-900">{d.department}</span> },
  { key: 'on_duty', header: 'On duty / total', align: 'right', render: (d) => `${d.on_duty} / ${d.total}` },
  { key: 'patients', header: 'Patients', align: 'right', render: (d) => d.patient_load },
  {
    key: 'ratio',
    header: 'Load ratio',
    align: 'right',
    render: (d) => <span className="tabular-nums">{formatNumber(d.load_ratio, 1)}</span>,
  },
  { key: 'workload', header: 'Avg workload', align: 'right', render: (d) => formatNumber(d.avg_workload, 1) },
]

export function StaffPage() {
  const fetcher = useCallback(() => listStaff({ limit: STAFF_LIMIT }), [])
  const { data, error, loading, refreshing, updatedAt, reload } = useAsync(fetcher)
  useLastUpdated(updatedAt)

  const [department, setDepartment] = useState('')
  const [shift, setShift] = useState<Shift | ''>('')
  const [offset, setOffset] = useState(0)

  const [proposal, setProposal] = useState<StaffRebalanceResponse | null>(null)
  const [busy, setBusy] = useState<'preview' | 'apply' | null>(null)
  const [rebalanceError, setRebalanceError] = useState<string | null>(null)

  const departments = useMemo(() => data?.summary.map((s) => s.department) ?? [], [data])

  const filteredStaff = useMemo(
    () =>
      (data?.items ?? []).filter((s) => (!department || s.department === department) && (!shift || s.shift === shift)),
    [data, department, shift],
  )
  const pageRows = data ? filteredStaff.slice(offset, offset + PAGE_SIZE) : null

  const comparison = useMemo(() => {
    if (!proposal) return []
    const after = new Map(proposal.after.map((a) => [a.department, a.load_ratio]))
    const depts = new Set([...proposal.before.map((b) => b.department), ...after.keys()])
    const before = new Map(proposal.before.map((b) => [b.department, b.load_ratio]))
    return [...depts].map((d) => ({ department: d, before: before.get(d) ?? null, after: after.get(d) ?? null }))
  }, [proposal])

  async function rebalance(apply: boolean) {
    setBusy(apply ? 'apply' : 'preview')
    setRebalanceError(null)
    try {
      const res = await rebalanceStaff({ apply })
      setProposal(res)
      if (apply) void reload()
    } catch (err) {
      setRebalanceError(getErrorMessage(err))
    } finally {
      setBusy(null)
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
        description="Staff workloads by department and shift. Rebalance to propose moves from low- to high-load departments."
        actions={
          <Button icon={Scale} loading={busy === 'preview'} disabled={busy !== null} onClick={() => void rebalance(false)}>
            Rebalance staff
          </Button>
        }
      />

      {error && data && <InlineAlert message={`Refresh failed: ${error}`} onRetry={() => void reload()} />}
      {rebalanceError && <InlineAlert message={`Rebalance failed: ${rebalanceError}`} />}

      {proposal && (
        <Card
          title={proposal.applied ? 'Staff changes applied' : 'Proposed staff reallocation'}
          description={`Solver: ${proposal.solver_status} · Recommendation #${proposal.recommendation_id}`}
          actions={
            <>
              {!proposal.applied && proposal.staff_reallocation.length > 0 && (
                <Button icon={CheckCircle2} loading={busy === 'apply'} disabled={busy !== null} onClick={() => void rebalance(true)}>
                  Apply changes
                </Button>
              )}
              <button
                type="button"
                onClick={() => setProposal(null)}
                aria-label="Dismiss rebalance proposal"
                className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </>
          }
        >
          {proposal.applied && (
            <div className="mb-4">
              <InlineAlert tone="success" message="The moves below were written to the roster. Staff data has been refreshed." />
            </div>
          )}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Moves</h3>
              {proposal.staff_reallocation.length === 0 ? (
                <EmptyState compact icon={Scale} title="No moves needed" description="Department loads are already balanced." />
              ) : (
                <ul className="space-y-3">
                  {proposal.staff_reallocation.map((m, i) => (
                    <li key={`${m.from}-${m.to}-${i}`} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="font-medium text-slate-900">{m.from}</span>
                        <ArrowRight size={14} className="text-slate-400" aria-label="to" />
                        <span className="font-medium text-slate-900">{m.to}</span>
                        <Badge tone="primary">
                          {m.staff_count} staff
                        </Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {m.staff_ids.map((id) => (
                          <span key={id} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
                            {id}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="mb-3 text-sm font-semibold text-slate-900">Load ratio before vs after</h3>
              {comparison.length === 0 ? (
                <EmptyState compact title="No load data returned" />
              ) : (
                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={comparison} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                      <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="department" tick={axisTick} interval={0} angle={-25} textAnchor="end" height={60} />
                      <YAxis tick={axisTick} />
                      <Tooltip formatter={(v) => formatNumber(Number(v), 2)} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="before" name="Before" fill={chartColors.neutral} radius={[4, 4, 0, 0]} />
                      <Bar dataKey="after" name="After" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Department load" description="Load ratio = patients per on-duty staff member">
          {loading && !data ? (
            <ChartSkeleton />
          ) : !data?.summary.length ? (
            <EmptyState compact title="No department data" />
          ) : (
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.summary} margin={{ top: 8, right: 0, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="department" tick={axisTick} interval={0} angle={-25} textAnchor="end" height={60} />
                  <YAxis yAxisId="ratio" tick={axisTick} />
                  <YAxis yAxisId="workload" orientation="right" domain={[0, 100]} tick={axisTick} />
                  <Tooltip formatter={(v) => formatNumber(Number(v), 1)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="ratio" dataKey="load_ratio" name="Load ratio" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="workload" dataKey="avg_workload" name="Avg workload" fill={chartColors.amber} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
        <Card title="Department summary" bodyClassName="p-0">
          <DataTable
            caption="Department staffing summary"
            columns={summaryColumns}
            rows={data?.summary ?? null}
            rowKey={(d) => d.department}
            loading={loading}
            refreshing={refreshing}
            skeletonRows={5}
            emptyTitle="No department data"
          />
        </Card>
      </div>

      <Card bodyClassName="p-0">
        <div className="grid grid-cols-1 gap-3 border-b border-slate-100 p-4 sm:grid-cols-3">
          <div>
            <label htmlFor="staff-dept" className="sr-only">
              Department
            </label>
            <select
              id="staff-dept"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value)
                setOffset(0)
              }}
              className={selectClass}
            >
              <option value="">All departments</option>
              {departments.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="staff-shift" className="sr-only">
              Shift
            </label>
            <select
              id="staff-shift"
              value={shift}
              onChange={(e) => {
                setShift(e.target.value as Shift | '')
                setOffset(0)
              }}
              className={selectClass}
            >
              <option value="">All shifts</option>
              {SHIFTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <DataTable
          caption="Staff members"
          columns={staffColumns}
          rows={pageRows}
          rowKey={(s) => s.id}
          loading={loading}
          refreshing={refreshing}
          emptyIcon={UsersRound}
          emptyTitle="No staff match these filters"
        />
        {data && <Pagination total={filteredStaff.length} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}
      </Card>
    </div>
  )
}
