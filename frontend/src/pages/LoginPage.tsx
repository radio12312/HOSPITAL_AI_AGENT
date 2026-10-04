import { LogIn, ShieldCheck, Stethoscope, UsersRound } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../components/Button'
import { Disclaimer } from '../components/Disclaimer'
import { InlineAlert } from '../components/ErrorState'
import { Field } from '../components/Field'
import { Logo } from '../components/Sidebar'
import { useAuth } from '../context/authContext'
import { getErrorMessage } from '../utils/errors'
import { inputClass } from '../utils/styles'

const DEMO_ACCOUNTS = [
  { label: 'Admin', username: 'admin', password: 'admin123', icon: ShieldCheck },
  { label: 'Doctor', username: 'doctor', password: 'doctor123', icon: Stethoscope },
  { label: 'Coordinator', username: 'coordinator', password: 'coord123', icon: UsersRound },
] as const

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (user) return <Navigate to={from} replace />

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-teal-50 to-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo />
          <p className="mt-4 text-sm text-slate-600">
            AI-assisted hospital operations: bed allocation, staffing, scheduling and emergency response in one place.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Use your hospital account or a demo account below.</p>

          <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4" noValidate>
            <Field label="Username" htmlFor="username">
              <input
                id="username"
                name="username"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Password" htmlFor="password">
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
            </Field>

            {error && <InlineAlert message={error} />}

            <Button
              type="submit"
              icon={LogIn}
              loading={submitting}
              disabled={!username.trim() || !password}
              className="w-full"
            >
              Sign in
            </Button>
          </form>

          <div className="mt-6 border-t border-slate-100 pt-5">
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">Demo accounts</p>
            <div className="grid grid-cols-3 gap-2">
              {DEMO_ACCOUNTS.map(({ label, username: u, password: p, icon: Icon }) => (
                <button
                  key={u}
                  type="button"
                  onClick={() => {
                    setUsername(u)
                    setPassword(p)
                    setError(null)
                  }}
                  aria-label={`Fill in ${label} demo account`}
                  className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-slate-200 px-2 py-3 text-xs font-medium text-slate-700 transition-colors hover:border-teal-700 hover:bg-teal-50 hover:text-teal-800"
                >
                  <Icon size={18} aria-hidden="true" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <Disclaimer className="mt-6" />
      </div>
    </div>
  )
}
