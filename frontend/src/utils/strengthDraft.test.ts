import { afterEach, describe, expect, it } from 'vitest'

import type { Exercise } from '../api/client'
import {
  addSet,
  defaultsFor,
  elapsedMinutes,
  loadDraft,
  removeSet,
  repeatLast,
  saveDraft,
  summarize,
} from './strengthDraft'

const squat = { exercise: 'Squat', reps: 8, weight_kg: 80, rpe: null }
const pullUp = { exercise: 'Tractions', reps: 6, weight_kg: null, rpe: 9 }
const catalogue: Exercise[] = [
  { name: 'Squat', group: 'Jambes', bodyweight: false, last_reps: 5, last_weight_kg: 87.5 },
  { name: 'Pompes', group: 'Pectoraux', bodyweight: true, last_reps: null, last_weight_kg: null },
]

afterEach(() => localStorage.clear())

describe('strength draft', () => {
  it('starts the clock with the first set and repeats the last one', () => {
    const start = new Date('2026-10-18T17:00:00Z')
    let draft = addSet(null, squat, start)
    draft = repeatLast(addSet(draft, pullUp))
    expect(draft.startedAt).toBe('2026-10-18T17:00:00.000Z')
    expect(draft.sets.map((s) => s.exercise)).toEqual(['Squat', 'Tractions', 'Tractions'])
    expect(elapsedMinutes(draft, new Date('2026-10-18T17:52:20Z'))).toBe(52)
  })

  it('removing the last set ends the draft', () => {
    expect(removeSet(addSet(null, squat), 0)).toBeNull()
  })

  it('survives a reload through localStorage', () => {
    const draft = addSet(null, squat)
    saveDraft(draft)
    expect(loadDraft()).toEqual(draft)
    saveDraft(null)
    expect(loadDraft()).toBeNull()
  })

  it('proposes the load of this session first, then the last session', () => {
    expect(defaultsFor('Squat', null, catalogue)).toEqual({ reps: '5', weight: '87.5' })
    expect(defaultsFor('Squat', addSet(null, squat), catalogue)).toEqual({
      reps: '8',
      weight: '80',
    })
    expect(defaultsFor('Pompes', null, catalogue)).toEqual({ reps: '10', weight: '' })
  })

  it('summarizes sets per exercise in French', () => {
    expect(summarize([squat, { ...squat, weight_kg: 82.5 }, pullUp])).toEqual([
      'Squat : 8 × 80 kg, 8 × 82,5 kg',
      'Tractions : 6 rép.',
    ])
  })
})
