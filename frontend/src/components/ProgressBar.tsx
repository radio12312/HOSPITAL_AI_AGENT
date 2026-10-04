import { toneBarClass, type Tone } from '../utils/tones'

interface ProgressBarProps {
  value: number
  max?: number
  tone?: Tone
  label: string
  showValue?: boolean
}

export function ProgressBar({ value, max = 100, tone = 'primary', label, showValue = false }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-2 w-full min-w-16 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={Math.round(value)}
      >
        <div className={`h-full rounded-full ${toneBarClass[tone]}`} style={{ width: `${pct}%` }} />
      </div>
      {showValue && <span className="w-10 text-right text-xs tabular-nums text-slate-600">{Math.round(value)}</span>}
    </div>
  )
}
