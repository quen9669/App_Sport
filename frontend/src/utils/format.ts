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
