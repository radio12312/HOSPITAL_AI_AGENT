import { Activity, AlertOctagon, CheckCircle2, FlaskConical, Play, RotateCcw, Siren, X } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { createEmergency, listEmergencies } from '../api/emergency'
import { listScenarios, resetScenarios, runScenario } from '../api/scenarios'
import { AgentRunView } from '../components/AgentRunView'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DataTable, type Column } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState, InlineAlert } from '../components/ErrorState'
import { Field } from '../components/Field'
import { PageHeader } from '../components/PageHeader'
import { Skeleton } from '../components/Skeleton'
import { useLastUpdated } from '../context/pageMeta'
import { useAsync } from '../hooks/useAsync'
import { useElapsed } from '../hooks/useElapsed'
import type {
  AgentQueryResponse,
  EmergencyCase,
  EmergencyCreateResponse,
  EmergencyListStatus,
  EmergencySeverity,
  ScenarioRunResponse,
  SurgeStatus,
} from '../types'
import { DEPARTMENTS, EMERGENCY_SEVERITIES } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { formatDateTime, formatMinutes, formatNumber, formatRelative, formatValue, humanize } from '../utils/format'
import { inputClass, selectClass } from '../utils/styles'
import { emergencySeverityTone, emergencyStatusTone, priorityTone } from '../utils/tones'

const caseColumns: Column<EmergencyCase>[] = [
  { key: 'id', header: 'Case', render: (c) => <span className="font-mono text-xs">{c.case_id}</span> },
  { key: 'severity', header: 'Severity', render: (c) => <Badge tone={emergencySeverityTone[c.severity]}>{humanize(c.severity)}</Badge> },
  { key: 'department', header: 'Department', render: (c) => c.department },
  {
    key: 'arrival',
    header: 'Arrived',
    render: (c) => (
      <div>
        <p>{formatDateTime(c.arrival_time)}</p>
        <p className="text-xs text-slate-500">{formatRelative(c.arrival_time)}</p>
      </div>
    ),
  },
  { key: 'status', header: 'Status', render: (c) => <Badge tone={emergencyStatusTone[c.status]}>{humanize(c.status)}</Badge> },
  {
    key: 'response',
    header: 'Response time',
    align: 'right',
    render: (c) => (c.response_time === null ? <span className="text-slate-400">Waiting</span> : formatMinutes(c.response_time)),
  },
]

function SurgeBanner({ surge }: { surge: SurgeStatus }) {
  const detected = surge.surge_detected
  return (
    <section
      role={detected ? 'alert' : 'status'}
      aria-label="Surge status"
      className={`flex flex-wrap items-center justify-between gap-4 rounded-xl border p-5 shadow-sm ${
        detected ? 'border-red-300 bg-red-50' : 'border-green-200 bg-green-50'
      }`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`flex h-10 w-10 items-center justify-center rounded-full ${
            detected ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
          }`}
        >
          {detected ? <AlertOctagon size={20} aria-hidden="true" /> : <CheckCircle2 size={20} aria-hidden="true" />}
        </span>
        <div>
          <p className={`text-base font-semibold ${detected ? 'text-red-900' : 'text-green-900'}`}>
            {detected ? 'Surge detected' : 'No surge detected'}
          </p>
          <p className={`text-sm ${detected ? 'text-red-800' : 'text-green-800'}`}>
            {surge.last_hour} arrivals in the last hour vs baseline {formatNumber(surge.baseline_per_hour, 1)}/h
          </p>
        </div>
      </div>
      <dl className="flex gap-6 text-sm">
        <div>
          <dt className="text-slate-600">Active</dt>
          <dd className="text-xl font-semibold tabular-nums text-slate-900">{surge.active_cases}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Critical</dt>
          <dd className={`text-xl font-semibold tabular-nums ${surge.critical_cases > 0 ? 'text-red-700' : 'text-slate-900'}`}>
            {surge.critical_cases}
          </dd>
        </div>
      </dl>
    </section>
  )
}

