import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Profile } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import ProfilePage from './ProfilePage'

// Recharts needs a real browser layout: replace the chart by a simple marker.
vi.mock('../components/WeightChart', () => ({
  default: ({ points }: { points: unknown[] }) => <p>Graphique de {points.length} pesées</p>,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

const profile: Profile = {
  height_cm: 180,
  sex: null,
  birth_date: '1990-05-01',
  max_heartrate: null,
  resting_heartrate: null,
  experience_level: null,
  injuries: null,
  age: 36,
  updated_at: '2026-10-18T08:00:00Z',
}

const metrics = [
  { id: 1, measured_on: '2026-10-16', weight_kg: 80, body_fat_pct: null, waist_cm: null },
  { id: 2, measured_on: '2026-10-17', weight_kg: 79.6, body_fat_pct: null, waist_cm: 86 },
]

describe('ProfilePage', () => {
  it('shows the profile, the age and the weight chart', async () => {
    fakeBackend({ 'GET /api/profile': profile, 'GET /api/body-metrics': metrics })

    render(<ProfilePage />)

    expect(await screen.findByDisplayValue('180')).toBeInTheDocument()
    expect(screen.getByText('(36 ans)')).toBeInTheDocument()
    expect(await screen.findByText('Graphique de 2 pesées')).toBeInTheDocument()
  })

  it('shows field errors and does not send an invalid profile', async () => {
    const fetchMock = fakeBackend({ 'GET /api/profile': profile, 'GET /api/body-metrics': [] })

    render(<ProfilePage />)
    const height = await screen.findByLabelText('Taille (cm)')
    await userEvent.clear(height)
    await userEvent.type(height, '300')
    await userEvent.type(screen.getByLabelText('FC repos (si connue)'), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))

    expect(screen.getByText('Entre 100 et 250 cm')).toBeInTheDocument()
    expect(screen.getByText('Entre 30 et 110 bpm')).toBeInTheDocument()
    expect(height).toHaveAttribute('aria-invalid', 'true')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
  })

  it('saves a valid profile', async () => {
    const fetchMock = fakeBackend({
      'GET /api/profile': profile,
      'GET /api/body-metrics': [],
      'PUT /api/profile': { ...profile, height_cm: 181 },
    })

    render(<ProfilePage />)
    const height = await screen.findByLabelText('Taille (cm)')
    await userEvent.clear(height)
    await userEvent.type(height, '181')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le profil' }))

    expect(await screen.findByText('Profil enregistré.')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({ height_cm: 181, sex: null })
  })
})
