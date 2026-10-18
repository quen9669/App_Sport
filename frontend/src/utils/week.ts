// The numbers of the "Ma semaine" tiles, computed from the week's activities.
import type { WeekActivity } from '../api/client'

export interface WeekTotals {
  sessions: number
  distanceKm: number
  activeSeconds: number
}

/** Hidden activities never count (same rule as the goals). */
export function weekTotals(activities: WeekActivity[]): WeekTotals {
  const counted = activities.filter((activity) => !activity.hidden)
  return {
    sessions: counted.length,
    distanceKm: counted.reduce((sum, a) => sum + (a.distance_m ?? 0), 0) / 1000,
    // Moving time when the watch measured it, else the elapsed time.
    activeSeconds: counted.reduce((sum, a) => sum + (a.moving_time_s ?? a.elapsed_time_s), 0),
  }
}
