import { describe, expect, it } from 'vitest'

import type { HealthDay } from '../api/client'
import { acwrLabel, formatClock, mean, regularityLabel, trendPoints } from './health'

function day(date: string, sleepHours: number | null): HealthDay {
  return {
    day: date,
    sleep_s: sleepHours === null ? null : sleepHours * 3600,
    sleep_score: null,
    bedtime_min: null,
    wake_min: null,
    resting_hr: null,
    hrv_ms: null,
    weight_kg: null,
  }
}

describe('trendPoints', () => {
  it('averages the last days and skips missing values', () => {
    const days = [day('2026-10-01', 6), day('2026-10-02', null), day('2026-10-03', 8)]
    const points = trendPoints(days, (d) => (d.sleep_s === null ? null : d.sleep_s / 3600), 2)
    expect(points.map((p) => p.value)).toEqual([6, null, 8])
    // Window of 2 days: day 2 has only day 1's value, day 3 only its own.
    expect(points.map((p) => p.average)).toEqual([6, 6, 8])
    expect(points[0]?.time).toBe(Date.UTC(2026, 9, 1))
  })

  it('gives no average when the whole window is empty', () => {
    expect(trendPoints([day('2026-10-01', null)], () => null)[0]?.average).toBeNull()
  })
})

describe('wording helpers', () => {
  it('formats clock times around midnight', () => {
    expect(formatClock(-30)).toBe('23:30')
    expect(formatClock(15)).toBe('00:15')
    expect(formatClock(425)).toBe('07:05')
  })

  it('computes a mean ignoring missing values', () => {
    expect(mean([1, null, 3])).toBe(2)
    expect(mean([null])).toBeNull()
  })

  it('reads regularity and the load ratio', () => {
    expect(regularityLabel(20)).toBe('régulier')
    expect(regularityLabel(75)).toBe('irrégulier')
    expect(regularityLabel(null)).toBe('pas assez de nuits')
    expect(acwrLabel(1.0)).toBe('Dans tes habitudes.')
    expect(acwrLabel(1.8)).toMatch(/progressivement/)
    expect(acwrLabel(null)).toMatch(/historique/)
  })
})
