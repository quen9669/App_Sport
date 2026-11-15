// Unit tests for the Monitoring page (Réglages), with a fake backend.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Monitoring } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import { formatAgo, formatBytes } from '../utils/monitoring'
import MonitoringPage from './MonitoringPage'

const NOW = '2026-11-15T18:00:00Z'

function monitoring(overrides: Partial<Monitoring> = {}): Monitoring {
  return {
    status: 'warning',
    checked_at: NOW,
    started_at: '2026-11-13T14:00:00Z',
    sources: [
      {
        source: 'garmin',
        status: 'ok',
        last_success_at: '2026-11-15T16:08:00Z',
        last_run_at: '2026-11-15T16:08:00Z',
        last_run_status: 'success',
        last_error: null,
        failures_7d: 0,
      },
      {
        source: 'strava',
        status: 'warning',
        last_success_at: '2026-11-15T10:00:00Z',
        last_run_at: '2026-11-15T16:00:00Z',
        last_run_status: 'failed',
        last_error: 'Strava a refusé la connexion',
        failures_7d: 2,
      },
    ],
    backup: {
      status: 'ok',
      last_copy_at: '2026-11-15T03:30:00Z',
      copies: 14,
      last_copy_bytes: 90 * 1024 * 1024,
    },
    memory: { status: 'ok', used_bytes: 214 * 1024 * 1024, limit_bytes: 512 * 1024 * 1024 },
    coach: { status: 'ok', enabled: true, month: '2026-11', spent_eur: 3.4, limit_eur: 10 },
    database_bytes: 86 * 1024 * 1024,
    activities_7d: 9,
    grafana_url: 'http://grafana.test/d/app-sport',
    ...overrides,
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('MonitoringPage', () => {
  it('shows every check with words, not colour alone', async () => {
    fakeBackend({ 'GET /api/monitoring': monitoring() })
    render(<MonitoringPage />)

    expect(await screen.findByText('Quelque chose est à surveiller.')).toBeInTheDocument()
    expect(screen.getByText('il y a 1 h 52')).toBeInTheDocument() // Garmin
    expect(screen.getByText(/Strava a refusé la connexion/)).toBeInTheDocument()
    expect(screen.getByText(/Échecs sur 7 jours : 2/)).toBeInTheDocument()
    expect(screen.getByText('3,40 € dépensés sur 10,00 € ce mois-ci')).toBeInTheDocument()
    expect(screen.getByText('Mémoire : 214 Mo sur 512 Mo')).toBeInTheDocument()
    expect(screen.getByText(/14 copies gardées · 90 Mo chacune/)).toBeInTheDocument()
  })

  it('opens Grafana in a new tab, and hides the button without an address', async () => {
    fakeBackend({ 'GET /api/monitoring': monitoring() })
    const { unmount } = render(<MonitoringPage />)
    const link = await screen.findByRole('link', { name: 'Ouvrir dans Grafana' })
    expect(link).toHaveAttribute('href', 'http://grafana.test/d/app-sport')
    expect(link).toHaveAttribute('target', '_blank')
    unmount()

    fakeBackend({ 'GET /api/monitoring': monitoring({ grafana_url: null }) })
    render(<MonitoringPage />)
    await screen.findByText('Quelque chose est à surveiller.')
    expect(screen.queryByRole('link', { name: 'Ouvrir dans Grafana' })).toBeNull()
  })

  it('reloads on "Actualiser" and says when the backend cannot answer', async () => {
    const fetchMock = fakeBackend({ 'GET /api/monitoring': monitoring({ status: 'ok' }) })
    render(<MonitoringPage />)
    await screen.findByText('Tout fonctionne.')
    await userEvent.click(screen.getByRole('button', { name: 'Actualiser' }))
    expect(fetchMock).toHaveBeenCalledTimes(2)

    fakeBackend({})
    await userEvent.click(screen.getByRole('button', { name: 'Actualiser' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Impossible de lire l'état de l'app.",
    )
  })
})

describe('formatAgo and formatBytes', () => {
  it('speaks French', () => {
    expect(formatAgo('2026-11-15T17:59:50Z', NOW)).toBe("à l'instant")
    expect(formatAgo('2026-11-15T17:15:00Z', NOW)).toBe('il y a 45 min')
    expect(formatAgo('2026-11-15T15:55:00Z', NOW)).toBe('il y a 2 h 05')
    expect(formatAgo('2026-11-12T18:00:00Z', NOW)).toBe('il y a 3 j')
    expect(formatBytes(512 * 1024 * 1024)).toBe('512 Mo')
    expect(formatBytes(1536 * 1024 * 1024)).toBe('1,5 Go')
    expect(formatBytes(2048)).toBe('2 Ko')
  })
})
