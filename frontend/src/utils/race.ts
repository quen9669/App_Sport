// Display and input helpers for the race page: race times, paces, zone names.
import type { Feasibility, PaceZoneKey } from '../api/client'

/** Race clock: "49:12" under an hour, "1:31:35" above (rounded to the second). */
export function formatRaceTime(seconds: number): string {
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = String(m).padStart(h > 0 ? 2 : 1, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Pace in minutes per km: 300 -> "5:00". */
export function formatPace(secondsPerKm: number): string {
  const total = Math.round(secondsPerKm)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/**
 * "50:00", "49:30" or "1:45:00" typed by hand -> seconds, or null if it is not a time.
 * Two parts are minutes and seconds; three are hours, minutes, seconds.
 */
export function parseRaceTime(text: string): number | null {
  const match = /^(\d{1,3}):(\d{1,2})(?::(\d{1,2}))?$/.exec(text.trim())
  if (!match) return null
  const numbers = match
    .slice(1)
    .filter((part) => part !== undefined)
    .map(Number)
  // Everything after the first part (minutes, seconds) must stay below 60.
  if (numbers.slice(1).some((n) => n >= 60)) return null
  return numbers.reduce((total, n) => total * 60 + n, 0)
}

export const ZONE_LABELS: Record<PaceZoneKey, string> = {
  easy: 'Facile (footing)',
  marathon: 'Allure marathon',
  threshold: 'Seuil',
  interval: 'Intervalles (VMA)',
  repetition: 'Répétitions',
}

export const ZONE_HINTS: Record<PaceZoneKey, string> = {
  easy: 'la majorité des sorties, on peut parler',
  marathon: 'longues portions à allure de course longue',
  threshold: 'tempo de 20 à 30 min, « confortablement dur »',
  interval: 'fractions de 3 à 5 min, récupération égale',
  repetition: 'fractions courtes et rapides (200 à 400 m)',
}

export const FEASIBILITY_LABELS: Record<Feasibility, string> = {
  realistic: 'Réaliste',
  ambitious: 'Ambitieux',
  unlikely: 'Peu probable',
}

/** The standard race distances of the form, in metres. */
export const RACE_DISTANCES = [
  { label: '5 km', meters: 5000 },
  { label: '10 km', meters: 10_000 },
  { label: 'Semi-marathon', meters: 21_097.5 },
  { label: 'Marathon', meters: 42_195 },
]
