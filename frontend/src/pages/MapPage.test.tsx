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
      city: 'Luxembourg',
      country_code: 'LU',
    },
  ],
  points: [
    {
      id: 2,
      name: 'Nage à Royan',
      sport: 'other',
      start_time: '2026-10-15T09:00:00Z',
      distance_m: 1500,
      moving_time_s: 2400,
      elapsed_time_s: 2500,
      city: 'Royan',
      country_code: 'FR',
      latitude: 45.62,
      longitude: -1.02,
    },
  ],
  places: [
    {
      id: 7,
      name: 'Jims Gare',
      latitude: 49.6,
      longitude: 6.13,
      activity_count: 1,
      activities: [
        {
          id: 3,
          name: 'Musculation',
          sport: 'strength',
          start_time: '2026-10-14T17:00:00Z',
          distance_m: null,
          moving_time_s: 900,
          elapsed_time_s: 900,
          city: 'Luxembourg',
          country_code: 'LU',
        },
      ],
    },
  ],
  bounds: { south: 49.5, west: 6, north: 49.7, east: 6.3 },
  total: 3,
}

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
    // One table row per activity: route, start-only dot and gym session, newest first.
    const table = screen.getByRole('table', { name: 'Activités dans la zone affichée' })
    const rows = within(table).getAllByRole('row').slice(1) // without the header
    expect(rows.map((row) => within(row).getByRole('link').textContent)).toEqual([
      'Nage à Royan',
      'Musculation',
      'Sortie du mardi',
    ])
    expect(within(rows[2]!).getByRole('link')).toHaveAttribute('href', '/activites/1')
    expect(rows[0]).toHaveTextContent('Royan')
    expect(rows[0]).toHaveTextContent('Divers')
    expect(rows[2]).toHaveTextContent('10,2 km')
    // A gym session has no distance: the cell stays empty.
    expect(within(rows[1]!).getAllByRole('cell')[5]).toHaveTextContent(/^$/)
    expect(
      screen.getByText(/3 activités correspondent aux filtres, 3 dans la zone/),
    ).toBeInTheDocument()
    const url = String(fetchMock.mock.calls.find(([u]) => String(u).includes('/map/'))?.[0])
    expect(url).toContain('bbox=6%2C49.5%2C6.3%2C49.7')
    expect(url).toContain('days=14') // the last 14 days by default
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
    expect(within(form).getByLabelText(/Ville/)).toHaveValue('Luxembourg')
    expect(within(form).getByRole('combobox')).toHaveValue('strength_default')
  })
})
