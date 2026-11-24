// Loads data from the backend once (and again when `deps` change or `reload()` is called).
// One place for the "fetch, ignore the answer if the page left, keep the error" pattern.
import { useCallback, useEffect, useState, type DependencyList } from 'react'

export function useLoad<T>(fetcher: () => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false // the answer of a page that has already gone is ignored
    fetcher()
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `fetcher` is a new function each render; `deps` says when to reload
  }, [...deps, tick])

  const reload = useCallback(() => setTick((value) => value + 1), [])
  // For screens whose actions answer with fresh data: use it, and forget an old load error.
  const replace = useCallback((value: T) => {
    setData(value)
    setError(null)
  }, [])
  return { data, error, reload, replace, setData }
}
