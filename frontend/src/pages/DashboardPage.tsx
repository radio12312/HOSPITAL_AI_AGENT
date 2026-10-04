import {
  Activity,
  BedDouble,
  Clock,
  Gauge,
  RotateCw,
  Siren,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import { useCallback, useMemo, type ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getDashboard } from '../api/dashboard'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState, InlineAlert } from '../components/ErrorState'
import { KpiCard } from '../components/KpiCard'
import { PageHeader } from '../components/PageHeader'
import { RecommendationsPanel } from '../components/RecommendationsPanel'
import { ChartSkeleton, ListSkeleton } from '../components/Skeleton'
import { useAuth } from '../context/authContext'
import { useLastUpdated } from '../context/pageMeta'
import { useAsync } from '../hooks/useAsync'
import type { DashboardResponse, Recommendation } from '../types'
import { DASHBOARD_POLL_MS } from '../utils/constants'
import { formatMinutes, formatNumber, formatPct, formatRelative, formatShortDate, humanize } from '../utils/format'
import { chartColors } from '../utils/styles'
import { emergencySeverityTone, emergencyStatusTone } from '../utils/tones'

const CHART_HEIGHT = 260
const axisTick = { fontSize: 12, fill: '#64748b' }

function ChartCard({
  title,
  description,
  loading,
  isEmpty,
  className = '',
  children,
}: {
  title: string
  description?: string
  loading: boolean
  isEmpty: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <Card title={title} description={description} className={className}>
      {loading ? (
        <ChartSkeleton height={CHART_HEIGHT} />
      ) : isEmpty ? (
        <EmptyState compact title="No data available" />
      ) : (
        <div style={{ height: CHART_HEIGHT }}>{children}</div>
      )}
    </Card>
  )
}

function utilColor(pct: number): string {
  if (pct >= 90) return chartColors.red
  if (pct >= 75) return chartColors.amber
  return chartColors.primary
}

