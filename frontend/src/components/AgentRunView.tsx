import { Ban } from 'lucide-react'
import type { AgentQueryResponse } from '../types'
import { formatValue, humanize } from '../utils/format'
import { runStatusTone } from '../utils/tones'
import { Badge } from './Badge'
import { Disclosure, JsonBlock } from './Disclosure'
import { FormattedText } from './FormattedText'
import { HumanReviewPanel } from './HumanReviewPanel'
import { ReviewerSection } from './ReviewerSection'

const STATUS_LABEL: Record<AgentQueryResponse['status'], string> = {
  completed: 'Completed',
  needs_human: 'Needs human review',
  rejected: 'Rejected',
}

interface AgentRunViewProps {
  run: AgentQueryResponse
  /** Called with the POST /agent/resume response so the caller can replace the run. */
  onRunUpdate: (run: AgentQueryResponse) => void
}

/** Shared renderer for AgentQueryResponse (AI Assistant + scenario simulator). */
export function AgentRunView({ run, onRunUpdate }: AgentRunViewProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {run.status && <Badge tone={runStatusTone[run.status] ?? 'neutral'}>{STATUS_LABEL[run.status] ?? run.status}</Badge>}
        {run.agents_used.length > 0 && <span className="text-xs text-slate-500">Agents:</span>}
        {run.agents_used.map((a) => (
          <Badge key={a} tone="primary">
            {a}
          </Badge>
        ))}
      </div>

      {run.status === 'rejected' && (
        <div className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4" role="status">
          <Ban size={18} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-slate-800">Run rejected by administrator</p>
            <p className="mt-0.5 text-sm text-slate-600">No recommendations from this run were applied.</p>
          </div>
        </div>
      )}

      {run.status === 'needs_human' ? (
        <HumanReviewPanel threadId={run.thread_id} interrupt={run.interrupt} onResolved={onRunUpdate} />
      ) : (
        run.answer && <FormattedText text={run.answer} />
      )}

      {run.status === 'completed' && !run.answer && (
        <p className="text-sm text-slate-500">The agents returned no answer text.</p>
      )}

      {run.review && <ReviewerSection review={run.review} />}

      <Disclosure summary="How this answer was produced">
        {run.trace.length > 0 ? (
          <ol className="space-y-2">
            {run.trace.map((step, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-medium text-teal-800">
                  {i + 1}
                </span>
                <span>
                  <span className="font-medium text-slate-900">{humanize(step.agent)}</span>
                  <span className="text-slate-400"> — </span>
                  <span className="text-slate-700">{step.summary}</span>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-slate-500">No trace steps recorded.</p>
        )}
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 border-t border-slate-200 pt-3 text-xs text-slate-600 sm:grid-cols-3">
          <div>
            <dt className="inline font-medium text-slate-700">LLM calls: </dt>
            <dd className="inline tabular-nums">{formatValue(run.llm_calls)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="inline font-medium text-slate-700">Model: </dt>
            <dd className="inline break-all">{formatValue(run.model)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="inline font-medium text-slate-700">Thread: </dt>
            <dd className="inline break-all font-mono">{formatValue(run.thread_id)}</dd>
          </div>
        </dl>
      </Disclosure>

      <Disclosure summary="Raw agent outputs (JSON)">
        <JsonBlock value={run.outputs} />
      </Disclosure>
    </div>
  )
}
