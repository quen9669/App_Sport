// Profile form helpers: convert between the API's profile and the form's text fields,
// and validate with the same bounds as the backend.
import type { Profile, ProfileInput } from '../api/client'
import { ageOn, PROFILE_BOUNDS, rangeError, type Range } from './bounds'

/** The form keeps every field as text, exactly as typed. */
export interface ProfileForm {
  height_cm: string
  sex: string
  birth_date: string
  max_heartrate: string
  resting_heartrate: string
  experience_level: string
  injuries: string
}

export type FormErrors = Partial<Record<keyof ProfileForm, string>>

const text = (value: number | string | null) => (value === null ? '' : String(value))

export function toForm(profile: Profile): ProfileForm {
  return {
    height_cm: text(profile.height_cm),
    sex: text(profile.sex),
    birth_date: text(profile.birth_date),
    max_heartrate: text(profile.max_heartrate),
    resting_heartrate: text(profile.resting_heartrate),
    experience_level: text(profile.experience_level),
    injuries: text(profile.injuries),
  }
}

export const parseNumber = (value: string) => Number(value.replace(',', '.'))

/** Check every field with the same bounds as the backend. Returns the errors by field. */
export function validateProfile(form: ProfileForm, today = new Date()): FormErrors {
  const errors: FormErrors = {}
  const numberFields: [keyof ProfileForm, Range, string][] = [
    ['height_cm', PROFILE_BOUNDS.height_cm, 'cm'],
    ['max_heartrate', PROFILE_BOUNDS.max_heartrate, 'bpm'],
    ['resting_heartrate', PROFILE_BOUNDS.resting_heartrate, 'bpm'],
  ]
  for (const [field, range, unit] of numberFields) {
    if (form[field].trim()) {
      const problem = rangeError(parseNumber(form[field]), range, unit)
      if (problem) errors[field] = problem
    }
  }
  if (form.birth_date) {
    const age = ageOn(form.birth_date, today)
    const { min, max } = PROFILE_BOUNDS.age
    if (Number.isNaN(age) || age < min || age > max) {
      errors.birth_date = `L’âge doit être entre ${min} et ${max} ans`
    }
  }
  if (form.injuries.length > PROFILE_BOUNDS.injuries_max_length) {
    errors.injuries = `${PROFILE_BOUNDS.injuries_max_length} caractères maximum`
  }
  return errors
}

export function toInput(form: ProfileForm): ProfileInput {
  const optionalNumber = (value: string) => (value.trim() ? parseNumber(value) : null)
  return {
    height_cm: optionalNumber(form.height_cm),
    max_heartrate: optionalNumber(form.max_heartrate),
    resting_heartrate: optionalNumber(form.resting_heartrate),
    sex: (form.sex || null) as ProfileInput['sex'],
    birth_date: form.birth_date || null,
    experience_level: (form.experience_level || null) as ProfileInput['experience_level'],
    injuries: form.injuries.trim() || null,
  }
}
