import type { ReactNode } from 'react'

interface PageHeaderProps {
  description?: ReactNode
  actions?: ReactNode
}

/** Sits under the top bar (which holds the page title): description on the left, actions on the right. */
export function PageHeader({ description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      {description ? <p className="max-w-2xl text-sm text-slate-600">{description}</p> : <span />}
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
