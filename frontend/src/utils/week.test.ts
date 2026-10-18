import { describe, expect, it } from 'vitest'

import type { WeekActivity } from '../api/client'
import { weekTotals } from './week'

function activity(fields: Partial<WeekActivity>): WeekActivity {
  return {
    id: 1,
    name: 'Footing',
    sport: 'run',
    sport_type: 'running',
    start_time: '2026-10-13T07:00:00Z',
    distance_m: 10_000,
    moving_time_s: 3000,
    elapsed_time_s: 3100,
    city: null,
    country_code: null,
    average_heartrate: null,
    max_heartrate: null,
    category: 'cardio',
    automatic_category: 'cardio',
    source: 'garmin',
    hidden: false,
    possible_duplicate: false,
    ...fields,
  }
}

describe('weekTotals', () => {
  it('adds up distance and active time, without hidden activities', () => {
    const totals = weekTotals([
      activity({}),
      activity({ id: 2, distance_m: null, moving_time_s: null, elapsed_time_s: 3600 }),
      activity({ id: 3, hidden: true }),
    ])
    expect(totals).toEqual({ sessions: 2, distanceKm: 10, activeSeconds: 6600 })
  })
})
