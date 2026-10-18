// The API client's phase 6 behaviour: session cookie, 401 and offline writes.
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fakeBackend, json } from '../test/fakeBackend'
import { AUTH_REQUIRED_EVENT, fetchGoals, OFFLINE_MESSAGE, saveCigaretteDay } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('API client', () => {
  it('sends the session cookie and announces a 401', async () => {
    const fetchMock = fakeBackend({
      'GET /api/goals': () => json({ detail: 'Connexion requise.' }, 401),
    })
    const loginShown = vi.fn()
    window.addEventListener(AUTH_REQUIRED_EVENT, loginShown)

    await expect(fetchGoals()).rejects.toThrow('Connexion requise.')

    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe('include')
    expect(loginShown).toHaveBeenCalledTimes(1)
    window.removeEventListener(AUTH_REQUIRED_EVENT, loginShown)
  })

  it('refuses a change offline with a clear message, without calling the backend', async () => {
    const fetchMock = fakeBackend({})
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)

    await expect(saveCigaretteDay('2026-10-18', 1, null)).rejects.toThrow(OFFLINE_MESSAGE)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
