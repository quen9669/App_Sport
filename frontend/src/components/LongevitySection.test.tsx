// Unit tests for <LongevitySection /> and its helpers, against a fake backend.
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Longevity } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import { formatChange, milestoneProgress } from '../utils/longevity'
import LongevitySection from './LongevitySection'

afterEach(() => {
  vi.unstubAllGlobals()
})

const longevity: Longevity = {
  today: '2026-10-18',
  indicators: [
    {
      key: 'intensity_minutes',
      value: 210,
      previous: 140,
      unit: 'min/sem',
      status: 'met',
      evidence: 'established',
      samples: 4,
    },
    {
      key: 'sleep_duration',
      value: 6.5,
      previous: null,
      unit: 'h',
      status: 'partly',
      evidence: 'established',
      samples: 30,
    },
    {
      key: 'vo2max',
      value: null,
      previous: null,
      unit: 'ml/kg/min',
      status: null,
      evidence: 'established',
      samples: 0,
    },
  ],
  smoke_free: {
    quit_date: '2026-09-01',
    days_since_quit: 48,
    smoke_free_days: 47,
    current_streak: 8,
    cigarettes: 2,
    before_start: '2026-08-02',
    before_end: '2026-08-31',
    after_start: '2026-09-19',
    comparisons: [
      {
        key: 'resting_hr',
        unit: 'bpm',
        before: 60,
        after: 55,
        before_days: 30,
        after_days: 30,
      },
      { key: 'steps', unit: 'pas/jour', before: null, after: 8000, before_days: 0, after_days: 30 },
    ],
  },
}

function renderSection() {
  fakeBackend({ 'GET /api/longevity': longevity })
  render(
    <MemoryRouter>
      <LongevitySection />
    </MemoryRouter>,
  )
}

describe('LongevitySection', () => {
  it('shows each lever with its verdict and evidence level, in words', async () => {
    renderSection()
    const intensity = await screen.findByRole('listitem', { name: 'Minutes d’intensité' })
    expect(within(intensity).getByText('210 min/sem')).toBeInTheDocument()
    expect(within(intensity).getByText(/4 semaines avant : 140 min\/sem/)).toBeInTheDocument()
    expect(within(intensity).getByText('Repère atteint')).toBeInTheDocument()
    expect(within(intensity).getByText('Preuve solide')).toBeInTheDocument()

    const sleep = screen.getByRole('listitem', { name: 'Durée de sommeil' })
    expect(within(sleep).getByText('6,5 h')).toBeInTheDocument()
    expect(within(sleep).getByText('En chemin')).toBeInTheDocument()

    const vo2 = screen.getByRole('listitem', { name: 'VO2max (estimation Garmin)' })
    expect(within(vo2).getByText('Pas encore assez de données')).toBeInTheDocument()
  })

  it('shows the smoke-free counters, the milestones and the before / since table', async () => {
    renderSection()
    expect(await screen.findByText('8 jours')).toBeInTheDocument()
    // 48 days: the first three WHO milestones are reached, the next is at 1 year.
    expect(screen.getByText(/La toux et l’essoufflement diminuent/)).toBeInTheDocument()
    expect(screen.getByText(/Prochain repère dans 317 jours \(1 an\)/)).toBeInTheDocument()
    const row = screen.getByRole('row', { name: /FC au repos/ })
    expect(within(row).getByText('60 bpm')).toBeInTheDocument()
    expect(within(row).getByText('−5')).toBeInTheDocument()
    const steps = screen.getByRole('row', { name: /Pas par jour/ })
    expect(within(steps).getAllByText('–')).toHaveLength(2) // no "before", so no change
    expect(screen.getByRole('link', { name: 'En parler au coach longévité' })).toHaveAttribute(
      'href',
      '/longevite',
    )
  })

  it('says so when the backend fails', async () => {
    fakeBackend({})
    render(
      <MemoryRouter>
        <LongevitySection />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('bilan longévité')
  })
})

describe('longevity helpers', () => {
  it('formats a signed change', () => {
    expect(formatChange(60, 55)).toBe('−5')
    expect(formatChange(6.2, 6.9, 1)).toBe('+0,7')
    expect(formatChange(50, 50)).toBe('0')
    expect(formatChange(null, 50)).toBe('–')
  })

  it('finds the milestones reached and the next one', () => {
    expect(milestoneProgress(0).reached).toHaveLength(0)
    expect(milestoneProgress(0).next?.daysLeft).toBe(1)
    expect(milestoneProgress(400).reached.map((m) => m.when)).toContain('1 an')
    expect(milestoneProgress(20 * 365).next).toBeNull()
  })
})
