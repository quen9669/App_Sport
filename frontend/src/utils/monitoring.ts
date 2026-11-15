// Words and formats of the Monitoring page (Réglages), kept apart from the
// component so the page file only exports components (fast refresh).
import type { MonitoringStatus } from '../api/client'
import { formatNumber } from './format'

/** Words for each status: colour is never the only clue. */
export const MONITORING_LABELS: Record<MonitoringStatus, string> = {
  ok: 'OK',
  warning: 'À surveiller',
  error: 'Problème',
  unknown: 'Pas encore de données',
}

/** "il y a 1 h 52", "il y a 3 j", from an ISO date and the time of the check. */
export function formatAgo(iso: string, nowIso: string): string {
  const minutes = Math.max(0, Math.round((Date.parse(nowIso) - Date.parse(iso)) / 60_000))
  if (minutes < 1) return "à l'instant"
  if (minutes < 60) return `il y a ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `il y a ${hours} h ${String(minutes % 60).padStart(2, '0')}`
  return `il y a ${Math.floor(hours / 24)} j`
}

/** "214 Mo", "1,2 Go" (powers of 1024, like Docker's limits). */
export function formatBytes(bytes: number): string {
  const mb = bytes / 1024 / 1024
  if (mb < 1) return `${Math.max(1, Math.round(bytes / 1024))} Ko`
  if (mb < 1024) return `${Math.round(mb)} Mo`
  return `${formatNumber(mb / 1024)} Go`
}
