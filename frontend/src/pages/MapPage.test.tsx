// Unit tests for <MapPage />. Leaflet needs a real browser (canvas), so the map
// component is replaced by a stand-in that reports a view and lists what it got;
// the real map is covered by the E2E test.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MapRoutes, Place } from '../api/client'
import type { MapMode } from '../components/RoutesMap'
import { fakeBackend } from '../test/fakeBackend'
import MapPage from './MapPage'

vi.mock('../components/RoutesMap', () => ({
  default: function FakeMap(props: {
    routes: { id: number }[]
    mode: MapMode
    onViewChange: (bbox: string, zoom: number) => void
  }) {
    const { onViewChange } = props
    useEffect(() => onViewChange('6,49.5,6.3,49.7', 12), [onViewChange])
    return (
      <div data-testid="map">
        {props.routes.length} tracés, mode {props.mode}
      </div>
    )
  },
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

const data: MapRoutes = {
  routes: [
    {
      id: 1,
      name: 'Sortie du mardi',
      sport_type: 'running',
      sport: 'run',
      start_time: '2026-10-13T17:00:00Z',
      distance_m: 10_200,
      moving_time_s: 3300,
      elapsed_time_s: 3400,
      elevation_gain_m: 80,
      average_speed_mps: 3.1,
      average_heartrate: 148,
      polyline: '_p~iF~ps|U_ulLnnqC',
    },
  ],
  places: [
    {
      id: 7,
      name: 'Jims Gare',
      latitude: 49.6,
      longitude: 6.13,
      activity_count: 12,
      activities: [],
    },
  ],
  bounds: { south: 49.5, west: 6, north: 49.7, east: 6.3 },
  total: 13,
}

const places: Place[] = [
  {
    id: 7,
    name: 'Jims Gare',
    latitude: 49.6,
    longitude: 6.13,
    role: 'strength_default',
    chosen_count: 0,
  },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <MapPage />
    </MemoryRouter>,
  )
}

describe('MapPage', () => {
  it('loads the visible activities and lists them', async () => {
    const fetchMock = fakeBackend({ 'GET /api/map/routes': data, 'GET /api/places': places })
    renderPage()

    expect(await screen.findByText('1 tracés, mode routes')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sortie du mardi' })).toHaveAttribute(
      'href',
      '/activites/1',
    )
    expect(
      screen.getByText(/13 activités correspondent aux filtres, 13 dans la zone/),
    ).toBeInTheDocument()
    const url = String(fetchMock.mock.calls.find(([u]) => String(u).includes('/map/'))?.[0])
    expect(url).toContain('bbox=6%2C49.5%2C6.3%2C49.7')
    expect(url).toContain('days=365') // one year by default
  })

  it('sends the filters to the backend and switches to the heatmap', async () => {
    const fetchMock = fakeBackend({ 'GET /api/map/routes': data, 'GET /api/places': places })
    renderPage()
    await screen.findByTestId('map')

    const sports = screen.getByRole('group', { name: 'Sport' })
    await userEvent.click(within(sports).getByRole('button', { name: 'Vélo' }))
    await userEvent.click(screen.getByRole('button', { name: 'Tout' }))
    await userEvent.type(screen.getByLabelText('Distance min (km)'), '20')
    await userEvent.click(screen.getByRole('button', { name: 'Heatmap' }))

    await waitFor(() => {
      const last = String(fetchMock.mock.calls.at(-1)?.[0])
      expect(last).toContain('sport=ride')
      expect(last).toContain('min_km=20')
      expect(last).not.toContain('days=')
    })
    expect(screen.getByText('1 tracés, mode heat')).toBeInTheDocument()
  })

  it('shows the places used for sessions without GPS', async () => {
    fakeBackend({ 'GET /api/map/routes': data, 'GET /api/places': places })
    renderPage()

    const panel = await screen.findByRole('region', { name: 'Mes lieux' })
    const form = await within(panel).findByRole('form', { name: 'Lieu Jims Gare' })
    expect(within(form).getByDisplayValue('49.6, 6.13')).toBeInTheDocument()
    expect(within(form).getByRole('combobox')).toHaveValue('strength_default')
  })
})
