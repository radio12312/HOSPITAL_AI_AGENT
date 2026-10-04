import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

/** Accessible collapsible section built on native <details>. */
export function Disclosure({ summary, children, defaultOpen = false }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="group rounded-lg border border-slate-200 bg-slate-50/60" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 [&::-webkit-details-marker]:hidden">
        <ChevronRight size={16} className="transition-transform group-open:rotate-90" aria-hidden="true" />
        {summary}
      </summary>
      <div className="border-t border-slate-200 px-3 py-3">{children}</div>
    </details>
  )
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-md bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}
