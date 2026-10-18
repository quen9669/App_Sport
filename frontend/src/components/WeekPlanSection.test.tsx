// Unit tests for the accepted plans on the Mon plan page.
import { render, screen, within } from '@testing-library/react'
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
})
