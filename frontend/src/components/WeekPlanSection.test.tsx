// Unit tests for the accepted plans on the Mon plan page.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CoachPlan } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import WeekPlanSection from './WeekPlanSection'

afterEach(() => {
  vi.unstubAllGlobals()
})

const plan: CoachPlan = {
  id: 3,
  coach: 'training',
  week_start: '2026-10-12',
  summary: 'Semaine allégée.',
  status: 'accepted',
  sessions: [
    {
      day: '2026-10-13',
      kind: 'class',
      title: 'Body Pump',
      duration_min: 55,
      intensity: '',
      details: '',
      why: 'Force',
    },
  ],
}

function renderSection() {
  return render(
    <MemoryRouter>
      <WeekPlanSection />
    </MemoryRouter>,
  )
}

describe('WeekPlanSection', () => {
  it('shows the accepted plan of the week, without buttons', async () => {
    fakeBackend({ 'GET /api/coach/plans/current': { this_week: plan, next_week: null } })
    renderSection()
    const card = await screen.findByRole('article', { name: 'Plan de la semaine du 12 oct.' })
    expect(within(card).getByText('Body Pump')).toBeInTheDocument()
    expect(within(card).getByText(/mar\. 13 oct\./)).toBeInTheDocument()
    expect(within(card).queryByRole('button')).toBeNull()
  })

  it('points to the coach when no plan is accepted', async () => {
    fakeBackend({ 'GET /api/coach/plans/current': { this_week: null, next_week: null } })
    renderSection()
    expect(await screen.findByRole('link', { name: /Demande un plan/ })).toHaveAttribute(
      'href',
      '/coach',
    )
  })

  describe('runs sent to Garmin', () => {
    // Far in the future, so the run is never "past" whatever day the tests run.
    const run: CoachPlan = {
      ...plan,
      id: 4,
      week_start: '2099-01-05',
      sessions: [
        {
          day: '2099-01-06',
          kind: 'run',
          title: 'Fractionné',
          duration_min: 50,
          intensity: '',
          details: '',
          why: 'VMA',
          workout: {
            warmup: { duration_s: 900, distance_m: null, pace: 'easy' },
            blocks: [
              {
                repeats: 6,
                work: { duration_s: null, distance_m: 800, pace: 'interval' },
                recovery: { duration_s: 120, distance_m: null, pace: 'none' },
              },
            ],
            cooldown: null,
          },
          garmin: null,
        },
      ],
    }
    const current = {
      this_week: run,
      next_week: null,
      pace_targets: { interval: { slow_s_per_km: 245, fast_s_per_km: 235 } },
    }
    const sent: CoachPlan = {
      ...run,
      sessions: [
        { ...run.sessions[0]!, garmin: { workout_id: 7, sent_at: '2099-01-04T10:00:00Z' } },
      ],
    }

    it('shows the steps with their paces and sends one run', async () => {
      const fetchMock = fakeBackend({
        'GET /api/coach/plans/current': current,
        'POST /api/coach/plans/4/sessions/0/garmin': sent,
      })
      renderSection()
      const steps = await screen.findByRole('list', { name: 'Étapes : Fractionné' })
      expect(within(steps).getByText(/6 × 800 m · 3:55-4:05 \/km/)).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Envoyer sur ma Garmin' }))
      expect(await screen.findByText(/Sur ta Garmin/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retirer de ma Garmin' })).toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true)
    })

    it('says why a send failed', async () => {
      fakeBackend({
        'GET /api/coach/plans/current': current,
        'POST /api/coach/plans/4/sessions/0/garmin': () =>
          new Response(JSON.stringify({ detail: 'Garmin n’est pas configuré (page Sources).' }), {
            status: 409,
          }),
      })
      renderSection()
      fireEvent.click(await screen.findByRole('button', { name: 'Envoyer sur ma Garmin' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('page Sources')
    })

    it('edits the steps before sending', async () => {
      let saved: unknown = null
      fakeBackend({
        'GET /api/coach/plans/current': current,
        'PUT /api/coach/plans/4/sessions/0/workout': (_url: string, init?: RequestInit) => {
          saved = JSON.parse(String(init?.body))
          return run
        },
      })
      renderSection()
      fireEvent.click(await screen.findByRole('button', { name: 'Modifier les étapes' }))
      const form = screen.getByRole('form', { name: 'Modifier les étapes' })
      fireEvent.change(within(form).getByLabelText('Répétitions'), { target: { value: '8' } })
      fireEvent.click(within(form).getByLabelText('Retour au calme'))
      fireEvent.click(within(form).getByRole('button', { name: 'Enregistrer' }))
      expect(
        await screen.findByRole('button', { name: 'Envoyer sur ma Garmin' }),
      ).toBeInTheDocument()
      expect(saved).toMatchObject({
        blocks: [{ repeats: 8 }],
        cooldown: { duration_s: 600, pace: 'easy' },
      })
    })
  })
})
