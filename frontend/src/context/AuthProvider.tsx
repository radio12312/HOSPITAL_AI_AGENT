import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { login as loginRequest } from '../api/auth'
import { clearStoredSession, TOKEN_KEY, USER_KEY } from '../api/client'
import type { User } from '../types'
import { AuthContext, type AuthContextValue } from './authContext'

function readStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw || !localStorage.getItem(TOKEN_KEY)) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser)
  const [token, setToken] = useState<string | null>(() =>
    readStoredUser() ? localStorage.getItem(TOKEN_KEY) : null,
  )

  const login = useCallback(async (username: string, password: string) => {
    const res = await loginRequest({ username, password })
    localStorage.setItem(TOKEN_KEY, res.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const logout = useCallback(() => {
    clearStoredSession()
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, login, logout }),
    [user, token, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