export function DashboardPage() {
  const { user } = useAuth()
  const fetcher = useCallback(() => getDashboard(), [])
  const { data, error, loading, refreshing, updatedAt, reload, setData } = useAsync<DashboardResponse>(fetcher, {
    pollMs: DASHBOARD_POLL_MS,
  })
  useLastUpdated(updatedAt)

  const admissionsSeries = useMemo(() => {
    if (!data) return []
    const rows: { date: string; admissions: number | null; forecast: number | null }[] = data.admissions_trend.map(
      (p) => ({ date: p.date, admissions: p.admissions, forecast: null }),
    )
    // Join the forecast line to the last actual point so the two series connect.
    if (rows.length > 0 && data.demand_forecast.length > 0) {
      const last = rows[rows.length - 1]
      last.forecast = last.admissions
    }
    for (const f of data.demand_forecast) {
      rows.push({ date: f.date, admissions: null, forecast: Math.round(f.expected_admissions * 10) / 10 })
    }
    return rows
  }, [data])

  const updateRecommendation = useCallback(
    (rec: Recommendation) =>
      setData((prev) =>
        prev
          ? {
              ...prev,
              recent_recommendations: prev.recent_recommendations.map((r) => (r.id === rec.id ? rec : r)),
            }
          : prev,
      ),
    [setData],
  )

  if (error && !data) {
    return (
      <Card>
        <ErrorState message={error} onRetry={() => void reload()} />
      </Card>
    )
  }

  const k = data?.kpis
  const showSkeleton = loading && !data

  return (
    <div className="space-y-6">
      <PageHeader
        description="Live hospital operations overview. Refreshes automatically every 30 seconds."
        actions={
          <Button
            variant="secondary"
            icon={RotateCw}
            loading={refreshing}
            onClick={() => void reload()}
            aria-label="Refresh dashboard"
          >
            Refresh
          </Button>
        }
      />

      {error && data && <InlineAlert message={`Auto-refresh failed: ${error}`} onRetry={() => void reload()} />}

      <section aria-label="Key performance indicators" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Admissions Today"
          icon={UserPlus}
          loading={showSkeleton}
          value={formatNumber(k?.admissions_today)}
          sub="New admissions since midnight"
        />
        <KpiCard
          label="Bed Occupancy"
          icon={BedDouble}
          loading={showSkeleton}
          accent={k && k.bed_occupancy_pct >= 90 ? 'warning' : 'primary'}
          value={formatPct(k?.bed_occupancy_pct)}
          sub={`ICU ${formatPct(k?.icu_occupancy_pct)}`}
        />
        <KpiCard
          label="Staff Availability"
          icon={UsersRound}
          loading={showSkeleton}
          accent="info"
          value={k ? `${formatNumber(k.staff_on_duty)} / ${formatNumber(k.staff_total)}` : '—'}
          sub="On duty / total staff"
        />
        <KpiCard
          label="Emergency Alerts"
          icon={Siren}
          loading={showSkeleton}
          accent={k && k.critical_emergencies > 0 ? 'danger' : 'primary'}
          value={formatNumber(k?.active_emergencies)}
          sub={
            <span className={k && k.critical_emergencies > 0 ? 'font-medium text-red-600' : undefined}>
              {formatNumber(k?.critical_emergencies)} critical
            </span>
          }
        />
        <KpiCard
          label="Predicted Wait Time"
          icon={Clock}
          loading={showSkeleton}
          value={formatMinutes(k?.avg_predicted_wait_min)}
          sub="Average across departments"
        />
        <KpiCard
          label="Resource Utilization"
          icon={Gauge}
          loading={showSkeleton}
          accent={k && k.resource_utilization_pct >= 90 ? 'warning' : 'primary'}
          value={formatPct(k?.resource_utilization_pct)}
          sub="Beds, equipment and staff combined"
        />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard
          title="Admissions"
          description="Last 14 days and 7-day forecast (dashed)"
          loading={showSkeleton}
          isEmpty={admissionsSeries.length === 0}
          className="lg:col-span-2"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={admissionsSeries} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d: string) => formatShortDate(d)} tick={axisTick} minTickGap={16} />
              <YAxis tick={axisTick} allowDecimals={false} />
              <Tooltip labelFormatter={(d) => formatShortDate(String(d))} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="admissions"
                name="Admissions"
                stroke={chartColors.primary}
                strokeWidth={2}
                dot={{ r: 2 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="forecast"
                name="Forecast"
                stroke={chartColors.sky}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={{ r: 2 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Occupancy by ward"
          description="Occupied vs available beds"
          loading={showSkeleton}
          isEmpty={!data?.occupancy_by_ward.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data?.occupancy_by_ward ?? []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="ward" tick={axisTick} interval={0} />
              <YAxis tick={axisTick} allowDecimals={false} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="occupied" name="Occupied" stackId="beds" fill={chartColors.primary} />
              <Bar dataKey="available" name="Available" stackId="beds" fill={chartColors.neutral} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Predicted wait by department"
          description="Minutes"
          loading={showSkeleton}
          isEmpty={!data?.wait_time_by_department.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data?.wait_time_by_department ?? []}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
            >
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={axisTick} />
              <YAxis type="category" dataKey="department" tick={axisTick} width={120} />
              <Tooltip formatter={(v) => formatMinutes(Number(v))} />
              <Bar dataKey="predicted_wait_min" name="Predicted wait" fill={chartColors.sky} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Staff on duty by department"
          description="Bars: on duty · line: average workload (0–100)"
          loading={showSkeleton}
          isEmpty={!data?.staff_by_department.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data?.staff_by_department ?? []} margin={{ top: 8, right: 0, left: -16, bottom: 0 }}>
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="department" tick={axisTick} interval={0} angle={-25} textAnchor="end" height={60} />
              <YAxis yAxisId="staff" tick={axisTick} allowDecimals={false} />
              <YAxis yAxisId="load" orientation="right" domain={[0, 100]} tick={axisTick} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar yAxisId="staff" dataKey="on_duty" name="On duty" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
              <Line
                yAxisId="load"
                type="monotone"
                dataKey="avg_workload"
                name="Avg workload"
                stroke={chartColors.amber}
                strokeWidth={2}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Equipment utilization"
          description="% in use by equipment type"
          loading={showSkeleton}
          isEmpty={!data?.equipment_utilization.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data?.equipment_utilization ?? []} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="type" tick={axisTick} interval={0} />
              <YAxis tick={axisTick} domain={[0, 100]} />
              <Tooltip formatter={(v) => formatPct(Number(v))} />
              <Bar dataKey="utilization_pct" name="Utilization" radius={[4, 4, 0, 0]}>
                {(data?.equipment_utilization ?? []).map((e) => (
                  <Cell key={e.type} fill={utilColor(e.utilization_pct)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Emergency alerts" description="Active emergency cases">
          {showSkeleton ? (
            <ListSkeleton />
          ) : !data?.emergency_alerts.length ? (
            <EmptyState compact icon={Activity} title="No active alerts" description="All emergency cases are handled." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.emergency_alerts.map((a) => (
                <li key={a.case_id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex min-w-0 items-center gap-3">
                    <Badge tone={emergencySeverityTone[a.severity]}>{humanize(a.severity)}</Badge>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {a.case_id} · {a.department}
                      </p>
                      <p className="text-xs text-slate-500">Arrived {formatRelative(a.arrival_time)}</p>
                    </div>
                  </div>
                  <Badge tone={emergencyStatusTone[a.status]}>{humanize(a.status)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Recent recommendations"
          description={user?.role === 'admin' ? 'Accept or override pending agent recommendations' : 'Latest agent recommendations'}
        >
          {showSkeleton ? (
            <ListSkeleton />
          ) : (
            <RecommendationsPanel
              items={data?.recent_recommendations ?? []}
              canDecide={user?.role === 'admin'}
              onUpdated={updateRecommendation}
            />
          )}
        </Card>
      </div>
    </div>
  )
}
