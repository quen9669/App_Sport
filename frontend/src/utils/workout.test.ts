// Unit tests for the way the steps of a run are written.
import { describe, expect, it } from 'vitest'

import type { RunWorkout } from '../api/client'
import { stepLength, workoutLines } from './workout'

const intervals: RunWorkout = {
  warmup: { duration_s: 900, distance_m: null, pace: 'easy' },
  blocks: [
    {
      repeats: 6,
      work: { duration_s: null, distance_m: 800, pace: 'interval' },
      recovery: { duration_s: 120, distance_m: null, pace: 'none' },
    },
  ],
  cooldown: { duration_s: 600, distance_m: null, pace: 'easy' },
}

describe('workout lines', () => {
  it('writes each step with its pace range', () => {
    const targets = {
      easy: { slow_s_per_km: 330, fast_s_per_km: 300 },
      interval: { slow_s_per_km: 245, fast_s_per_km: 235 },
    }
    expect(workoutLines(intervals, targets)).toEqual([
      'Échauffement · 15 min · 5:00-5:30 /km (endurance)',
      '6 × 800 m · 3:55-4:05 /km (fractionné (VMA)) · récup 2 min',
      'Retour au calme · 10 min · 5:00-5:30 /km (endurance)',
    ])
  })

  it('shows only the zone while the form is unknown', () => {
    expect(workoutLines(intervals, {})[1]).toBe('6 × 800 m · (fractionné (VMA)) · récup 2 min')
  })

  it('writes lengths in minutes, seconds, metres or km', () => {
    expect(stepLength({ duration_s: 90, distance_m: null, pace: 'none' })).toBe('1 min 30')
    expect(stepLength({ duration_s: 45, distance_m: null, pace: 'none' })).toBe('45 s')
    expect(stepLength({ duration_s: null, distance_m: 5000, pace: 'easy' })).toBe('5 km')
    expect(stepLength({ duration_s: null, distance_m: 1500, pace: 'easy' })).toBe('1,5 km')
  })
})
