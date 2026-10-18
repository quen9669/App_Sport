// Unit tests for <HealthPage />, against a fake backend.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { HealthDay, HealthMetrics, TrainingLoad } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import HealthPage from './HealthPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function day(date: string, overrides: Partial<HealthDay> = {}): HealthDay {
  return {
    day: date,
    sleep_s: 7.5 * 3600,
    sleep_score: 80,
    bedtime_min: -30,
    wake_min: 420,
    resting_hr: 50,
    hrv_ms: 60,
    weight_kg: null,
    ...overrides,
  }
}

const metrics: HealthMetrics = {
  days: [day('2026-10-16'), day('2026-10-17', { sleep_s: 6.5 * 3600, resting_hr: 52 })],
  regularity: { nights: 2, bedtime_sd_min: null, wake_sd_min: null },
}

const load: TrainingLoad = {
  weeks: [
    { week: '2026-W41', monday: '2026-10-05', load: 300, sessions: 4, with_heart_rate: 4 },
    { week: '2026-W42', monday: '2026-10-12', load: 420, sessions: 5, with_heart_rate: 5 },
  ],
  acute: 420,
  chronic: 280,
  acwr: 1.5,
  heart_rate: { max_hr: 185, resting_hr: 50, max_source: 'age', resting_source: 'garmin' },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HealthPage />
    </MemoryRouter>,
  )
}

describe('HealthPage', () => {
  it('summarises sleep and recovery over the period', async () => {
    fakeBackend({ 'GET /api/health-metrics': metrics, 'GET /api/training-load': load })

    renderPage()

    // Mean of 7 h 30 and 6 h 30.
    expect(await screen.findByText('7 h 00')).toBeInTheDocument()
    expect(screen.getByText('23:30')).toBeInTheDocument()
    expect(screen.getByText('51 bpm')).toBeInTheDocument()
    expect(screen.getByText(/pas assez de nuits/)).toBeInTheDocument()
  })

  it('asks the backend for another period', async () => {
    const fetchMock = fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
    })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: '90 jours' }))

    expect(screen.getByRole('button', { name: '90 jours' })).toHaveAttribute('aria-pressed', 'true')
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('days=90'))).toBe(true)
  })

  it('shows the training load with its caution and how heart rate was found', async () => {
    fakeBackend({ 'GET /api/health-metrics': metrics, 'GET /api/training-load': load })

    renderPage()

    expect(await screen.findByText('Un peu plus que d’habitude.')).toBeInTheDocument()
    expect(screen.getByText(/pas un diagnostic/)).toBeInTheDocument()
    expect(screen.getByText(/estimée d’après ton âge/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /FC max dans le profil/ })).toBeInTheDocument()
  })
})
