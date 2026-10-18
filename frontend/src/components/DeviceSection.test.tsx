// "Cet appareil": install button, and sign-out that forgets the offline data.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AUTH_REQUIRED_EVENT } from '../api/client'
import { captureInstallPrompt } from '../pwa/install'
import { fakeBackend } from '../test/fakeBackend'
import DeviceSection from './DeviceSection'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DeviceSection', () => {
  it('signs out, empties the offline data and shows the login screen', async () => {
    const fetchMock = fakeBackend({
      'GET /api/auth/status': { enabled: true, authenticated: true },
      'POST /api/auth/logout': undefined,
    })
    const deleteCache = vi.fn().mockResolvedValue(true)
    vi.stubGlobal('caches', { delete: deleteCache })
    localStorage.setItem('app-sport:last-online', '2026-10-18T10:00:00Z')
    const loginShown = vi.fn()
    window.addEventListener(AUTH_REQUIRED_EVENT, loginShown)

    render(<DeviceSection />)
    await userEvent.click(await screen.findByRole('button', { name: 'Se déconnecter' }))

    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true)
    expect(deleteCache).toHaveBeenCalledWith('api-cache')
    expect(localStorage.getItem('app-sport:last-online')).toBeNull()
    expect(loginShown).toHaveBeenCalled()
    window.removeEventListener(AUTH_REQUIRED_EVENT, loginShown)
  })

  it('has no sign-out button when the app has no password', async () => {
    fakeBackend({ 'GET /api/auth/status': { enabled: false, authenticated: true } })
    render(<DeviceSection />)
    expect(await screen.findByText(/Pour installer l’app/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Se déconnecter' })).not.toBeInTheDocument()
  })

  it('offers to install the app once Chrome allows it', async () => {
    fakeBackend({ 'GET /api/auth/status': { enabled: false, authenticated: true } })
    captureInstallPrompt()
    render(<DeviceSection />)

    const prompt = vi.fn().mockResolvedValue(undefined)
    const offer = Object.assign(new Event('beforeinstallprompt'), {
      prompt,
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    })
    window.dispatchEvent(offer)

    await userEvent.click(await screen.findByRole('button', { name: 'Installer l’app' }))
    expect(prompt).toHaveBeenCalled()
    expect(await screen.findByText(/App installée/)).toBeInTheDocument()
  })
})
