// Display helpers: dates in Luxembourg time, French wording.

const dateTimeFormat = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Luxembourg',
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

/** "18/10 09:42" from an ISO date sent by the backend (always in UTC). */
export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

export const SOURCE_LABELS: Record<string, string> = {
  strava: 'Strava',
  garmin: 'Garmin',
  file_import: 'Import de fichier',
  synthetic: 'Données de test',
}

export const KIND_LABELS: Record<string, string> = {
  manual: 'manuelle',
  scheduled: 'planifiée',
  backfill: 'historique',
}

export const STATUS_LABELS: Record<string, string> = {
  running: 'En cours',
  success: 'Réussie',
  partial: 'Partielle',
  failed: 'Échec',
}

export const CATEGORY_LABELS: Record<string, string> = {
  strength: 'Musculation',
  cardio: 'Cardio',
  other: 'Autre',
}

export const GOAL_KIND_LABELS: Record<string, string> = {
  strength_sessions: 'Séances de musculation',
  cardio_sessions: 'Séances de cardio',
  active_minutes: 'Minutes d’activité',
  distance_km: 'Kilomètres',
  training_load: 'Charge d’entraînement',
  intensity_minutes: 'Minutes d’intensité (Garmin)',
}

export const GOAL_UNITS: Record<string, string> = {
  strength_sessions: 'séances',
  cardio_sessions: 'séances',
  active_minutes: 'min',
  distance_km: 'km',
  training_load: 'points',
  intensity_minutes: 'min',
}

export const SPORT_LABELS: Record<string, string> = {
  run: 'course',
  ride: 'vélo',
}

/** "Séances de musculation", or "Kilomètres (course)" for a distance goal limited to one sport. */
export function goalTitle(kind: string, sport: string | null): string {
  const title = GOAL_KIND_LABELS[kind] ?? kind
  return sport ? `${title} (${SPORT_LABELS[sport] ?? sport})` : title
}

const dayFormat = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Luxembourg',
  weekday: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/** "sam. 17 09:00" for the list of the week's activities. */
export function formatDayTime(iso: string): string {
  return dayFormat.format(new Date(iso))
}

/** "18 oct." from a plain "2026-10-18" date (no time, no timezone shift). */
export function formatShortDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number) as [number, number, number]
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('fr-FR', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
  })
}

/** "1 h 05" or "45 min". */
export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`
}

/** French decimal comma: 79.6 -> "79,6". */
export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString('fr-FR', { maximumFractionDigits: digits })
}

/** Today's date as "2026-10-18" in Luxembourg time (not UTC: at 00:30 it is already tomorrow). */
export function todayIso(now: Date = new Date()): string {
  // The "sv-SE" locale happens to format dates as YYYY-MM-DD.
  return now.toLocaleDateString('sv-SE', { timeZone: 'Europe/Luxembourg' })
}
