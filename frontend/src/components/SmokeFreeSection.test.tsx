// Unit tests for <SmokeFreeSection />, against a fake backend.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Smoking } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import SmokeFreeSection from './SmokeFreeSection'

afterEach(() => {
  vi.unstubAllGlobals()
})

const smoking: Smoking = {
  quit_date: '2026-09-01',
  quit_date_is_default: true,
  today: '2026-10-18',
  days_since_quit: 48,
  smoke_free_days: 47,
  cigarette_days: 1,
  cigarettes: 2,
  current_streak: 8,
  longest_streak: 39,
  months: [
    { month: '2026-09', days: 30, smoke_free_days: 30, cigarettes: 0 },
    { month: '2026-10', days: 18, smoke_free_days: 17, cigarettes: 2 },
  ],
  entries: [{ day: '2026-10-10', cigarettes: 2, note: 'soirée' }],
}

describe('SmokeFreeSection', () => {
  it('shows the counters, the months and the days with a cigarette', async () => {
    fakeBackend({ 'GET /api/smoking': smoking })
    render(<SmokeFreeSection />)

    expect(await screen.findByText('47 (98 %)')).toBeInTheDocument()
    expect(screen.getByText('8 jours')).toBeInTheDocument() // current streak
    expect(screen.getByText('39 jours')).toBeInTheDocument() // record
    expect(screen.getByText(/30\/30 jours sans cigarette/)).toBeInTheDocument()
    expect(screen.getByText(/2 cigarettes · soirée/)).toBeInTheDocument()
    expect(screen.getByText(/Date par défaut/)).toBeInTheDocument()
  })

  it('writes a day with a cigarette and shows the new counters', async () => {
    const fetchMock = fakeBackend({
      'GET /api/smoking': { ...smoking, entries: [], cigarettes: 0 },
      'PUT /api/smoking/days/2026-10-17': { ...smoking, current_streak: 1 },
    })
    const user = userEvent.setup()
    render(<SmokeFreeSection />)

    await user.click(await screen.findByRole('button', { name: '+ J’ai fumé' }))
    const day = screen.getByLabelText('Jour')
    await user.clear(day)
    await user.type(day, '2026-10-17')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('1 jour')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ cigarettes: 1, note: null })
  })

  it('refuses an impossible count before sending', async () => {
    const fetchMock = fakeBackend({ 'GET /api/smoking': smoking })
    const user = userEvent.setup()
    render(<SmokeFreeSection />)

    await user.click(await screen.findByRole('button', { name: '+ J’ai fumé' }))
    const count = screen.getByLabelText('Cigarettes')
    await user.clear(count)
    await user.type(count, '0')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Entre 1 et 60')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
  })

  it('removes a day written by mistake', async () => {
    fakeBackend({
      'GET /api/smoking': smoking,
      'DELETE /api/smoking/days/2026-10-10': { ...smoking, entries: [], cigarette_days: 0 },
    })
    const user = userEvent.setup()
    render(<SmokeFreeSection />)

    const list = (await screen.findByText('Jours avec cigarette')).nextElementSibling as HTMLElement
    await user.click(within(list).getByRole('button', { name: /Supprimer/ }))

    expect(await screen.findByText('Jours sans cigarette')).toBeInTheDocument()
    expect(screen.queryByText('Jours avec cigarette')).not.toBeInTheDocument()
  })
})
