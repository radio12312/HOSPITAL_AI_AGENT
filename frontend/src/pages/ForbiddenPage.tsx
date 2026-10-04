import { ShieldX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/authContext'
import { ROLE_LABELS } from '../utils/constants'

export function ForbiddenPage() {
  const { user } = useAuth()
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-16 text-center shadow-sm">
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
        <ShieldX size={24} aria-hidden="true" />
      </span>
      <h2 className="text-lg font-semibold text-slate-900">You don't have access to this page</h2>
      <p className="mt-2 max-w-md text-sm text-slate-600">
        {user
          ? `Your role (${ROLE_LABELS[user.role]}) isn't permitted to view this area. If you need access, ask a hospital administrator.`
          : 'Please sign in to continue.'}
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex h-10 items-center rounded-lg bg-teal-700 px-4 text-sm font-medium text-white hover:bg-teal-800"
      >
        Back to dashboard
      </Link>
    </div>
  )
}
