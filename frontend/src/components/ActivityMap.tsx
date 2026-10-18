// Map of one activity: its route (or its place, for a session without GPS),
// and a dot that follows the finger on the charts below.
// Loaded on demand (React.lazy in ActivityPage), like the main map.
import 'leaflet/dist/leaflet.css'

import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet'

import type { SportGroup } from '../api/client'
import { cssColor, decodePolyline, SPORT_COLOR_VARS, type LatLng } from '../utils/activity'
import { OSM_ATTRIBUTION, OSM_TILES } from '../utils/tiles'

interface Props {
  polyline: string | null
  place: { latitude: number; longitude: number } | null
  sport: SportGroup
  marker: LatLng | null // position matching the point under the finger on a chart
}

export default function ActivityMap({ polyline, place, sport, marker }: Props) {
  const route = useMemo(() => (polyline ? decodePolyline(polyline) : []), [polyline])
  const color = cssColor(SPORT_COLOR_VARS[sport])
  const start = route[0]
  const center: LatLng = start ?? (place ? [place.latitude, place.longitude] : [49.61, 6.13])
  return (
    <MapContainer className="map map--detail" center={center} zoom={15} preferCanvas>
      <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} />
      {route.length > 1 && (
        <>
          <FitRoute route={route} />
          <Polyline positions={route} pathOptions={{ color, weight: 4, opacity: 0.9 }} />
          {start && <CircleMarker center={start} radius={6} pathOptions={endStyle('#16a34a')} />}
          <CircleMarker
            center={route.at(-1) ?? center}
            radius={6}
            pathOptions={endStyle('#dc2626')}
          />
        </>
      )}
      {route.length < 2 && place && (
        <CircleMarker
          center={[place.latitude, place.longitude]}
          radius={12}
          pathOptions={{ color, fillColor: color, fillOpacity: 0.5 }}
        />
      )}
      {marker && (
        <CircleMarker
          center={marker}
          radius={7}
          pathOptions={{ color: '#ffffff', weight: 3, fillColor: color, fillOpacity: 1 }}
        />
      )}
    </MapContainer>
  )
}

// Start (green) and finish (red): white border so they stay visible on the route.
const endStyle = (fill: string) => ({
  color: '#ffffff',
  weight: 2,
  fillColor: fill,
  fillOpacity: 1,
})

function FitRoute({ route }: { route: LatLng[] }) {
  const map = useMap()
  useEffect(() => {
    map.fitBounds(route, { padding: [16, 16], animate: false })
  }, [map, route])
  return null
}
