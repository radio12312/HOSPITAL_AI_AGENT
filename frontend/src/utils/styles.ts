// Shared class strings so form controls look identical across pages.

export const inputClass =
  'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ' +
  'placeholder:text-slate-400 focus:border-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-700/20 ' +
  'disabled:cursor-not-allowed disabled:bg-slate-100'

export const selectClass = `${inputClass} pr-8`

export const labelClass = 'mb-1 block text-sm font-medium text-slate-700'

export const tableHeadClass =
  'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500'

export const tableCellClass = 'px-4 py-3 text-sm text-slate-700 whitespace-nowrap'

export const chartColors = {
  primary: '#0f766e',
  primaryLight: '#5eead4',
  neutral: '#cbd5e1',
  slate: '#64748b',
  amber: '#f59e0b',
  sky: '#0284c7',
  red: '#dc2626',
  green: '#16a34a',
  grid: '#e2e8f0',
} as const
