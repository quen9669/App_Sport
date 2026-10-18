import { describe, expect, it } from 'vitest'

import type { ActivitySeries } from '../api/client'
import {
  decodePolyline,
  flagEmoji,
  formatPace,
  parseCoordinates,
  positionAt,
  seriesRows,
  shownDistance,
  speedText,
} from './activity'

const series: ActivitySeries = {
  time_s: [0, 60, 120],
  distance_m: [0, 200, 400],
  altitude_m: [300, null, 310],
  heartrate: [120, 130, 140],
  speed_mps: [null, 10 / 3, 10 / 3],
  latlng: [[49.6, 6.1], null, [49.61, 6.12]],
}

describe('activity helpers', () => {
  it('decodes an encoded polyline (example from the Google specification)', () => {
    expect(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')).toEqual([
      [38.5, -120.2],
      [40.7, -120.95],
      [43.252, -126.453],
    ])
    expect(decodePolyline('')).toEqual([])
  })

  it('shows a pace for running and a speed for the rest', () => {
    expect(formatPace(5.2)).toBe('5:12 /km')
    expect(formatPace(4.999)).toBe('5:00 /km') // 4:59.9 rounds up to 5:00, not 4:60
    expect(speedText('run', 1000 / 300)).toBe('5:00 /km')
    expect(speedText('ride', 10)).toBe('36 km/h')
    expect(speedText('run', null)).toBeNull()
  })

  it('builds chart rows in km with the pace in min/km for a run', () => {
    const rows = seriesRows(series, 'run')
    expect(rows.map((r) => r.x)).toEqual([0, 0.2, 0.4])
    expect(rows[0]?.speed).toBeNull()
    expect(rows[1]?.speed).toBeCloseTo(5)
    expect(rows[1]?.altitude).toBeNull()
  })

  it('finds the map position of a chart point, using the last known one', () => {
    expect(positionAt(series, 0)).toEqual([49.6, 6.1])
    expect(positionAt(series, 1)).toEqual([49.6, 6.1]) // no GPS at this sample
    expect(positionAt(series, 2)).toEqual([49.61, 6.12])
    expect(positionAt(series, null)).toBeNull()
  })

  it('reads coordinates copied from a map app, with a dot or a decimal comma', () => {
    expect(parseCoordinates('49.600415, 6.131926')).toEqual([49.600415, 6.131926])
    expect(parseCoordinates('49,6004; 6,1319')).toEqual([49.6004, 6.1319])
    expect(parseCoordinates('49,6004 6,1319')).toEqual([49.6004, 6.1319])
    expect(parseCoordinates('95, 6')).toBeNull()
    expect(parseCoordinates('Luxembourg')).toBeNull()
    expect(parseCoordinates('')).toBeNull()
  })
})

describe('flags and distances of the activity tables', () => {
  it('turns a country code into its flag emoji', () => {
    expect(flagEmoji('LU')).toBe('🇱🇺')
    expect(flagEmoji('fr')).toBe('🇫🇷')
    expect(flagEmoji(null)).toBe('')
    expect(flagEmoji('XYZ')).toBe('')
  })

  it('shows no distance for an activity that moved nowhere', () => {
    expect(shownDistance({ sport: 'strength', distance_m: 1200 })).toBeNull()
    expect(shownDistance({ sport: 'other', distance_m: null })).toBeNull()
    expect(shownDistance({ sport: 'run', distance_m: 5000 })).toBe(5000)
  })
})
