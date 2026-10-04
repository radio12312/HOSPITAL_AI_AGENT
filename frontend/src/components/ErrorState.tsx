import { AlertTriangle, RotateCw } from 'lucide-react'
import { Button } from './Button'

interface ErrorStateProps {
  message: string
  title?: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorState({ message, title = 'Could not load data', onRetry, compact = false }: ErrorStateProps) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6' : 'py-12'}`}>
      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-50 text-red-600">
        <AlertTriangle size={20} aria-hidden="true" />
      </span>
      <p className="text-sm font-medium text-slate-900">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" icon={RotateCw} className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

/** Thin inline banner for errors that happen while stale data is still shown, or form errors. */
export function InlineAlert({
  message,
  tone = 'danger',
  onRetry,
}: {
  message: string
  tone?: 'danger' | 'success' | 'info'
  onRetry?: () => void
}) {
  const cls = {
    danger: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-green-200 bg-green-50 text-green-800',
    info: 'border-sky-200 bg-sky-50 text-sky-800',
  }[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${cls}`}
    >
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="cursor-pointer text-sm font-medium underline underline-offset-2 hover:no-underline"
        >
          Retry
        </button>
      )}
    </div>
  )
}
