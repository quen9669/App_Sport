import { describe, expect, it } from 'vitest'

import type { BodyMetric } from '../api/client'
import { withRollingAverage } from './weight'

const metric = (measured_on: string, weight_kg: number): BodyMetric => ({
  id: 0,
  measured_on,
  weight_kg,
  body_fat_pct: null,
  waist_cm: null,
})

describe('withRollingAverage', () => {
  it('averages the weigh-ins of the last 7 days, by date', () => {
    const points = withRollingAverage([
      metric('2026-10-01', 80),
      metric('2026-10-03', 81),
      metric('2026-10-07', 79), // 1 to 7 October: 7 days, all three count
      metric('2026-10-08', 78), // 1 October is now 7 days old: dropped
    ])
    expect(points.map((p) => p.average)).toEqual([80, 80.5, 80, 79.3])
  })
})
