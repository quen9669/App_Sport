// Helpers of the Santé page: chart points, averages and plain-French wording.
import type { HealthDay } from '../api/client'

export interface TrendPoint {
  date: string // "2026-10-18"
  time: number // milliseconds, the chart's x axis
  value: number | null // null = no data that day (the line shows a gap)
  average: number | null // rolling average of the last `windowDays` days
}

/**
 * One point per day for one metric, with a rolling average.
 * `days` are consecutive and sorted (the backend sends one entry per day), so
 * the average of a day is the mean of the values of that day and the
 * `windowDays - 1` previous entries, skipping the missing ones.
 */
export function trendPoints(
  days: HealthDay[],
  pick: (day: HealthDay) => number | null,
  windowDays = 7,
): TrendPoint[] {
  const values = days.map(pick)
  return days.map((day, index) => {
    const window = values.slice(Math.max(0, index - windowDays + 1), index + 1)
    return {
      date: day.day,
      time: Date.parse(`${day.day}T00:00:00Z`),
      value: values[index] ?? null,
      average: round(mean(window), 1),
    }
  })
}

/** Mean of the non-missing values, or null when there is none. */
export function mean(values: (number | null)[]): number | null {
  const present = values.filter((value): value is number => value !== null)
  if (present.length === 0) return null
  return present.reduce((sum, value) => sum + value, 0) / present.length
}

export function round(value: number | null, digits = 0): number | null {
  if (value === null) return null
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

/** -30 -> "23:30", 425 -> "07:05" (minutes from midnight, negative the evening before). */
export function formatClock(minutes: number): string {
  const inDay = ((Math.round(minutes) % 1440) + 1440) % 1440
  const hours = String(Math.floor(inDay / 60)).padStart(2, '0')
  return `${hours}:${String(inDay % 60).padStart(2, '0')}`
}

/** How regular a schedule is, from the standard deviation of bed or wake times. */
export function regularityLabel(sdMinutes: number | null): string {
  if (sdMinutes === null) return 'pas assez de nuits'
  if (sdMinutes <= 30) return 'régulier'
  if (sdMinutes <= 60) return 'assez régulier'
  return 'irrégulier'
}

/** Plain-French reading of the acute:chronic ratio. Never a medical statement. */
export function acwrLabel(acwr: number | null): string {
  if (acwr === null) return 'Pas encore assez d’historique (5 semaines).'
  if (acwr < 0.8) return 'Semaine plus légère que d’habitude.'
  if (acwr <= 1.3) return 'Dans tes habitudes.'
  if (acwr <= 1.5) return 'Un peu plus que d’habitude.'
  return 'Nettement plus que d’habitude : augmente progressivement.'
}
