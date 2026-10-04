import type { ReactNode } from 'react'
import type { Tone } from '../utils/tones'

const toneClass: Record<Tone, string> = {
  success: 'bg-green-50 text-green-700 ring-green-600/20',
  warning: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  danger: 'bg-red-50 text-red-700 ring-red-600/20',
  info: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  neutral: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  primary: 'bg-teal-50 text-teal-800 ring-teal-700/20',
}

interface BadgeProps {
  tone?: Tone
  children: ReactNode
  className?: string
}

export function Badge({ tone = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${toneClass[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
