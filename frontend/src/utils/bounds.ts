// Validation bounds, identical to the backend's (backend/app/api/profile.py and goals.py).
// Checking them here shows the error at once; the backend checks them again anyway.

import type { GoalKind } from '../api/client'

export interface Range {
  min: number
  max: number
}

export const PROFILE_BOUNDS = {
  height_cm: { min: 100, max: 250 },
  max_heartrate: { min: 120, max: 230 },
  resting_heartrate: { min: 30, max: 110 },
  age: { min: 12, max: 100 },
  injuries_max_length: 2000,
} as const

export const BODY_BOUNDS = {
  weight_kg: { min: 30, max: 300 },
  body_fat_pct: { min: 3, max: 70 },
  waist_cm: { min: 40, max: 200 },
} as const

export const GOAL_TARGET_BOUNDS: Record<GoalKind, Range> = {
  strength_sessions: { min: 1, max: 14 },
  cardio_sessions: { min: 1, max: 14 },
  active_minutes: { min: 10, max: 3000 },
  distance_km: { min: 1, max: 1000 },
  training_load: { min: 10, max: 5000 },
  intensity_minutes: { min: 10, max: 3000 },
}

export const STRENGTH_BOUNDS = {
  reps: { min: 1, max: 100 },
  weight_kg: { min: 0, max: 500 },
  rpe: { min: 1, max: 10 },
  duration_min: { min: 1, max: 300 },
  max_sets: 100,
} as const

/** French error message if `value` is outside `range`, otherwise null. */
export function rangeError(value: number, range: Range, unit = ''): string | null {
  if (Number.isNaN(value)) return 'Nombre invalide'
  if (value < range.min || value > range.max) {
    const suffix = unit ? ` ${unit}` : ''
    return `Entre ${range.min} et ${range.max}${suffix}`
  }
  return null
}

/** Age in full years on `today` (one less if the birthday has not happened yet this year). */
export function ageOn(birthDate: string, today: Date = new Date()): number {
  const [year, month, day] = birthDate.split('-').map(Number) as [number, number, number]
  const beforeBirthday =
    today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)
  return today.getFullYear() - year - (beforeBirthday ? 1 : 0)
}
