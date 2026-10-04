import { Clock, Menu, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { getClock, type HospitalClock } from '../api/clock'
import { useAuth } from '../context/authContext'
import { PageMetaContext, type LastUpdated } from '../context/pageMeta'
import { formatClock } from '../utils/format'
import { pageTitle } from '../utils/navigation'
import { Disclaimer } from './Disclaimer'
import { Sidebar } from './Sidebar'

export function Layout() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [lastUpdated, setLastUpdated] = useState<LastUpdated | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const drawerRef = useRef<HTMLDialogElement>(null)
  const title = pageTitle(pathname, user?.role)

  const meta = useMemo(() => ({ lastUpdated, setLastUpdated }), [lastUpdated])

  useEffect(() => {
    document.title = `${title} · Hospital Workflow Agent`
  }, [title])

  useEffect(() => {
    const d = drawerRef.current
    if (!d) return
    if (menuOpen && !d.open) d.showModal()
    if (!menuOpen && d.open) d.close()
  }, [menuOpen])

  const updated = lastUpdated && lastUpdated.path === pathname ? lastUpdated.at : null

  // Simulated hospital clock (moves when a scenario runs); refreshed on navigation.
  const [hospitalTime, setHospitalTime] = useState<HospitalClock | null>(null)
  useEffect(() => {
    getClock()
      .then(setHospitalTime)
      .catch(() => setHospitalTime(null))
  }, [pathname])

  return (
    <PageMetaContext.Provider value={meta}>
      <div className="min-h-screen">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
        >
          Skip to content
        </a>

        {/* Desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden lg:block">
          <Sidebar />
        </aside>

        {/* Mobile drawer */}
        <dialog
          ref={drawerRef}
          aria-label="Navigation menu"
          onCancel={(e) => {
            e.preventDefault()
            setMenuOpen(false)
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setMenuOpen(false)
          }}
          className="m-0 h-full max-h-none w-64 max-w-none bg-transparent p-0 backdrop:bg-slate-900/40 lg:hidden"
        >
          {menuOpen && (
            <div className="relative h-full">
              <Sidebar onNavigate={() => setMenuOpen(false)} />
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close navigation menu"
                className="absolute top-4 right-3 cursor-pointer rounded-md p-1.5 text-slate-500 hover:bg-slate-100"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
          )}
        </dialog>

        <div className="flex min-h-screen flex-col lg:pl-64">
          <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6 lg:px-8">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={menuOpen}
              className="-ml-1 cursor-pointer rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            >
              <Menu size={20} aria-hidden="true" />
            </button>
            <h1 className="min-w-0 flex-1 truncate text-lg font-semibold text-slate-900">{title}</h1>
            {hospitalTime && (
              <p
                className="hidden items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800 md:flex"
                title="Simulated hospital clock"
              >
                <span>Hospital time</span>
                <time dateTime={hospitalTime.now} className="tabular-nums">
                  {new Date(hospitalTime.now).toLocaleString(undefined, {
                    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                  })}
                </time>
                {hospitalTime.active_scenario && (
                  <span className="text-teal-600">· {hospitalTime.active_scenario.replace(/_/g, ' ')}</span>
                )}
              </p>
            )}
            {updated && (
              <p className="flex items-center gap-1.5 text-xs text-slate-500" aria-live="polite">
                <Clock size={14} aria-hidden="true" />
                <span className="hidden sm:inline">Last updated</span>
                <time dateTime={updated.toISOString()} className="tabular-nums">
                  {formatClock(updated)}
                </time>
              </p>
            )}
          </header>

          <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>

          <footer className="border-t border-slate-200 px-4 py-4">
            <Disclaimer />
          </footer>
        </div>
      </div>
    </PageMetaContext.Provider>
  )
}
