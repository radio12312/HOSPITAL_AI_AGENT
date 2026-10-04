import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/authContext'
import { ForbiddenPage } from '../pages/ForbiddenPage'
import type { Role } from '../types'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <ForbiddenPage />
  return <>{children}</>
}
