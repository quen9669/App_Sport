import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Exercise, StrengthSessionInput } from '../api/client'
import { fakeBackend } from '../test/fakeBackend'
import StrengthPage from './StrengthPage'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

const exercises: Exercise[] = [
  { name: 'Squat', group: 'Jambes', bodyweight: false, last_reps: 8, last_weight_kg: 80 },
  { name: 'Tractions', group: 'Dos', bodyweight: true, last_reps: null, last_weight_kg: null },
]

describe('StrengthPage', () => {
  it('logs sets with the last load pre-filled, repeats one and saves the session', async () => {
    let saved: StrengthSessionInput | null = null
    fakeBackend({
      'GET /api/strength/exercises': exercises,
      'GET /api/strength/sessions': [],
      'POST /api/strength/sessions': (_url: string, init?: RequestInit) => {
        saved = JSON.parse(String(init?.body)) as StrengthSessionInput
        return { id: 1, activity_id: null, ...saved }
      },
    })

    render(<StrengthPage />)
    await screen.findByRole('option', { name: 'Squat' })
    await userEvent.selectOptions(screen.getByLabelText('Exercice'), 'Squat')
    expect(screen.getByLabelText('Charge (kg)')).toHaveValue('80')

    await userEvent.click(screen.getByRole('button', { name: 'Ajouter la série' }))
    await userEvent.click(screen.getByRole('button', { name: 'Répéter la série' }))
    expect(screen.getByRole('heading', { name: '2 séries' })).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Durée (min)'), '55')
    await userEvent.click(screen.getByRole('button', { name: 'Terminer la séance' }))

    expect(await screen.findByText('Séance enregistrée. Bravo !')).toBeInTheDocument()
    expect(saved).toMatchObject({
      duration_min: 55,
      sets: [
        { exercise: 'Squat', reps: 8, weight_kg: 80, rpe: null },
        { exercise: 'Squat', reps: 8, weight_kg: 80, rpe: null },
      ],
    })
    expect(localStorage.getItem('app-sport:strength-draft')).toBeNull()
  })

  it('accepts a free exercise and checks the bounds', async () => {
    fakeBackend({ 'GET /api/strength/exercises': exercises, 'GET /api/strength/sessions': [] })

    render(<StrengthPage />)
    await screen.findByRole('option', { name: 'Squat' })
    await userEvent.selectOptions(screen.getByLabelText('Exercice'), 'Autre exercice…')
    await userEvent.type(screen.getByLabelText('Nom de l’exercice'), 'Hack squat')
    await userEvent.type(screen.getByLabelText('Répétitions'), '200')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter la série' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Entre 1 et 100 répétitions')

    await userEvent.clear(screen.getByLabelText('Répétitions'))
    await userEvent.type(screen.getByLabelText('Répétitions'), '12')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter la série' }))
    expect(screen.getByText(/Hack squat : 12 rép\./)).toBeInTheDocument()
  })
})
