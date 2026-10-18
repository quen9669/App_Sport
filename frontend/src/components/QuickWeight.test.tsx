import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fakeBackend } from '../test/fakeBackend'
import QuickWeight from './QuickWeight'

afterEach(() => {
  vi.unstubAllGlobals()
})

const last = {
  id: 1,
  measured_on: '2026-10-17',
  weight_kg: 79.8,
  body_fat_pct: null,
  waist_cm: null,
}

describe('QuickWeight', () => {
  it('saves the last weight in 2 taps, adjusted by 0.1 kg', async () => {
    const fetchMock = fakeBackend({
      'GET /api/body-metrics': [last],
      'POST /api/body-metrics': (_url: string, init?: RequestInit) => ({
        id: 2,
        ...(JSON.parse(String(init?.body)) as object),
      }),
    })
    const onSaved = vi.fn()

    render(<QuickWeight onSaved={onSaved} />)
    await userEvent.click(screen.getByRole('button', { name: '+ Poids' }))
    expect(await screen.findByDisplayValue('79.8')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Moins 0,1 kg' }))
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('79,7 kg enregistrés')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ weight_kg: 79.7 })
    expect(onSaved).toHaveBeenCalled()
  })

  it('refuses an impossible weight without calling the backend', async () => {
    const fetchMock = fakeBackend({ 'GET /api/body-metrics': [] })

    render(<QuickWeight />)
    await userEvent.click(screen.getByRole('button', { name: '+ Poids' }))
    const input = await screen.findByLabelText('Poids du jour (kg)')
    await userEvent.clear(input)
    await userEvent.type(input, '700')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Entre 30 et 300 kg')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })
})
