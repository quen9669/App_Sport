// Unit tests for <HomePage />. `fetch` is replaced by a fake so no backend is needed.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { WeekProgress } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import HomePage from './HomePage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const health = { status: 'ok', version: '0.1.0' }

const week: WeekProgress = {
  week: '2026-W42',
  previous_week: '2026-W41',
  next_week: '2026-W43',
  monday: '2026-10-12',
  sunday: '2026-10-18',
  goals: [
    {
      goal: {
        id: 1,
        kind: 'strength_sessions',
        target: 3,
        sport: null,
        start_date: '2026-10-01',
        end_date: null,
        status: 'active',
      },
      done: 2,
      achieved: false,
      activity_ids: [10, 11],
      session_ids: [],
    },
    {
      goal: {
        id: 2,
        kind: 'cardio_sessions',
        target: 3,
        sport: null,
        start_date: '2026-10-01',
        end_date: null,
        status: 'active',
      },
      done: 3,
      achieved: true,
      activity_ids: [12, 13, 14],
      session_ids: [],
    },
  ],
  activities: [
    {
      id: 11,
      name: 'Body Pump',
      sport_type: 'Workout',
      start_time: '2026-10-14T17:00:00Z',
      moving_time_s: 3300,
      elapsed_time_s: 3300,
      distance_m: null,
      category: 'strength',
      automatic_category: 'strength',
    },
  ],
  sessions: [],
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('shows "Backend OK" when the health check succeeds', async () => {
    fakeBackend({ 'GET /api/health': health, 'GET /api/goals/progress': week })

    renderPage()

    // findBy* waits until the text appears (the API call is asynchronous).
    expect(await screen.findByText('Backend OK')).toBeInTheDocument()
  })

  it('shows an error message when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')))

    renderPage()

    expect(await screen.findByText('Backend injoignable')).toBeInTheDocument()
  })

  it('shows one ring per goal with the week progress', async () => {
    fakeBackend({ 'GET /api/health': health, 'GET /api/goals/progress': week })

    renderPage()

    expect(
      await screen.findByLabelText('Séances de musculation : 2 sur 3 séances'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Séances de cardio : 3 sur 3 séances')).toHaveClass(
      'ring--achieved',
    )
    expect(screen.getByRole('heading', { name: /Semaine du 12 oct\. au 18 oct\./ })).toBeVisible()
  })

  it('invites to create goals when there are none', async () => {
    fakeBackend({
      'GET /api/health': health,
      'GET /api/goals/progress': { ...week, goals: [], activities: [] },
    })

    renderPage()

    expect(await screen.findByRole('link', { name: 'Définis tes objectifs' })).toBeInTheDocument()
  })

  it('corrects the category of an activity', async () => {
    const fetchMock = fakeBackend({
      'GET /api/health': health,
      'GET /api/goals/progress': week,
      'PATCH /api/activities/11/category': {
        id: 11,
        category: 'cardio',
        automatic_category: 'strength',
        overridden: true,
      },
    })

    renderPage()
    const select = await screen.findByLabelText('Catégorie de Body Pump')
    await userEvent.selectOptions(select, 'cardio')

    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(patch?.[1]?.body).toBe(JSON.stringify({ category: 'cardio' }))
  })

  it('lists typed strength sessions and says when Strava already counted them', async () => {
    fakeBackend({
      'GET /api/health': health,
      'GET /api/goals/progress': {
        ...week,
        sessions: [
          {
            id: 5,
            performed_at: '2026-10-14T16:00:00Z',
            duration_min: 60,
            exercises: ['Squat', 'Développé couché'],
            set_count: 6,
            counted: false,
          },
        ],
      },
    })

    renderPage()

    expect(await screen.findByText('Squat, Développé couché')).toBeInTheDocument()
    expect(screen.getByText('Déjà comptée via Strava')).toBeInTheDocument()
  })

  it('loads the previous week', async () => {
    const fetchMock = fakeBackend({ 'GET /api/health': health, 'GET /api/goals/progress': week })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Semaine précédente' }))

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('week=2026-W41'))).toBe(true)
  })
})
