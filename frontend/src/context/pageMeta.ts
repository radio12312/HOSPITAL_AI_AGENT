import { createContext, useContext, useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export interface LastUpdated {
  path: string
  at: Date
}

export interface PageMetaContextValue {
  lastUpdated: LastUpdated | null
  setLastUpdated: (value: LastUpdated | null) => void
}

export const PageMetaContext = createContext<PageMetaContextValue>({
  lastUpdated: null,
  setLastUpdated: () => undefined,
})

/** Publishes a page's last data refresh time to the top bar. */
export function useLastUpdated(at: Date | null): void {
  const { setLastUpdated } = useContext(PageMetaContext)
  const { pathname } = useLocation()

  useEffect(() => {
    if (at) setLastUpdated({ path: pathname, at })
  }, [at, pathname, setLastUpdated])
}
