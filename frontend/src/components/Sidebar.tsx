import { HeartPulse, LogOut } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/authContext'
import { ROLE_LABELS } from '../utils/constants'
import { NAV_BY_ROLE } from '../utils/navigation'

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-700 text-white">
        <HeartPulse size={20} aria-hidden="true" />
      </span>
      <span className="text-sm leading-tight font-semibold text-slate-900">
        Hospital Workflow
        <br />
        Agent
      </span>
    </div>
  )
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  const items = user ? NAV_BY_ROLE[user.role] : []

  return (
    <div className="flex h-full w-64 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center px-5">
        <Logo />
      </div>

      <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {items.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-teal-50 text-teal-800'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon size={18} aria-hidden="true" className={isActive ? 'text-teal-700' : 'text-slate-400'} />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {user && (
        <div className="border-t border-slate-200 p-4">
          <div className="flex items-center gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700 uppercase"
              aria-hidden="true"
            >
              {user.username.slice(0, 2)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900">{user.username}</p>
              <span className="mt-0.5 inline-flex rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-800 ring-1 ring-teal-700/20 ring-inset">
                {ROLE_LABELS[user.role]}
              </span>
            </div>
            <button
              type="button"
              onClick={logout}
              aria-label="Log out"
              title="Log out"
              className="cursor-pointer rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <LogOut size={18} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
