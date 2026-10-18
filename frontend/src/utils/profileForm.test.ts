import { describe, expect, it } from 'vitest'

import { ageOn } from './bounds'
import { validateProfile, type ProfileForm } from './profileForm'

const empty: ProfileForm = {
  height_cm: '',
  sex: '',
  birth_date: '',
  max_heartrate: '',
  resting_heartrate: '',
  experience_level: '',
  injuries: '',
}

const today = new Date(2026, 9, 18) // months start at 0 in JavaScript: 9 = October

describe('validateProfile', () => {
  it('accepts an empty profile (every field is optional)', () => {
    expect(validateProfile(empty, today)).toEqual({})
  })

  it('reports each out-of-range field', () => {
    const errors = validateProfile(
      {
        ...empty,
        height_cm: '90',
        max_heartrate: '250',
        resting_heartrate: 'abc',
        birth_date: '2020-01-01',
        injuries: 'x'.repeat(2001),
      },
      today,
    )
    expect(errors).toEqual({
      height_cm: 'Entre 100 et 250 cm',
      max_heartrate: 'Entre 120 et 230 bpm',
      resting_heartrate: 'Nombre invalide',
      birth_date: 'L’âge doit être entre 12 et 100 ans',
      injuries: '2000 caractères maximum',
    })
  })

  it('accepts French decimals', () => {
    expect(validateProfile({ ...empty, height_cm: '180,5' }, today)).toEqual({})
  })
})

describe('ageOn', () => {
  it('counts full years', () => {
    expect(ageOn('1990-10-19', today)).toBe(35)
    expect(ageOn('1990-10-18', today)).toBe(36)
  })
})
