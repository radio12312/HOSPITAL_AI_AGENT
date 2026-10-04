import { Loader2, type LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
type Size = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: LucideIcon
}

const variantClass: Record<Variant, string> = {
  primary: 'bg-teal-700 text-white shadow-sm hover:bg-teal-800 disabled:bg-teal-700/60',
  secondary:
    'border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-red-600 text-white shadow-sm hover:bg-red-700 disabled:bg-red-600/60',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:text-slate-400',
}

const sizeClass: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon: Icon,
  disabled,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const iconSize = size === 'sm' ? 14 : 16
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex cursor-pointer items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed ${variantClass[variant]} ${sizeClass[size]} ${className}`}
      {...rest}
    >
      {loading ? (
        <Loader2 size={iconSize} className="animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon size={iconSize} aria-hidden="true" />
      )}
      {children}
    </button>
  )
}
