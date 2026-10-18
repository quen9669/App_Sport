// Helpers for the map and the activity detail: routes, sports, pace and speed.
import type { ActivitySeries, SportGroup } from '../api/client'
import { formatNumber } from './format'

export type LatLng = [number, number]

export const SPORT_LABELS: Record<SportGroup, string> = {
  run: 'Course',
  ride: 'Vélo',
  walk: 'Marche',
  strength: 'Muscu',
  other: 'Divers',
}

export const SPORT_EMOJIS: Record<SportGroup, string> = {
  run: '🏃',
  ride: '🚴',
  walk: '🚶',
  strength: '🏋️',
  other: '🤸',
}

// One colour per sport, chosen by FRANKS: red running, green cycling, purple
// walking, yellow strength, orange the rest. Defined in theme.css (with a
// lighter step for the dark theme); the map and the tables use the same ones.
export const SPORT_COLOR_VARS: Record<SportGroup, string> = {
  run: '--sport-run',
  ride: '--sport-ride',
  walk: '--sport-walk',
  strength: '--sport-strength',
  other: '--sport-other',
}

/**
 * The flag emoji of a country: "LU" -> 🇱🇺. A flag is two "regional indicator"
 * letters, which sit at a fixed distance from A-Z in Unicode. Windows does not
 * draw them by itself: main.tsx loads a small font for that (no external request).
 */
export function flagEmoji(code: string | null): string {
  if (!code || !/^[A-Za-z]{2}$/.test(code)) return ''
  const base = 0x1f1e6 - 'A'.charCodeAt(0)
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => base + c.charCodeAt(0)))
}

/** Country names in French, from the browser ("LU" -> "Luxembourg"). */
export function countryName(code: string | null): string {
  if (!code) return ''
  try {
    return new Intl.DisplayNames(['fr'], { type: 'region' }).of(code.toUpperCase()) ?? code
  } catch {
    return code
  }
}

/** A distance only makes sense when the activity moved somewhere. */
export function shownDistance(row: { sport: SportGroup; distance_m: number | null }) {
  return row.sport === 'strength' || !row.distance_m ? null : row.distance_m
}

/**
 * The colour behind a CSS variable, e.g. "--series-1" -> "#2a78d6".
 * Leaflet draws on a canvas, which does not understand `var(--x)`.
 */
export function cssColor(variable: string, fallback = '#2a78d6'): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
  return value || fallback
}

/**
 * Decode a Google "encoded polyline" (same format as the backend's
 * app/services/polyline.py): each point is the difference from the previous
 * one, rounded to 5 decimals, written as printable characters.
 */
export function decodePolyline(encoded: string): LatLng[] {
  const points: LatLng[] = []
  let index = 0
  let lat = 0
  let lng = 0
  while (index < encoded.length) {
    const deltas: number[] = []
    for (let part = 0; part < 2; part++) {
      let shift = 0
      let result = 0
      let byte: number
      do {
        byte = encoded.charCodeAt(index++) - 63
        result |= (byte & 0x1f) << shift
        shift += 5
      } while (byte >= 0x20)
      deltas.push(result & 1 ? ~(result >> 1) : result >> 1)
    }
    lat += deltas[0] ?? 0
    lng += deltas[1] ?? 0
    points.push([lat / 1e5, lng / 1e5])
  }
  return points
}

/** "10,2 km" from metres. */
export function formatKm(metres: number): string {
  return `${formatNumber(metres / 1000, metres < 10_000 ? 2 : 1)} km`
}

/** Minutes per km from metres per second (null when not moving). */
export function paceMinPerKm(mps: number | null): number | null {
  return mps && mps > 0.5 ? 1000 / mps / 60 : null
}

/** "5:12 /km" from minutes per km. */
export function formatPace(minPerKm: number): string {
  let minutes = Math.floor(minPerKm)
  let seconds = Math.round((minPerKm - minutes) * 60)
  if (seconds === 60) {
    minutes += 1
    seconds = 0
  }
  return `${minutes}:${String(seconds).padStart(2, '0')} /km`
}

/** Running is read as a pace (min/km), everything else as a speed (km/h). */
export function speedText(sport: SportGroup, mps: number | null): string | null {
  if (!mps) return null
  if (sport === 'run') {
    const pace = paceMinPerKm(mps)
    return pace === null ? null : formatPace(pace)
  }
  return `${formatNumber(mps * 3.6)} km/h`
}

/** One row per sample, ready for the detail charts (x axis in km when known, else minutes). */
export interface SeriesRow {
  index: number
  x: number
  altitude: number | null
  heartrate: number | null
  speed: number | null // min/km for running, km/h otherwise
}

export function seriesRows(series: ActivitySeries, sport: SportGroup): SeriesRow[] {
  const byDistance = series.distance_m.some((d) => d !== null)
  return series.time_s.map((time, index) => {
    const mps = series.speed_mps[index] ?? null
    const distance = series.distance_m[index] ?? null
    return {
      index,
      x: byDistance ? (distance ?? 0) / 1000 : time / 60,
      altitude: series.altitude_m[index] ?? null,
      heartrate: series.heartrate[index] ?? null,
      speed: sport === 'run' ? paceMinPerKm(mps) : mps === null ? null : mps * 3.6,
    }
  })
}

/** True when the x axis of `seriesRows` is a distance (km), false for minutes. */
export const rowsByDistance = (series: ActivitySeries) => series.distance_m.some((d) => d !== null)

/** Map filters: period choices, in days (null = all the history). */
export const PERIOD_CHOICES: { label: string; days: number | null }[] = [
  { label: '14 jours', days: 14 },
  { label: '30 jours', days: 30 },
  { label: '3 mois', days: 90 },
  { label: '1 an', days: 365 },
  { label: 'Tout', days: null },
]

/** GPS position of sample `index`, or the nearest sample before it that has one. */
export function positionAt(series: ActivitySeries, index: number | null): LatLng | null {
  if (index === null) return null
  for (let i = Math.min(index, series.latlng.length - 1); i >= 0; i--) {
    const point = series.latlng[i]
    if (point) return point
  }
  return null
}

/**
 * Two numbers from "49.6004, 6.1319" (as map apps copy them), "49,6004; 6,1319"
 * or "49,6004 6,1319" (French decimal comma). Null if it is not a valid position.
 */
export function parseCoordinates(text: string): [number, number] | null {
  const trimmed = text.trim()
  // With a decimal comma, the comma cannot also separate the two numbers.
  const separator = trimmed.includes(';')
    ? ';'
    : trimmed.includes('.') || trimmed.split(',').length === 2
      ? ','
      : /\s+/
  const numbers = trimmed.split(separator).map((part) => Number(part.trim().replace(',', '.')))
  if (numbers.length !== 2 || numbers.some((n) => Number.isNaN(n))) return null
  const [lat, lng] = numbers as [number, number]
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return [lat, lng]
}
