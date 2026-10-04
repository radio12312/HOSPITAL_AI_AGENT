import { useEffect, useRef } from 'react'

/**
 * Calls `callback` every `intervalMs` while enabled. Skips ticks while the tab is hidden
 * so background tabs do not hammer the API.
 */
export function usePolling(callback: () => void, intervalMs: number | undefined, enabled = true): void {
  const saved = useRef(callback)

  useEffect(() => {
    saved.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled || !intervalMs) return undefined
    const id = window.setInterval(() => {
      if (!document.hidden) saved.current()
    }, intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs, enabled])
}
