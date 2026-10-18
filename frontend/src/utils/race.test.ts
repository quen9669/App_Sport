import { describe, expect, it } from 'vitest'

import { formatPace, formatRaceTime, parseRaceTime } from './race'

describe('race helpers', () => {
  it('formats race times and paces', () => {
    expect(formatRaceTime(2952.4)).toBe('49:12')
    expect(formatRaceTime(5495)).toBe('1:31:35')
    expect(formatRaceTime(3600)).toBe('1:00:00')
    expect(formatPace(300)).toBe('5:00')
    expect(formatPace(338.6)).toBe('5:39')
  })

  it('reads a time typed by hand', () => {
    expect(parseRaceTime('50:00')).toBe(3000)
    expect(parseRaceTime(' 49:30 ')).toBe(2970)
    expect(parseRaceTime('1:45:00')).toBe(6300)
    expect(parseRaceTime('50')).toBeNull()
    expect(parseRaceTime('49:75')).toBeNull()
    expect(parseRaceTime('abc')).toBeNull()
  })
})
