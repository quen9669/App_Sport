// The strength session being typed at the gym, before it is saved.
// It is kept in the browser (localStorage) so that closing the app or losing
// the network between two sets never loses what was typed.
import type { Exercise, StrengthSetInput } from '../api/client'

export interface Draft {
  startedAt: string // ISO date-time, when the first set was added
  sets: StrengthSetInput[]
}

const STORAGE_KEY = 'app-sport:strength-draft'

/** Read the saved draft. Storage can be unavailable (private mode): then there is none. */
export function loadDraft(): Draft | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const draft = JSON.parse(raw) as Draft
    return Array.isArray(draft.sets) && typeof draft.startedAt === 'string' ? draft : null
  } catch {
    return null
  }
}

export function saveDraft(draft: Draft | null): void {
  try {
    if (draft) localStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage unavailable: the draft only lives in memory, which is fine.
  }
}

/** Add a set, starting the draft (and its clock) with the first one. */
export function addSet(draft: Draft | null, set: StrengthSetInput, now = new Date()): Draft {
  return draft
    ? { ...draft, sets: [...draft.sets, set] }
    : { startedAt: now.toISOString(), sets: [set] }
}

export function removeSet(draft: Draft, index: number): Draft | null {
  const sets = draft.sets.filter((_, i) => i !== index)
  return sets.length > 0 ? { ...draft, sets } : null
}

/** "Répéter la série" : the same exercise, reps and load as the last set, in one tap. */
export function repeatLast(draft: Draft): Draft {
  const last = draft.sets.at(-1)
  return last ? { ...draft, sets: [...draft.sets, { ...last }] } : draft
}

/**
 * Values proposed when an exercise is picked: the last set of that exercise in
 * this session if any, otherwise the last time it was done (from the backend).
 */
export function defaultsFor(
  name: string,
  draft: Draft | null,
  exercises: Exercise[],
): { reps: string; weight: string } {
  const inSession = draft?.sets.filter((set) => set.exercise === name).at(-1)
  if (inSession) {
    return { reps: String(inSession.reps), weight: inSession.weight_kg?.toString() ?? '' }
  }
  const known = exercises.find((exercise) => exercise.name === name)
  return {
    reps: known?.last_reps?.toString() ?? (known?.bodyweight ? '10' : '8'),
    weight: known?.last_weight_kg?.toString() ?? '',
  }
}

/** Minutes since the first set, at least 1 and at most 300 (the backend's bounds). */
export function elapsedMinutes(draft: Draft, now = new Date()): number {
  const minutes = Math.round((now.getTime() - Date.parse(draft.startedAt)) / 60000)
  return Math.min(Math.max(minutes, 1), 300)
}

/** "8 × 80 kg", or "6 rép." for a body-weight set. */
export function formatSet(set: StrengthSetInput): string {
  return set.weight_kg === null
    ? `${set.reps} rép.`
    : `${set.reps} × ${String(set.weight_kg).replace('.', ',')} kg`
}

/** "Squat : 8 × 80 kg, 8 × 80 kg" lines, one per exercise, in the order done. */
export function summarize(sets: StrengthSetInput[]): string[] {
  const byExercise = new Map<string, string[]>()
  for (const set of sets) {
    const text = formatSet(set)
    byExercise.set(set.exercise, [...(byExercise.get(set.exercise) ?? []), text])
  }
  return [...byExercise].map(([exercise, parts]) => `${exercise} : ${parts.join(', ')}`)
}
