// Unit tests for the Sources page, with a fake backend answering by URL.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { GarminStatus, StravaStatus, SyncLog } from '../api/client'
import SourcesPage from './SourcesPage'

const stravaConnected: StravaStatus = {
  configured: true,
  connected: true,
  athlete_id: '1',
  scope: 'read,activity:read_all',
  activity_count: 42,
  history_complete: false,
}

const garminOff: GarminStatus = {
  configured: false,
  night_count: 0,
  day_count: 0,
  latest_day: null,
  activity_count: 0,
  activity_history_complete: false,
}

const log: SyncLog = {
  id: 1,
  source: 'strava',
  kind: 'manual',
  status: 'success',
  started_at: '2026-10-18T07:00:00Z',
  finished_at: '2026-10-18T07:01:00Z',
  items_created: 42,
  items_updated: 0,
  error: null,
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

/** Install a fake `fetch` and return it, so tests can inspect the calls. */
function fakeBackend(strava: StravaStatus) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/api/strava/status')) return Promise.resolve(json(strava))
    if (url.endsWith('/api/garmin/status')) return Promise.resolve(json(garminOff))
    if (url.includes('/api/sync/logs')) return Promise.resolve(json([log]))
    if (url.endsWith('/api/sync/strava') && init?.method === 'POST') {
      return Promise.resolve(json({ status: 'started' }, 202))
    }
    return Promise.resolve(json({ detail: 'not found' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage(url = '/sources') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <SourcesPage />
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SourcesPage', () => {
  it('shows Strava progress, Garmin hint and the sync journal', async () => {
    fakeBackend(stravaConnected)

    renderPage()

    expect(
      await screen.findByText(/42 activités importées, historique en cours/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Garmin n’est pas configuré/)).toBeInTheDocument()
    expect(screen.getByText('Réussie')).toBeInTheDocument()
  })

  it('offers to connect Strava when not connected yet', async () => {
    fakeBackend({ ...stravaConnected, connected: false })

    renderPage()

    const link = await screen.findByRole('link', { name: 'Connecter Strava' })
    expect(link).toHaveAttribute('href', expect.stringContaining('/api/strava/connect'))
  })

  it('explains the result of the Strava consent page', async () => {
    fakeBackend(stravaConnected)

    renderPage('/sources?strava=missing_scope')

    expect(await screen.findByText(/activités privées/)).toBeInTheDocument()
  })

  it('starts a Strava sync when the button is clicked', async () => {
    const fetchMock = fakeBackend(stravaConnected)
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Synchroniser maintenant' }))

    expect(await screen.findByText('Synchronisation Strava lancée.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/sync/strava'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
