// Detail of one activity: key numbers, the route on a map, and the altitude,
// pace and heart-rate charts. Moving a finger on a chart moves a dot on the map.
// Sessions without GPS show their place (a gym), which can be changed here.
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  ApiError,
  fetchActivity,
  fetchPlaces,
  setActivityPlace,
  type ActivityDetail,
  type Place,
} from '../api/client'
import {
  formatKm,
  positionAt,
  rowsByDistance,
  seriesRows,
  SPORT_LABELS,
  speedText,
} from '../utils/activity'
import { CATEGORY_LABELS, formatDateTime, formatDuration, SOURCE_LABELS } from '../utils/format'

// Loaded on demand: Leaflet and Recharts are only downloaded when needed.
const ActivityMap = lazy(() => import('../components/ActivityMap'))
const DetailCharts = lazy(() => import('../components/DetailCharts'))

export default function ActivityPage() {
  const id = Number(useParams().id)
  const [activity, setActivity] = useState<ActivityDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchActivity(id)
      .then((data) => {
        if (!cancelled) setActivity(data)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const missing = err instanceof ApiError && err.status === 404
        setError(missing ? 'Cette activité n’existe pas.' : 'Impossible de charger l’activité.')
      })
    return () => {
      cancelled = true
    }
  }, [id])

  const rows = useMemo(
    () => (activity ? seriesRows(activity.series, activity.sport) : []),
    [activity],
  )

  if (error) {
    return (
      <>
        <p className="field-error" role="alert">
          {error}
        </p>
        <Link to="/carte">Retour à la carte</Link>
      </>
    )
  }
  if (!activity) return <p className="hint">Chargement…</p>

  const hasMap = activity.polyline !== null || activity.place !== null
  return (
    <>
      <h1>{activity.name}</h1>
      <p className="subtitle">
        {SPORT_LABELS[activity.sport]} · {CATEGORY_LABELS[activity.category] ?? activity.category} ·{' '}
        {formatDateTime(activity.start_time)} · {SOURCE_LABELS[activity.source] ?? activity.source}
      </p>

      <ActivityStats activity={activity} />

      {hasMap && (
        <Suspense fallback={<p className="hint">Chargement de la carte…</p>}>
          <ActivityMap
            polyline={activity.polyline}
            place={activity.place}
            sport={activity.sport}
            marker={positionAt(activity.series, active)}
          />
        </Suspense>
      )}
      {activity.polyline === null && (
        <PlaceChoice activity={activity} onChange={(updated) => setActivity(updated)} />
      )}

      {rows.length > 1 ? (
        <Suspense fallback={<p className="hint">Chargement des graphiques…</p>}>
          <DetailCharts
            rows={rows}
            sport={activity.sport}
            byDistance={rowsByDistance(activity.series)}
            onActive={setActive}
          />
        </Suspense>
      ) : (
        <p className="hint">Pas de courbes détaillées pour cette activité.</p>
      )}
      <p>
        <Link to="/carte">Retour à la carte</Link>
      </p>
    </>
  )
}

function ActivityStats({ activity }: { activity: ActivityDetail }) {
  const speed = speedText(activity.sport, activity.average_speed_mps)
  const items: [string, string | null][] = [
    ['Distance', activity.distance_m !== null ? formatKm(activity.distance_m) : null],
    ['Durée', formatDuration(activity.moving_time_s ?? activity.elapsed_time_s)],
    [activity.sport === 'run' ? 'Allure moy.' : 'Vitesse moy.', speed],
    [
      'Dénivelé +',
      activity.elevation_gain_m !== null ? `${Math.round(activity.elevation_gain_m)} m` : null,
    ],
    [
      'FC moy.',
      activity.average_heartrate !== null ? `${Math.round(activity.average_heartrate)} bpm` : null,
    ],
    [
      'FC max',
      activity.max_heartrate !== null ? `${Math.round(activity.max_heartrate)} bpm` : null,
    ],
  ]
  return (
    <dl className="stats">
      {items
        .filter(([, value]) => value !== null)
        .map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
    </dl>
  )
}

/** Where a session without GPS happened: the default place, or one chosen by hand. */
function PlaceChoice({
  activity,
  onChange,
}: {
  activity: ActivityDetail
  onChange: (updated: ActivityDetail) => void
}) {
  const [places, setPlaces] = useState<Place[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchPlaces()
      .then((list) => {
        if (!cancelled) setPlaces(list)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger tes lieux.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function choose(value: string) {
    setError(null)
    try {
      onChange(await setActivityPlace(activity.id, value === '' ? null : Number(value)))
    } catch {
      setError('Le lieu n’a pas pu être enregistré.')
    }
  }

  const place = activity.place
  return (
    <div className="card">
      <label>
        Lieu de la séance (pas de GPS)
        <select
          value={place?.chosen ? String(place.id) : ''}
          onChange={(event) => void choose(event.target.value)}
        >
          <option value="">
            Lieu par défaut{place && !place.chosen ? ` (${place.name})` : ''}
          </option>
          {places.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <p className="hint">
        Tes lieux se gèrent sur la page <Link to="/carte">Carte</Link>, section « Mes lieux ».
      </p>
    </div>
  )
}
