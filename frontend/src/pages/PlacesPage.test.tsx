// Unit tests for <PlacesPage />: the places of the sessions without GPS.
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Place } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import PlacesPage from './PlacesPage'

const places: Place[] = [
  {
    id: 7,
    name: 'Jims Gare',
    latitude: 49.6,
    longitude: 6.13,
    city: 'Luxembourg',
    role: 'strength_default',
    chosen_count: 0,
  },
]

describe('PlacesPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the places used for sessions without GPS', async () => {
    fakeBackend({ 'GET /api/places': places })
    render(<PlacesPage />)

    const panel = await screen.findByRole('region', { name: 'Mes lieux' })
    const form = await within(panel).findByRole('form', { name: 'Lieu Jims Gare' })
    expect(within(form).getByDisplayValue('49.6, 6.13')).toBeInTheDocument()
    expect(within(form).getByLabelText(/Ville/)).toHaveValue('Luxembourg')
    expect(within(form).getByRole('combobox')).toHaveValue('strength_default')
  })
})
