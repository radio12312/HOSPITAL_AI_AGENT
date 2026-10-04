import { ShieldCheck } from 'lucide-react'
import type { AgentReview, ReviewViolation } from '../types'
import { humanize } from '../utils/format'
import { tableCellClass, tableHeadClass } from '../utils/styles'
import { verdictTone } from '../utils/tones'
import { Badge } from './Badge'

export function ViolationsTable({ violations, caption }: { violations: ReviewViolation[]; caption: string }) {
  if (violations.length === 0) return <p className="text-sm text-slate-500">No violations.</p>
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-slate-50">
          <tr>
            <th scope="col" className={tableHeadClass}>Agent</th>
            <th scope="col" className={tableHeadClass}>Rule</th>
            <th scope="col" className={tableHeadClass}>Detail</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {violations.map((v, i) => (
            <tr key={`${v.agent}-${v.rule}-${i}`}>
              <td className={tableCellClass}>
                <Badge tone="primary">{v.agent}</Badge>
              </td>
              <td className={`${tableCellClass} font-mono text-xs`}>{v.rule}</td>
              <td className="px-4 py-3 text-sm text-slate-700">{v.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Reviewer outcome: final verdict, revision count and the per-attempt timeline. */
export function ReviewerSection({ review }: { review: AgentReview }) {
  const history = [...review.history].sort((a, b) => a.attempt - b.attempt)
  return (
    <section aria-label="Reviewer" className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldCheck size={16} className="text-teal-700" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-slate-900">Reviewer</h3>
        <Badge tone={verdictTone(review.verdict)}>Verdict: {humanize(review.verdict)}</Badge>
        <Badge tone="neutral">
          {review.revision_count} revision{review.revision_count === 1 ? '' : 's'}
        </Badge>
      </div>

      {review.violations.length > 0 && (
        <div className="mt-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Current violations</p>
          <ViolationsTable violations={review.violations} caption="Current reviewer violations" />
        </div>
      )}

      {history.length > 0 ? (
        <ol className="mt-4 space-y-4 border-l-2 border-slate-200 pl-4" aria-label="Review attempts">
          {history.map((h) => (
            <li key={h.attempt} className="relative">
              <span
                className={`absolute top-1 -left-[23px] h-3 w-3 rounded-full ring-2 ring-white ${
                  h.verdict === 'approve' ? 'bg-green-500' : 'bg-amber-500'
                }`}
                aria-hidden="true"
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-900">Attempt #{h.attempt}</span>
                <Badge tone={verdictTone(h.verdict)}>{humanize(h.verdict)}</Badge>
              </div>
              {h.violations.length > 0 && (
                <ul className="mt-1.5 space-y-1 text-sm text-slate-700">
                  {h.violations.map((v, i) => (
                    <li key={i}>
                      <span className="font-medium">{v.agent}</span>
                      <span className="text-slate-400"> · </span>
                      <span className="font-mono text-xs">{v.rule}</span>
                      <span className="text-slate-400"> — </span>
                      {v.detail}
                    </li>
                  ))}
                </ul>
              )}
              {h.feedback && (
                <p className="mt-1.5 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  <span className="font-medium text-slate-700">Feedback: </span>
                  {h.feedback}
                </p>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No review attempts recorded.</p>
      )}
    </section>
  )
}
