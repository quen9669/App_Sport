// Weight chart helpers.
import type { BodyMetric } from '../api/client'

export interface WeightPoint {
  date: string // "2026-10-18"
  time: number // milliseconds, used as the chart's x axis
  weight: number
  average: number // 7-day rolling average
}

const DAY_MS = 24 * 60 * 60 * 1000

function toTime(isoDate: string): number {
  return Date.parse(`${isoDate}T00:00:00Z`)
}

/**
 * Add a 7-day rolling average to each weigh-in: the mean of the weigh-ins of
 * that day and the 6 days before. It smooths day-to-day noise (water, meals).
 * Based on dates, not on a count of points, so missing days don't distort it.
 * `metrics` must be sorted from oldest to newest (the backend does it).
 */
export function withRollingAverage(metrics: BodyMetric[], windowDays = 7): WeightPoint[] {
  return metrics.map((metric, index) => {
    const time = toTime(metric.measured_on)
    let sum = 0
    let count = 0
    for (let i = index; i >= 0; i--) {
      const previous = metrics[i]
      if (!previous || time - toTime(previous.measured_on) >= windowDays * DAY_MS) break
      sum += previous.weight_kg
      count += 1
    }
    return {
      date: metric.measured_on,
      time,
      weight: metric.weight_kg,
      average: Math.round((sum / count) * 10) / 10,
    }
  })
}
