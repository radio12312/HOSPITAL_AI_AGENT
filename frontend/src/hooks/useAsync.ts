import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { getErrorMessage } from '../utils/errors'
import { usePolling } from './usePolling'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  /** True only while there is neither data nor an error yet - show skeletons. */
  loading: boolean
  /** True for reloads (manual or dependency change) while data is already shown. */
  refreshing: boolean
  updatedAt: Date | null
  reload: () => Promise<void>
  setData: Dispatch<SetStateAction<T | null>>
}

interface Result<T> {
  data: T | null
  error: string | null
  updatedAt: Date | null
  /** The fetcher that produced this result; differs from the current one while a new request is in flight. */
  source: (() => Promise<T>) | null
}

/**
 * Runs `fetcher` on mount and whenever its identity changes (wrap it in useCallback with
 * its real dependencies). Responses from superseded requests are ignored. Optional polling
 * refreshes silently in the background.
 */
export function useAsync<T>(fetcher: () => Promise<T>, options: { pollMs?: number } = {}): AsyncState<T> {
  const [result, setResult] = useState<Result<T>>({ data: null, error: null, updatedAt: null, source: null })
  const [manualRefreshing, setManualRefreshing] = useState(false)
  const requestId = useRef(0)

  const execute = useCallback(async () => {
    const id = ++requestId.current
    try {
      const data = await fetcher()
      if (id !== requestId.current) return
      setResult({ data, error: null, updatedAt: new Date(), source: fetcher })
    } catch (err) {
      if (id !== requestId.current) return
      setResult((prev) => ({ ...prev, error: getErrorMessage(err), source: fetcher }))
    } finally {
      if (id === requestId.current) setManualRefreshing(false)
    }
  }, [fetcher])

  useEffect(() => {
    // Data fetching on dependency change: every setState in `execute` runs after `await`,
    // never synchronously, so this does not cause cascading renders.
    // oxlint-disable-next-line react/set-state-in-effect
    void execute()
  }, [execute])

  usePolling(() => void execute(), options.pollMs)

  const reload = useCallback(async () => {
    setManualRefreshing(true)
    // Clearing a previous error lets the UI fall back to skeletons while retrying.
    setResult((prev) => (prev.error ? { ...prev, error: null } : prev))
    await execute()
  }, [execute])

  const setData = useCallback<Dispatch<SetStateAction<T | null>>>((action) => {
    setResult((prev) => ({
      ...prev,
      data: typeof action === 'function' ? (action as (p: T | null) => T | null)(prev.data) : action,
    }))
  }, [])

  const loading = result.data === null && result.error === null
  const refreshing = manualRefreshing || (result.source !== null && result.source !== fetcher)

  return { data: result.data, error: result.error, loading, refreshing, updatedAt: result.updatedAt, reload, setData }
}
