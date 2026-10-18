// Unit tests for <ActivityPage />. The Leaflet map and the charts are replaced
// by stand-ins (Leaflet needs a real browser); the E2E test opens the real page.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ActivityDetail, Place } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import ActivityPage from './ActivityPage'

vi.mock('../components/ActivityMap', () => ({
  default: (props: { place: { latitude: number } | null }) => (
    <div data-testid="activity-map">{props.place ? 'lieu' : 'parcours'}</div>
  ),
}))
vi.mock('../components/DetailCharts', () => ({
  default: (props: { rows: unknown[] }) => <div>{props.rows.length} points</div>,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

const run: ActivityDetail = {
  id: 1,
  name: 'Sortie longue',
  sport_type: 'running',
  sport: 'run',
  category: 'cardio',
  source: 'garmin',
  start_time: '2026-10-17T07:00:00Z',
  elapsed_time_s: 5400,
  moving_time_s: 5300,
  distance_m: 16_000,
  elevation_gain_m: 120,
  average_speed_mps: 1000 / 330,
  max_speed_mps: 4,
  average_heartrate: 146,
  max_heartrate: 172,
  average_cadence: 84,
  hidden: false,
  polyline: '_p~iF~ps|U_ulLnnqC',
  place: null,
  series: {
    time_s: [0, 10, 20],
    distance_m: [0, 30, 60],
    altitude_m: [300, 301, 302],
    heartrate: [120, 125, 130],
    speed_mps: [3, 3, 3],
    latlng: [
      [49.6, 6.1],
      [49.6, 6.11],
      [49.6, 6.12],
    ],
  },
}

const gym: ActivityDetail = {
  ...run,
  id: 2,
  name: 'Musculation',
  sport_type: 'strength_training',
  sport: 'strength',
  category: 'strength',
  distance_m: null,
  elevation_gain_m: null,
  average_speed_mps: null,
  polyline: null,
  place: { id: 7, name: 'Jims Gare', latitude: 49.6, longitude: 6.13, chosen: false },
  series: { time_s: [], distance_m: [], altitude_m: [], heartrate: [], speed_mps: [], latlng: [] },
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
  {
    id: 8,
    name: 'Jims Gasperich',
    latitude: 49.59,
    longitude: 6.12,
    role: 'other_default',
    chosen_count: 0,
  },
]

function renderPage(id: number) {
  return render(
    <MemoryRouter initialEntries={[`/activites/${id}`]}>
      <Routes>
        <Route path="/activites/:id" element={<ActivityPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ActivityPage', () => {
  it('shows the key numbers, the route and the charts', async () => {
    fakeBackend({ 'GET /api/activities/1': run })
    renderPage(1)

    expect(await screen.findByRole('heading', { name: 'Sortie longue' })).toBeInTheDocument()
    expect(screen.getByText('16 km')).toBeInTheDocument()
    expect(screen.getByText('5:30 /km')).toBeInTheDocument()
    expect(screen.getByText('172 bpm')).toBeInTheDocument()
    expect(await screen.findByTestId('activity-map')).toHaveTextContent('parcours')
    expect(await screen.findByText('3 points')).toBeInTheDocument()
  })

  it('lets the user choose the place of a session without GPS', async () => {
    const moved: ActivityDetail = {
      ...gym,
      place: { id: 8, name: 'Jims Gasperich', latitude: 49.59, longitude: 6.12, chosen: true },
    }
    const fetchMock = fakeBackend({
      'GET /api/activities/2': gym,
      'GET /api/places': places,
      'PATCH /api/activities/2/place': moved,
    })
    renderPage(2)

    const select = await screen.findByLabelText('Lieu de la séance (pas de GPS)')
    expect(screen.getByRole('option', { name: 'Lieu par défaut (Jims Gare)' })).toBeInTheDocument()
    await screen.findByRole('option', { name: 'Jims Gasperich' })
    await userEvent.selectOptions(select, '8')

    await waitFor(() => expect(select).toHaveValue('8'))
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ place_id: 8 })
    expect(screen.getByText('Pas de courbes détaillées pour cette activité.')).toBeInTheDocument()
  })

  it('says when the activity does not exist', async () => {
    fakeBackend({})
    renderPage(99)
    expect(await screen.findByRole('alert')).toHaveTextContent('Cette activité n’existe pas.')
  })
})
