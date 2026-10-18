// The map of every activity: routes coloured by sport, or a heatmap, plus the
// places of the sessions without GPS (gyms). Loaded on demand (React.lazy in
// MapPage): Leaflet is only downloaded when the map is opened.
//
// Leaflet draws on a <canvas> (`preferCanvas`): hundreds of routes stay fluid,
// even on a phone. The tiles (the background map) come from OpenStreetMap; the
// routes themselves never leave the app.
import 'leaflet/dist/leaflet.css'

import { useEffect, useMemo } from 'react'
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { Link } from 'react-router-dom'

import type { Bounds, MapPlace, MapPoint, MapRoute } from '../api/client'
import {
  cssColor,
  decodePolyline,
  formatKm,
  SPORT_COLOR_VARS,
  SPORT_LABELS,
  speedText,
} from '../utils/activity'
import { formatDateTime, formatDuration } from '../utils/format'
import { OSM_ATTRIBUTION, OSM_TILES } from '../utils/tiles'

// Luxembourg city: where the map opens before the activities are known.
const START_CENTER: [number, number] = [49.61, 6.13]
const START_ZOOM = 12
// Heatmap: every route drawn thick and almost transparent, in one warm colour.
// Where routes overlap the colour adds up, so frequent paths stand out.
const HEAT_COLOR = '#ff4d00'
const HEAT_OPACITY = 0.18

// Pixels: the biggest a gym circle gets, whatever its number of sessions.
const MAX_PLACE_RADIUS = 16

export type MapMode = 'routes' | 'heat'

interface Props {
  routes: MapRoute[]
  points: MapPoint[] // activities with a start point but no route yet
  places: MapPlace[]
  mode: MapMode
  fitTo: Bounds | null // frame these bounds when they change (new filters)
  onViewChange: (bbox: string, zoom: number) => void
}

export default function RoutesMap({ routes, points, places, mode, fitTo, onViewChange }: Props) {
  return (
    <MapContainer
      className="map"
      center={START_CENTER}
      zoom={START_ZOOM}
      preferCanvas
      scrollWheelZoom
    >
      <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} />
      <ViewWatcher onViewChange={onViewChange} />
      <FitBounds bounds={fitTo} />
      {routes.map((route) => (
        <RouteLine key={route.id} route={route} heat={mode === 'heat'} />
      ))}
      {points.map((point) => (
        <StartDot key={point.id} point={point} heat={mode === 'heat'} />
      ))}
      {places.map((place) => (
        <PlaceMarker key={place.id} place={place} heat={mode === 'heat'} />
      ))}
    </MapContainer>
  )
}

function RouteLine({ route, heat }: { route: MapRoute; heat: boolean }) {
  const positions = useMemo(() => decodePolyline(route.polyline), [route.polyline])
  const style = heat
    ? { color: HEAT_COLOR, weight: 6, opacity: HEAT_OPACITY }
    : { color: cssColor(SPORT_COLOR_VARS[route.sport]), weight: 3, opacity: 0.8 }
  return (
    <Polyline positions={positions} pathOptions={style}>
      <Popup>
        <RouteSummary route={route} />
      </Popup>
    </Polyline>
  )
}

/** An activity known only by its start point (its route is not imported yet). */
function StartDot({ point, heat }: { point: MapPoint; heat: boolean }) {
  const color = heat ? HEAT_COLOR : cssColor(SPORT_COLOR_VARS[point.sport])
  return (
    <CircleMarker
      center={[point.latitude, point.longitude]}
      radius={5}
      pathOptions={{
        color,
        fillColor: color,
        fillOpacity: heat ? HEAT_OPACITY * 2 : 0.7,
        weight: 1,
      }}
    >
      <Popup>
        <div className="map-popup">
          <strong>{point.name}</strong>
          <div className="hint">
            {SPORT_LABELS[point.sport]} · {formatDateTime(point.start_time)}
          </div>
          <div className="hint">Départ seulement : le tracé n’est pas encore importé.</div>
          <Link to={`/activites/${point.id}`}>Voir le détail</Link>
        </div>
      </Popup>
    </CircleMarker>
  )
}

function RouteSummary({ route }: { route: MapRoute }) {
  const speed = speedText(route.sport, route.average_speed_mps)
  return (
    <div className="map-popup">
      <strong>{route.name}</strong>
      <div className="hint">
        {SPORT_LABELS[route.sport]} · {formatDateTime(route.start_time)}
      </div>
      <ul>
        {route.distance_m !== null && <li>{formatKm(route.distance_m)}</li>}
        <li>{formatDuration(route.moving_time_s ?? route.elapsed_time_s)}</li>
        {speed && <li>{speed}</li>}
        {route.elevation_gain_m !== null && <li>D+ {Math.round(route.elevation_gain_m)} m</li>}
        {route.average_heartrate !== null && (
          <li>FC moy. {Math.round(route.average_heartrate)} bpm</li>
        )}
      </ul>
      <Link to={`/activites/${route.id}`}>Voir le détail</Link>
    </div>
  )
}

function PlaceMarker({ place, heat }: { place: MapPlace; heat: boolean }) {
  // The circle grows with the number of sessions (area, not radius, is what the
  // eye compares), up to a cap: a year of gym sessions must not hide the map.
  const radius = Math.min(6 + 2 * Math.sqrt(place.activity_count), MAX_PLACE_RADIUS)
  const color = heat ? HEAT_COLOR : cssColor(SPORT_COLOR_VARS.strength)
  return (
    <CircleMarker
      center={[place.latitude, place.longitude]}
      radius={radius}
      pathOptions={{ color, fillColor: color, fillOpacity: heat ? 0.35 : 0.5, weight: 2 }}
    >
      <Popup>
        <div className="map-popup">
          <strong>{place.name}</strong>
          <div className="hint">
            {place.activity_count} séance{place.activity_count > 1 ? 's' : ''} sans GPS
          </div>
          <ul>
            {place.activities.slice(0, 5).map((activity) => (
              <li key={activity.id}>
                <Link to={`/activites/${activity.id}`}>{activity.name}</Link>{' '}
                <span className="hint">{formatDateTime(activity.start_time)}</span>
              </li>
            ))}
          </ul>
        </div>
      </Popup>
    </CircleMarker>
  )
}

/** Tell the page what is visible, after each move or zoom (and once at the start). */
function ViewWatcher({ onViewChange }: { onViewChange: Props['onViewChange'] }) {
  const map = useMapEvents({
    moveend: () => onViewChange(map.getBounds().toBBoxString(), map.getZoom()),
  })
  useEffect(() => {
    onViewChange(map.getBounds().toBBoxString(), map.getZoom())
  }, [map, onViewChange])
  return null
}

/** Frame `bounds` whenever a new value arrives (not on every render). */
function FitBounds({ bounds }: { bounds: Bounds | null }) {
  const map = useMap()
  useEffect(() => {
    if (!bounds) return
    map.fitBounds(
      [
        [bounds.south, bounds.west],
        [bounds.north, bounds.east],
      ],
      { padding: [24, 24], maxZoom: 15, animate: false },
    )
  }, [map, bounds])
  return null
}
