// "Activités" tab: every activity on a map (routes or heatmap), with filters by
// sport, period and distance, and the list of what is shown. The places used for
// the sessions without GPS are edited in Réglages (PlacesPage).
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'

import {
  fetchMapRoutes,
  type ActivityRow,
  type Bounds,
  type MapRoutes,
  type SportGroup,
} from '../api/client'
import ActivityTable from '../components/ActivityTable'
import type { MapMode } from '../components/RoutesMap'
import { PERIOD_CHOICES, SPORT_LABELS } from '../utils/activity'

// Loaded on demand: Leaflet (~150 kB) is only downloaded when the map is opened.
const RoutesMap = lazy(() => import('../components/RoutesMap'))

const SPORTS: (SportGroup | null)[] = [null, 'run', 'ride', 'walk', 'strength', 'other']
// The list under the map stops here: beyond, the map itself is more useful.
const LIST_LIMIT = 30

export interface MapFilters {
  sport: SportGroup | null
  days: number | null
  minKm: string // text of the input: "" = no limit
  maxKm: string
}

// FRANKS's choice: the map opens on the last 14 days, framed on them.
const START_FILTERS: MapFilters = { sport: null, days: 14, minKm: '', maxKm: '' }

/** Text input to a number, or undefined when empty or invalid (no filter). */
function kmValue(text: string): number | undefined {
  const value = Number(text.replace(',', '.'))
  return text.trim() === '' || Number.isNaN(value) || value < 0 ? undefined : value
}

export default function MapPage() {
  const [filters, setFilters] = useState<MapFilters>(START_FILTERS)
  const [mode, setMode] = useState<MapMode>('routes')
  const [view, setView] = useState<{ bbox: string; zoom: number } | null>(null)
  const [data, setData] = useState<MapRoutes | null>(null)
  const [fitTo, setFitTo] = useState<Bounds | null>(null)
  const [error, setError] = useState<string | null>(null)
  // After a filter change, the next answer frames the matching activities.
  // Not after a simple move of the map: framing would move it again, forever.
  const frameNext = useRef(true)

  const onViewChange = useCallback((bbox: string, zoom: number) => setView({ bbox, zoom }), [])

  function changeFilters(change: Partial<MapFilters>) {
    frameNext.current = true
    setFilters((current) => ({ ...current, ...change }))
  }

  useEffect(() => {
    if (view === null) return // wait until the map says what it shows
    let cancelled = false
    fetchMapRoutes({
      sport: filters.sport ?? undefined,
      days: filters.days ?? undefined,
      min_km: kmValue(filters.minKm),
      max_km: kmValue(filters.maxKm),
      bbox: view.bbox,
      zoom: Math.round(view.zoom),
    })
      .then((result) => {
        if (cancelled) return
        setError(null)
        setData(result)
        if (frameNext.current) {
          frameNext.current = false
          setFitTo(result.bounds)
        }
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger la carte.')
      })
    return () => {
      cancelled = true
    }
  }, [filters, view])

  const shown = data
    ? data.routes.length +
      data.points.length +
      data.places.reduce((n, p) => n + p.activity_count, 0)
    : 0

  return (
    <>
      <h1>Activités</h1>
      <p className="subtitle">Tes parcours sur la carte, et la liste des séances</p>

      <MapFiltersForm filters={filters} onChange={changeFilters} />
      <div className="segmented" role="group" aria-label="Affichage">
        <button
          type="button"
          className="secondary"
          aria-pressed={mode === 'routes'}
          onClick={() => setMode('routes')}
        >
          Tracés
        </button>
        <button
          type="button"
          className="secondary"
          aria-pressed={mode === 'heat'}
          onClick={() => setMode('heat')}
        >
          Heatmap
        </button>
      </div>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      <Suspense fallback={<p className="hint">Chargement de la carte…</p>}>
        <RoutesMap
          routes={data?.routes ?? []}
          points={data?.points ?? []}
          places={data?.places ?? []}
          mode={mode}
          fitTo={fitTo}
          onViewChange={onViewChange}
        />
      </Suspense>
      {data && (
        <p className="hint" aria-live="polite">
          {data.total} activité{data.total > 1 ? 's' : ''} correspond{data.total > 1 ? 'ent' : ''}{' '}
          aux filtres, {shown} dans la zone affichée.
        </p>
      )}
      {data && <VisibleList data={data} />}
    </>
  )
}

function MapFiltersForm({
  filters,
  onChange,
}: {
  filters: MapFilters
  onChange: (change: Partial<MapFilters>) => void
}) {
  return (
    <div className="map-filters">
      <div className="segmented" role="group" aria-label="Sport">
        {SPORTS.map((sport) => (
          <button
            key={sport ?? 'all'}
            type="button"
            className="secondary"
            aria-pressed={filters.sport === sport}
            onClick={() => onChange({ sport })}
          >
            {sport ? SPORT_LABELS[sport] : 'Tous'}
          </button>
        ))}
      </div>
      <div className="segmented" role="group" aria-label="Période">
        {PERIOD_CHOICES.map((choice) => (
          <button
            key={choice.label}
            type="button"
            className="secondary"
            aria-pressed={filters.days === choice.days}
            onClick={() => onChange({ days: choice.days })}
          >
            {choice.label}
          </button>
        ))}
      </div>
      <div className="inline-fields">
        <label>
          Distance min (km)
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={filters.minKm}
            onChange={(event) => onChange({ minKm: event.target.value })}
          />
        </label>
        <label>
          Distance max (km)
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={filters.maxKm}
            onChange={(event) => onChange({ maxKm: event.target.value })}
          />
        </label>
      </div>
    </div>
  )
}

/** The activities in view, newest first: easier than tapping thin lines on a phone. */
function VisibleList({ data }: { data: MapRoutes }) {
  const rows: ActivityRow[] = [
    ...data.routes,
    ...data.points,
    ...data.places.flatMap((place) => place.activities),
  ]
  // ISO dates in UTC sort correctly as text.
  rows.sort((a, b) => b.start_time.localeCompare(a.start_time))
  if (rows.length === 0) {
    return <p className="hint">Aucune activité dans cette zone avec ces filtres.</p>
  }
  return (
    <section className="card" aria-labelledby="visible-title">
      <h2 id="visible-title">Dans la zone affichée</h2>
      <ActivityTable rows={rows.slice(0, LIST_LIMIT)} label="Activités dans la zone affichée" />
      {rows.length > LIST_LIMIT && (
        <p className="hint">
          Les {LIST_LIMIT} plus récentes sur {rows.length}. Zoome ou filtre pour voir les autres.
        </p>
      )}
    </section>
  )
}
