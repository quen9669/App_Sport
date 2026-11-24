import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fakeBackend } from '../test/fakeBackend'
import ActivityCalendar from './ActivityCalendar'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ActivityCalendar', () => {
  it('shows the streak and one dot per activity of the last 30 days', async () => {
    fakeBackend({
      'GET /api/activity-calendar': {
        streak_weeks: 12,
        today: '2026-11-24',
        monday: '2026-11-23',
        activities: [
          { id: 1, day: '2026-11-23', sport: 'walk', name: 'Marche', duration_s: 1800 },
          { id: 2, day: '2026-11-10', sport: 'swim', name: 'Piscine', duration_s: 3600 },
        ],
      },
    })
    render(<ActivityCalendar />)
    expect(await screen.findByText('semaines d’affilée')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Piscine \(Natation, 1 h 00\)/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Marche \(Marche, 30 min\)/ })).toBeInTheDocument()
  })
})
