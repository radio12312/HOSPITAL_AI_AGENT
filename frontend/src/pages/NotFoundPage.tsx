import { MapPinOff } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-16 text-center shadow-sm">
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <MapPinOff size={24} aria-hidden="true" />
      </span>
      <h2 className="text-lg font-semibold text-slate-900">Page not found</h2>
      <p className="mt-2 text-sm text-slate-600">The page you're looking for doesn't exist.</p>
      <Link
        to="/"
        className="mt-6 inline-flex h-10 items-center rounded-lg bg-teal-700 px-4 text-sm font-medium text-white hover:bg-teal-800"
      >
        Back to dashboard
      </Link>
    </div>
  )
}
