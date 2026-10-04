import { createContext, useContext } from 'react'
import type { User } from '../types'

export interface AuthContextValue {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<User>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
