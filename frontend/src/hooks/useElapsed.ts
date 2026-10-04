import { useEffect, useState } from 'react'

/** Seconds elapsed since `active` became true; resets when it turns false. */
export function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!active) return undefined
    const started = Date.now()
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => {
      window.clearInterval(id)
      setSeconds(0)
    }
  }, [active])

  return seconds
}