function EmergencyResponseCard({ result, onDismiss }: { result: EmergencyCreateResponse; onDismiss: () => void }) {
  const [done, setDone] = useState<Set<number>>(new Set())
  const { response } = result
  return (
    <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900">Emergency Response Agent</h3>
          <Badge tone={priorityTone(response.priority_level)}>Priority: {response.priority_level}</Badge>
          {response.surge_detected && <Badge tone="danger">Surge</Badge>}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss emergency response"
          className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Registered {result.cases.map((c) => c.case_id).join(', ') || 'no cases'} · Recommendation #{result.recommendation_id}
      </p>

      <fieldset className="mt-4">
        <legend className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Recommended actions</legend>
        {response.recommended_actions.length === 0 ? (
          <p className="text-sm text-slate-500">No actions recommended.</p>
        ) : (
          <ul className="space-y-2">
            {response.recommended_actions.map((action, i) => (
              <li key={i}>
                <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={done.has(i)}
                    onChange={() =>
                      setDone((prev) => {
                        const next = new Set(prev)
                        if (next.has(i)) next.delete(i)
                        else next.add(i)
                        return next
                      })
                    }
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-teal-700"
                  />
                  <span className={done.has(i) ? 'text-slate-400 line-through' : undefined}>{action}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      <div className="mt-4">
        <p className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Reserved beds</p>
        {response.reserved_beds.length === 0 ? (
          <p className="text-sm text-slate-500">No beds reserved.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {response.reserved_beds.map((b) => (
              <Badge key={b} tone="warning">
                <span className="font-mono">{b}</span>
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function RegisterEmergencyForm({ onRegistered }: { onRegistered: () => void }) {
  const [severity, setSeverity] = useState<EmergencySeverity>('critical')
  const [department, setDepartment] = useState<string>('Emergency')
  const [count, setCount] = useState('1')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EmergencyCreateResponse | null>(null)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const n = Number(count)
    if (!Number.isInteger(n) || n < 1 || n > 50) {
      setError('Count must be a whole number between 1 and 50.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const res = await createEmergency({ severity, department, count: n })
      setResult(res)
      onRegistered()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card title="Register incoming emergency" description="Registers the cases and runs the Emergency Response Agent">
      <form onSubmit={(e) => void handleSubmit(e)} className="grid grid-cols-1 gap-4 sm:grid-cols-4 sm:items-end" noValidate>
        <Field label="Severity" htmlFor="em-severity">
          <select
            id="em-severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as EmergencySeverity)}
            className={selectClass}
          >
            {EMERGENCY_SEVERITIES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Department" htmlFor="em-dept">
          <select id="em-dept" value={department} onChange={(e) => setDepartment(e.target.value)} className={selectClass}>
            {DEPARTMENTS.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </Field>
        <Field label="Patient count" htmlFor="em-count">
          <input
            id="em-count"
            type="number"
            min={1}
            max={50}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Button type="submit" variant="danger" icon={Siren} loading={submitting}>
          Register
        </Button>
      </form>
      {error && (
        <div className="mt-4">
          <InlineAlert message={error} />
        </div>
      )}
      {result && <EmergencyResponseCard key={result.recommendation_id} result={result} onDismiss={() => setResult(null)} />}
    </Card>
  )
}

function ScenarioSimulator({ onStateChanged }: { onStateChanged: () => void }) {
  const fetcher = useCallback(() => listScenarios(), [])
  const scenarios = useAsync(fetcher)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [result, setResult] = useState<ScenarioRunResponse | null>(null)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null)
  const elapsed = useElapsed(runningId !== null)

  async function run(id: string) {
    setRunningId(id)
    setRunError(null)
    setResetMsg(null)
    setResult(null)
    try {
      const res = await runScenario(id)
      setResult(res)
      onStateChanged()
    } catch (err) {
      setRunError(getErrorMessage(err))
    } finally {
      setRunningId(null)
    }
  }

  async function reset() {
    setResetting(true)
    setResetMsg(null)
    try {
      const res = await resetScenarios()
      setResult(null)
      setResetMsg({ tone: 'success', text: `Hospital state restored to baseline (${res.status}).` })
      onStateChanged()
    } catch (err) {
      setResetMsg({ tone: 'danger', text: getErrorMessage(err) })
    } finally {
      setResetting(false)
    }
  }

  const updateRun = (run: AgentQueryResponse) => setResult((prev) => (prev ? { ...prev, agent_run: run } : prev))
  const runningName = scenarios.data?.find((s) => s.id === runningId)?.name

  return (
    <Card
      title="Scenario simulator"
      description="Applies a scenario to the live demo state, then runs the full agent pipeline. Use reset to restore the baseline."
      actions={
        <Button
          variant="secondary"
          size="sm"
          icon={RotateCcw}
          loading={resetting}
          disabled={runningId !== null}
          onClick={() => void reset()}
        >
          Reset to baseline
        </Button>
      }
    >
      {resetMsg && (
        <div className="mb-4">
          <InlineAlert tone={resetMsg.tone} message={resetMsg.text} />
        </div>
      )}

      {scenarios.loading && !scenarios.data ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading scenarios">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="space-y-2 rounded-lg border border-slate-200 p-4">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
      ) : scenarios.error && !scenarios.data ? (
        <ErrorState compact message={scenarios.error} onRetry={() => void scenarios.reload()} />
      ) : !scenarios.data?.length ? (
        <EmptyState compact icon={FlaskConical} title="No scenarios available" />
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {scenarios.data.map((s) => (
            <li
              key={s.id}
              className={`flex flex-col rounded-lg border p-4 ${runningId === s.id ? 'border-teal-700 bg-teal-50/40' : 'border-slate-200'}`}
            >
              <p className="text-sm font-semibold text-slate-900">{s.name}</p>
              <p className="mt-1 flex-1 text-sm text-slate-600">{s.description}</p>
              <Button
                size="sm"
                icon={Play}
                className="mt-3 self-start"
                loading={runningId === s.id}
                disabled={runningId !== null || resetting}
                onClick={() => void run(s.id)}
                aria-label={`Run scenario ${s.name}`}
              >
                {runningId === s.id ? 'Running…' : 'Run'}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {runningId && (
        <div role="status" aria-live="polite" className="mt-5 rounded-lg border border-teal-200 bg-teal-50 p-4">
          <p className="text-sm font-medium text-teal-900">
            Running “{runningName ?? runningId}” — applying changes and running agents… {elapsed}s
          </p>
          <p className="mt-0.5 text-xs text-teal-800">This usually takes 10–30 seconds.</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-teal-100">
            <div
              className="h-full rounded-full bg-teal-700 transition-[width] duration-1000"
              style={{ width: `${Math.min(95, (elapsed / 30) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {runError && (
        <div className="mt-5">
          <InlineAlert message={`Scenario run failed: ${runError}`} />
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-5 border-t border-slate-100 pt-5">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-teal-700" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-slate-900">Result: {result.scenario.name}</h3>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Changes applied</p>
            {Object.keys(result.changes).length === 0 ? (
              <p className="text-sm text-slate-500">No state changes reported.</p>
            ) : (
              <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(result.changes).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
                    <dt className="text-sm text-slate-600">{humanize(key)}</dt>
                    <dd className="text-sm font-semibold tabular-nums text-slate-900">{formatValue(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <div>
            <p className="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Agent run</p>
            <AgentRunView run={result.agent_run} onRunUpdate={updateRun} />
          </div>
        </div>
      )}
    </Card>
  )
}

export function EmergencyPage() {
  const [statusFilter, setStatusFilter] = useState<EmergencyListStatus>('active')
  const fetcher = useCallback(() => listEmergencies({ status: statusFilter, limit: 100 }), [statusFilter])
  const { data, error, loading, refreshing, updatedAt, reload } = useAsync(fetcher)
  useLastUpdated(updatedAt)
  const refresh = useCallback(() => void reload(), [reload])

  return (
    <div className="space-y-6">
      <PageHeader description="Monitor emergency arrivals, register incoming cases and simulate surge scenarios." />

      {loading && !data ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : data ? (
        <SurgeBanner surge={data.surge} />
      ) : null}

      <Card
        title={statusFilter === 'active' ? 'Active cases' : 'All cases'}
        bodyClassName="p-0"
        actions={
          <div className="flex rounded-lg border border-slate-200 p-0.5" role="group" aria-label="Case filter">
            {(['active', 'all'] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={statusFilter === s}
                onClick={() => setStatusFilter(s)}
                className={`cursor-pointer rounded-md px-3 py-1 text-xs font-medium ${
                  statusFilter === s ? 'bg-teal-700 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {humanize(s)}
              </button>
            ))}
          </div>
        }
      >
        <DataTable
          caption="Emergency cases"
          columns={caseColumns}
          rows={data?.items ?? null}
          rowKey={(c) => c.id}
          loading={loading}
          refreshing={refreshing}
          error={error}
          onRetry={refresh}
          emptyIcon={Siren}
          emptyTitle={statusFilter === 'active' ? 'No active emergency cases' : 'No emergency cases recorded'}
        />
        {data && data.total > data.items.length && (
          <p className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
            Showing {data.items.length} of {data.total} cases.
          </p>
        )}
      </Card>

      <RegisterEmergencyForm onRegistered={refresh} />
      <ScenarioSimulator onStateChanged={refresh} />
    </div>
  )
}
