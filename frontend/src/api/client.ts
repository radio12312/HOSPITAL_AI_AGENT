import axios from 'axios'

export const TOKEN_KEY = 'hwa_token'
export const USER_KEY = 'hwa_user'

export function clearStoredSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export const api = axios.create({
  baseURL: '/api',
  // Agent and scenario calls can take 10-30 s; matches the nginx proxy_read_timeout.
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const isLoginRequest = error.config?.url?.includes('/auth/login') ?? false
      if (!isLoginRequest) {
        clearStoredSession()
        if (window.location.pathname !== '/login') {
          window.location.assign('/login')
        }
      }
    }
    return Promise.reject(error)
  },
)

/** Drops undefined / null / empty-string params so they are not sent as `?key=`. */
export function cleanParams<T extends object>(params: T): Partial<T> {
  const entries = Object.entries(params).filter(
    (entry) => entry[1] !== undefined && entry[1] !== null && entry[1] !== '',
  )
  return Object.fromEntries(entries) as Partial<T>
}
