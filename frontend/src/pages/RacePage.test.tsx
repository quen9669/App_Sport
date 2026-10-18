// Unit tests for <RacePage />, against a fake backend.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Race } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import RacePage from './RacePage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const form: Race['form'] = {
  status: 'ok',
  vdot: 41.2,
  low: 39.7,
  high: 42.7,
  reason: null,
  efforts: [
    {
      activity_id: 5,
      name: 'Tour du Kirchberg',
      day: '2026-10-15',
      distance_m: 5000,
      time_s: 1500,
      vdot: 41.8,
      method: 'race',
      segment: true,
      weight: 0.95,
      used: true,
    },
    {
      activity_id: 6,
      name: 'Footing',
      day: '2026-10-10',
      distance_m: 8000,
      time_s: 2900,
      vdot: 40.1,
      method: 'heart_rate',
      segment: false,
      weight: 0.88,
      used: false,
    },
  ],
  excluded: [],
}

const race: Race = {
  form,
  predictions: [
    {
      label: '10 km',
      distance_m: 10_000,
      time_s: 2952,
      fastest_s: 2870,
      slowest_s: 3040,
      riegel_s: 2990,
    },
  ],
  zones: [
    { key: 'easy', slow_s_per_km: 406, fast_s_per_km: 370 },
    { key: 'threshold', slow_s_per_km: 309, fast_s_per_km: 309 },
  ],
  target: null,
}

const withTarget: Race = {
  ...race,
  target: {
    name: '',
    distance_m: 10_000,
    race_date: '2026-12-13',
    target_time_s: 2999,
    elevation_gain_m: 0,
    days_left: 56,
    predicted_s: 2952,
    required_vdot: 40.0,
    pace_plan: {
      target_time_s: 2999,
      average_pace_s_per_km: 299.9,
      hill_allowance_s: 0,
      splits: [
        { km: 1, pace_s_per_km: 302.9, elapsed_s: 302.9 },
        { km: 10, pace_s_per_km: 296.9, elapsed_s: 2999 },
      ],
    },
    feasibility: { verdict: 'realistic', gap_s: 47, gap_pct: 0.016 },
  },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RacePage />
    </MemoryRouter>,
  )
}

describe('RacePage', () => {
  it('shows the form, the predictions, the paces and the runs used', async () => {
    fakeBackend({ 'GET /api/race': race })
    renderPage()

    expect(await screen.findByText('41,2')).toBeInTheDocument()
    expect(screen.getByText('39,7 à 42,7')).toBeInTheDocument()
    const predictions = screen.getByRole('table', { name: 'Temps prédits' })
    expect(within(predictions).getByText('49:12')).toBeInTheDocument()
    expect(within(predictions).getByText('47:50 à 50:40')).toBeInTheDocument()
    expect(within(predictions).getByText('4:55 /km')).toBeInTheDocument()
    const zones = screen.getByRole('table', { name: 'Allures d’entraînement' })
    expect(within(zones).getByText('6:46 à 6:10')).toBeInTheDocument()
    expect(within(zones).getByText('5:09')).toBeInTheDocument()
    const runs = screen.getByRole('table', { name: 'Sorties utilisées' })
    expect(within(runs).getByText('meilleur 5 km')).toBeInTheDocument()
    expect(within(runs).getByText('FC')).toBeInTheDocument()
    expect(within(runs).getByRole('link', { name: 'Footing' })).toHaveAttribute(
      'href',
      '/activites/6',
    )
  })

  it('says clearly when the data is insufficient, without times', async () => {
    fakeBackend({
      'GET /api/race': {
        form: {
          ...form,
          status: 'insufficient',
          vdot: null,
          low: null,
          high: null,
          reason: 'Pas assez de sorties exploitables : 1 sur les 120 derniers jours.',
          efforts: [],
        },
        predictions: [],
        zones: [],
        target: null,
      },
    })
    renderPage()

    expect(await screen.findByRole('status')).toHaveTextContent(/Pas assez de sorties/)
    expect(screen.queryByRole('table', { name: 'Temps prédits' })).not.toBeInTheDocument()
  })

  it('saves the target race and shows its plan and feasibility', async () => {
    const fetchMock = fakeBackend({ 'GET /api/race': race, 'PUT /api/race/target': withTarget })
    const user = userEvent.setup()
    renderPage()

    const raceForm = await screen.findByRole('form', { name: 'Préparer une course' })
    await user.type(within(raceForm).getByLabelText('Date'), '2026-12-13')
    await user.type(within(raceForm).getByLabelText(/Temps visé/), '49:59')
    await user.click(within(raceForm).getByRole('button', { name: 'Enregistrer' }))

    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      name: '',
      distance_m: 10_000,
      race_date: '2026-12-13',
      target_time_s: 2999,
      elevation_gain_m: 0,
    })
    const result = await screen.findByRole('group', { name: 'Plan de course' })
    expect(result).toHaveTextContent('Dans 8 semaines (56 jours).')
    expect(result).toHaveTextContent('Réaliste')
    expect(result).toHaveTextContent('Ton objectif demande un VDOT de 40, tu es à 41,2.')
    const splits = within(result).getByRole('table', { name: 'Passages au kilomètre' })
    expect(within(splits).getByText('49:59')).toBeInTheDocument()
  })

  it('refuses a target time it cannot read', async () => {
    const fetchMock = fakeBackend({ 'GET /api/race': race })
    const user = userEvent.setup()
    renderPage()

    const raceForm = await screen.findByRole('form', { name: 'Préparer une course' })
    await user.type(within(raceForm).getByLabelText('Date'), '2026-12-13')
    await user.type(within(raceForm).getByLabelText(/Temps visé/), '50 minutes')
    await user.click(within(raceForm).getByRole('button', { name: 'Enregistrer' }))

    expect(screen.getByRole('alert')).toHaveTextContent(/50:00 ou 1:45:00/)
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
  })

  it('leaves a run out of the estimate', async () => {
    const after: Race = {
      ...race,
      form: {
        ...form,
        efforts: [form.efforts[0]!],
        excluded: [{ activity_id: 6, name: 'Footing', day: '2026-10-10', distance_m: 8000 }],
      },
    }
    const fetchMock = fakeBackend({ 'GET /api/race': race, 'PATCH /api/race/efforts/6': after })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Exclure Footing' }))
    expect(await screen.findByRole('button', { name: 'Réintégrer Footing' })).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ excluded: true })
  })
})
