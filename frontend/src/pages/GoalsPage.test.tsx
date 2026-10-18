import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Goal, GoalInput } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import GoalsPage from './GoalsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** A tiny in-memory backend for goals. */
function goalsBackend() {
  const goals: Goal[] = []
  return fakeBackend({
    'GET /api/goals': () => goals,
    'GET /api/goals/history': () => ({ weeks: [], streak: 0 }),
    'POST /api/goals': (_url: string, init?: RequestInit) => {
      const input = JSON.parse(String(init?.body)) as GoalInput
      const goal: Goal = {
        id: goals.length + 1,
        sport: null,
        start_date: '2026-10-18',
        end_date: null,
        status: 'active',
        ...input,
      }
      goals.push(goal)
      return goal
    },
  })
}

describe('GoalsPage', () => {
  it('creates "3 muscu + 3 cardio" in one tap', async () => {
    goalsBackend()

    render(<GoalsPage />)
    await userEvent.click(
      await screen.findByRole('button', { name: '3 muscu + 3 cardio par semaine' }),
    )

    const list = await screen.findByRole('list')
    expect(list).toHaveTextContent('Séances de musculation : 3 séances')
    expect(list).toHaveTextContent('Séances de cardio : 3 séances')
    expect(screen.queryByRole('button', { name: /3 muscu/ })).not.toBeInTheDocument()
  })

  it('shows the streak and the history table', async () => {
    fakeBackend({
      'GET /api/goals': [],
      'GET /api/goals/history': {
        streak: 2,
        weeks: ['2026-W41', '2026-W42'].map((week) => ({
          week,
          monday: '2026-10-05',
          all_achieved: true,
          goals: [
            {
              goal_id: 1,
              kind: 'strength_sessions',
              sport: null,
              target: 3,
              done: 3,
              achieved: true,
            },
          ],
        })),
      },
    })

    render(<GoalsPage />)

    expect(await screen.findByText('2 semaines réussies d’affilée')).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveTextContent('2026-W423 / 3Oui')
  })

  it('checks the target bounds before sending', async () => {
    const fetchMock = goalsBackend()

    render(<GoalsPage />)
    const target = await screen.findByLabelText(/Cible par semaine/)
    await userEvent.clear(target)
    await userEvent.type(target, '20')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Entre 1 et 14 séances')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })
})
