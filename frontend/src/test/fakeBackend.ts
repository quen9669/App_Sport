// A fake `fetch` for unit tests: answers by URL (and method), records every call.
import { vi } from 'vitest'

export type Handler = (url: string, init?: RequestInit) => unknown

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

/**
 * Install a fake backend. `routes` maps "METHOD /path" (path without the query
 * string) to the JSON body to answer, or to a function computing it.
 * Unknown routes answer 404.
 */
export function fakeBackend(routes: Record<string, unknown>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    if (!(key in routes)) return Promise.resolve(json({ detail: 'not found' }, 404))
    const route = routes[key]
    const body = typeof route === 'function' ? (route as Handler)(String(input), init) : route
    if (body instanceof Response) return Promise.resolve(body)
    if (body === undefined) return Promise.resolve(new Response(null, { status: 204 }))
    return Promise.resolve(json(body))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
