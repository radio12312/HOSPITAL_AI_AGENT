import { Check, Clock, UserCheck, X } from 'lucide-react'
import { useId, useState } from 'react'
import { resumeAgent } from '../api/agent'
import { useAuth } from '../context/authContext'
import type { AgentInterrupt, AgentQueryResponse, ResumeAction } from '../types'
import { getErrorMessage } from '../utils/errors'
import { inputClass, labelClass } from '../utils/styles'
import { interruptReasonLabel } from '../utils/tones'
import { Badge } from './Badge'
import { Button } from './Button'
import { Disclosure, JsonBlock } from './Disclosure'
import { InlineAlert } from './ErrorState'
import { ViolationsTable } from './ReviewerSection'

interface HumanReviewPanelProps {
  threadId: string
  interrupt: AgentInterrupt | null
  onResolved: (run: AgentQueryResponse) => void
}

/** Shown when a run pauses with status "needs_human". Admins approve/reject via POST /agent/resume. */
export function HumanReviewPanel({ threadId, interrupt, onResolved }: HumanReviewPanelProps) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const noteId = useId()
  const [note, setNote] = useState('')
  const [pending, setPending] = useState<ResumeAction | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function decide(action: ResumeAction) {
    setPending(action)
    setError(null)
    try {
      const res = await resumeAgent({ thread_id: threadId, action, note: note.trim() })
      onResolved(res)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setPending(null)
    }
  }

  return (
    <section
      aria-label="Human review required"
      className="rounded-lg border-2 border-amber-300 bg-amber-50/60 p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <UserCheck size={18} className="text-amber-700" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-amber-900">Human review required</h3>
        {interrupt && <Badge tone="warning">Reason: {interruptReasonLabel[interrupt.reason] ?? interrupt.reason}</Badge>}
        {interrupt && (
          <Badge tone="neutral">
            {interrupt.revision_count} revision{interrupt.revision_count === 1 ? '' : 's'}
          </Badge>
        )}
      </div>

      {interrupt ? (
        <div className="mt-3 space-y-3">
          {interrupt.summary && <p className="text-sm text-slate-800">{interrupt.summary}</p>}
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Unresolved violations</p>
            <ViolationsTable violations={interrupt.unresolved_violations} caption="Unresolved violations" />
          </div>
          <Disclosure summary="Best outputs so far (JSON)">
            <JsonBlock value={interrupt.best_outputs} />
          </Disclosure>
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-700">The reviewer escalated this run without details.</p>
      )}

      <div className="mt-4 border-t border-amber-200 pt-4">
        {isAdmin ? (
          <div className="space-y-3">
            <div>
              <label htmlFor={noteId} className={labelClass}>
                Decision note (optional)
              </label>
              <textarea
                id={noteId}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Divert to County General"
                className={inputClass}
                disabled={pending !== null}
              />
            </div>
            {error && <InlineAlert message={error} />}
            <div className="flex flex-wrap gap-2">
              <Button icon={Check} loading={pending === 'approve'} disabled={pending !== null} onClick={() => void decide('approve')}>
                Approve
              </Button>
              <Button
                variant="secondary"
                icon={X}
                loading={pending === 'reject'}
                disabled={pending !== null}
                onClick={() => void decide('reject')}
              >
                Reject
              </Button>
            </div>
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-amber-900">
            <Clock size={16} aria-hidden="true" />
            Waiting for an administrator to approve or reject this run.
          </p>
        )}
      </div>
    </section>
  )
}
