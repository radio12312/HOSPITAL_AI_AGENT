import { Check, Lightbulb, PencilLine } from 'lucide-react'
import { useState } from 'react'
import { decideRecommendation } from '../api/recommendations'
import type { Recommendation } from '../types'
import { getErrorMessage } from '../utils/errors'
import { formatRelative, humanize } from '../utils/format'
import { inputClass } from '../utils/styles'
import { recommendationStatusTone } from '../utils/tones'
import { Badge } from './Badge'
import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { InlineAlert } from './ErrorState'
import { Field } from './Field'
import { Modal } from './Modal'

interface RecommendationsPanelProps {
  items: Recommendation[]
  canDecide: boolean
  onUpdated: (rec: Recommendation) => void
}

export function RecommendationsPanel({ items, canDecide, onUpdated }: RecommendationsPanelProps) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [overrideTarget, setOverrideTarget] = useState<Recommendation | null>(null)
  const [note, setNote] = useState('')
  const [overrideError, setOverrideError] = useState<string | null>(null)

  async function accept(rec: Recommendation) {
    setBusyId(rec.id)
    setError(null)
    try {
      onUpdated(await decideRecommendation(rec.id, { action: 'accept' }))
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function submitOverride() {
    if (!overrideTarget || !note.trim()) return
    setBusyId(overrideTarget.id)
    setOverrideError(null)
    try {
      onUpdated(await decideRecommendation(overrideTarget.id, { action: 'override', note: note.trim() }))
      setOverrideTarget(null)
      setNote('')
    } catch (err) {
      setOverrideError(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  if (items.length === 0) {
    return (
      <EmptyState
        compact
        icon={Lightbulb}
        title="No recommendations yet"
        description="Agent recommendations appear here after optimizers or the assistant run."
      />
    )
  }

  return (
    <>
      {error && (
        <div className="mb-3">
          <InlineAlert message={error} />
        </div>
      )}
      <ul className="divide-y divide-slate-100">
        {items.map((rec) => (
          <li key={rec.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="primary">{rec.agent}</Badge>
                <Badge tone={recommendationStatusTone[rec.status]}>{humanize(rec.status)}</Badge>
                <span className="text-xs text-slate-400">{formatRelative(rec.created_at)}</span>
              </div>
              <p className="mt-1 text-sm font-medium text-slate-900">{rec.title}</p>
              {rec.override_note && (
                <p className="mt-0.5 text-xs text-slate-500">Override note: {rec.override_note}</p>
              )}
            </div>
            {canDecide && rec.status === 'pending' && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  icon={Check}
                  loading={busyId === rec.id && !overrideTarget}
                  disabled={busyId !== null}
                  onClick={() => void accept(rec)}
                  aria-label={`Accept recommendation: ${rec.title}`}
                >
                  Accept
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  icon={PencilLine}
                  disabled={busyId !== null}
                  onClick={() => {
                    setOverrideTarget(rec)
                    setNote('')
                    setOverrideError(null)
                  }}
                  aria-label={`Override recommendation: ${rec.title}`}
                >
                  Override
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>

      <Modal
        open={overrideTarget !== null}
        title="Override recommendation"
        description={overrideTarget?.title}
        onClose={() => setOverrideTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOverrideTarget(null)}>
              Cancel
            </Button>
            <Button
              loading={busyId !== null}
              disabled={!note.trim()}
              onClick={() => void submitOverride()}
            >
              Save override
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="Reason for override" htmlFor="override-note" hint="Required. Recorded with the decision.">
            <textarea
              id="override-note"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Keep ICU-12 for post-op patient"
              className={inputClass}
            />
          </Field>
          {overrideError && <InlineAlert message={overrideError} />}
        </div>
      </Modal>
    </>
  )
}
