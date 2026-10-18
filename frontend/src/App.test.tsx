// Tests for the app frame: the 3 folders, their tabs and the always-visible disclaimer.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { AUTH_REQUIRED_EVENT } from './api/client'
import { json } from './test/fakeBackend'

afterEach(() => {
  vi.unstubAllGlobals()
})

/**
 * A backend without password where every other call never answers: only the
 * frame is tested here. `auth` replaces the sign-in answers.
 */
function stubBackend(auth: Record<string, () => Response> = {}) {
  const routes: Record<string, () => Response> = {
    'GET /api/auth/status': () => json({ enabled: false, authenticated: true }),
    ...auth,
  }
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${new URL(String(input)).pathname}`
    const route = routes[key]
    return route ? Promise.resolve(route()) : new Promise<Response>(() => {})
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// MemoryRouter = a router for tests, starting at the given URL.
function renderAt(url: string) {
  if (!vi.isMockFunction(globalThis.fetch)) stubBackend()
  return render(
    <MemoryRouter initialEntries={[url]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('shows the 3 folders and the medical disclaimer', async () => {
    renderAt('/')

    const folders = await screen.findByRole('navigation', { name: 'Dossiers' })
    const links = within(folders).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(['Entraînement', 'Santé', 'Coach'])
    expect(within(folders).getByRole('link', { name: 'Entraînement' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('link', { name: 'Réglages' })).toHaveAttribute('href', '/profil')
    expect(screen.getByText(/pas un avis médical/)).toBeInTheDocument()
  })

  it('shows the tabs of the folder of the current page', async () => {
    renderAt('/sante/sommeil')

    const tabs = await screen.findByRole('navigation', { name: 'Onglets Santé' })
    expect(within(tabs).getByRole('link', { name: 'Sommeil' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    // The summary tab is not lit up by its sub-pages.
    expect(within(tabs).getByRole('link', { name: 'Résumé' })).not.toHaveAttribute('aria-current')
  })

  it('keeps an activity page in the Entraînement folder', async () => {
    renderAt('/activites/42')

    const tabs = await screen.findByRole('navigation', { name: 'Onglets Entraînement' })
    expect(within(tabs).getByRole('link', { name: 'Activités' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('lists every tab, settings included, in the PC sidebar', async () => {
    renderAt('/')

    const menu = await screen.findByRole('navigation', { name: 'Menu' })
    for (const name of ['Ma semaine', 'Mon plan', 'Tabac', 'Mes lieux', 'Sources']) {
      expect(within(menu).getByRole('link', { name })).toBeInTheDocument()
    }
  })

  it('asks for the password first when the app has one', async () => {
    let tries = 0
    const fetchMock = stubBackend({
      'GET /api/auth/status': () => json({ enabled: true, authenticated: false }),
      'POST /api/auth/login': () => {
        tries += 1
        return tries === 1
          ? json({ detail: 'Mot de passe incorrect.' }, 401)
          : json({ enabled: true, authenticated: true })
      },
    })
    renderAt('/')

    const password = await screen.findByLabelText('Mot de passe')
    expect(screen.queryByRole('navigation', { name: 'Dossiers' })).not.toBeInTheDocument()

    await userEvent.type(password, 'faux')
    await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Mot de passe incorrect.')

    await userEvent.type(screen.getByLabelText('Mot de passe'), 'le bon')
    await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByRole('navigation', { name: 'Dossiers' })).toBeInTheDocument()
    const login = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST').at(-1)
    expect(login?.[1]?.body).toBe(JSON.stringify({ password: 'le bon' }))
    expect(login?.[1]?.credentials).toBe('include') // the session cookie is kept
  })

  it('goes back to the login screen when the session ends', async () => {
    renderAt('/')
    await screen.findByRole('navigation', { name: 'Dossiers' })

    window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))

    expect(await screen.findByLabelText('Mot de passe')).toBeInTheDocument()
  })

  it('opens the app when the backend cannot be reached (offline)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    renderAt('/')
    expect(await screen.findByRole('navigation', { name: 'Dossiers' })).toBeInTheDocument()
  })
})
