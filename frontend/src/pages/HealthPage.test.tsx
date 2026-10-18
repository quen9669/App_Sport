// Unit tests for <HealthPage />, against a fake backend.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  HealthDay,
  HealthMetrics,
  IntensityMinutes,
  Smoking,
  TrainingLoad,
} from '../api/client'
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
    weight_measured_on: null,
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
  target: null,
}

const intensity: IntensityMinutes = {
  weeks: [
    { week: '2026-W41', monday: '2026-10-05', moderate: 200, vigorous: 100, total: 400, days: 7 },
    { week: '2026-W42', monday: '2026-10-12', moderate: 150, vigorous: 90, total: 330, days: 7 },
  ],
  target: 350,
}

// The smoke-free card has its own tests (components/SmokeFreeSection.test.tsx).
const smoking: Smoking = {
  quit_date: '2026-09-01',
  quit_date_is_default: true,
  today: '2026-10-18',
  days_since_quit: 48,
  smoke_free_days: 48,
  cigarette_days: 0,
  cigarettes: 0,
  current_streak: 48,
  longest_streak: 48,
  months: [],
  entries: [],
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
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()

    // Mean of 7 h 30 and 6 h 30.
    expect(await screen.findByText('7 h 00')).toBeInTheDocument()
    expect(screen.getByText('23:30')).toBeInTheDocument()
    expect(screen.getByText('51 bpm')).toBeInTheDocument()
    expect(screen.getByText(/pas assez de nuits/)).toBeInTheDocument()
  })

  it('shows the last weigh-in, carried forward', async () => {
    const weighed = { weight_kg: 79.5, weight_measured_on: '2026-09-02' }
    fakeBackend({
      'GET /api/health-metrics': {
        ...metrics,
        days: metrics.days.map((d) => ({ ...d, ...weighed })),
      },
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()

    expect(await screen.findByText('79,5 kg')).toBeInTheDocument()
    expect(screen.getByText('2 sept.')).toBeInTheDocument()
  })

  it('says when there is no weigh-in at all', async () => {
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()

    expect(await screen.findByText(/Aucune pesée pour l’instant/)).toBeInTheDocument()
  })

  it('asks the backend for another period', async () => {
    const fetchMock = fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: '90 jours' }))

    expect(screen.getByRole('button', { name: '90 jours' })).toHaveAttribute('aria-pressed', 'true')
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('days=90'))).toBe(true)
  })

  it('shows the training load with its caution and how heart rate was found', async () => {
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()

    expect(await screen.findByText('Un peu plus que d’habitude.')).toBeInTheDocument()
    expect(screen.getByText(/pas un diagnostic/)).toBeInTheDocument()
    expect(screen.getByText(/estimée d’après ton âge/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /FC max dans le profil/ })).toBeInTheDocument()
  })

  it('says when the max heart rate is the highest one the watch recorded', async () => {
    const observed = { ...load, heart_rate: { ...load.heart_rate, max_source: 'observed' } }
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': observed,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })

    renderPage()

    expect(await screen.findByText(/la plus haute mesurée par ta montre/)).toBeInTheDocument()
  })

  it('shows the weekly training load target, or how to add one', async () => {
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })
    const { unmount } = renderPage()
    expect(
      await screen.findByRole('link', { name: /objectif « Charge d’entraînement »/ }),
    ).toBeInTheDocument()
    unmount()

    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': { ...load, target: 350 },
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })
    renderPage()
    const section = await screen.findByRole('region', { name: 'Charge d’entraînement' })
    expect(within(section).getByText('Objectif par semaine')).toBeInTheDocument()
    expect(within(section).getByText('350')).toBeInTheDocument()
  })

  it('shows the weekly Garmin intensity minutes with their goal', async () => {
    fakeBackend({
      'GET /api/health-metrics': metrics,
      'GET /api/training-load': load,
      'GET /api/intensity-minutes': intensity,
      'GET /api/smoking': smoking,
    })
    renderPage()

    const section = await screen.findByRole('region', { name: 'Minutes d’intensité' })
    expect(within(section).getByText('330 min')).toBeInTheDocument()
    expect(within(section).getByText('350 min')).toBeInTheDocument()
    expect(within(section).getByText(/compte double/)).toBeInTheDocument()
  })
})
