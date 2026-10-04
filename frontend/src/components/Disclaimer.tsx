import { Info } from 'lucide-react'

export function Disclaimer({ className = '' }: { className?: string }) {
  return (
    <p className={`flex items-center justify-center gap-1.5 text-xs text-slate-500 ${className}`}>
      <Info size={12} aria-hidden="true" />
      Decision support only — synthetic data, not for clinical use.
    </p>
  )
}
