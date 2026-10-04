import type { ReactNode } from 'react'
import { labelClass } from '../utils/styles'

interface FieldProps {
  label: string
  htmlFor: string
  hint?: string
  className?: string
  children: ReactNode
}

export function Field({ label, htmlFor, hint, className = '', children }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className={labelClass}>
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
