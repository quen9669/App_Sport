// "Muscu" page: type a strength session at the gym, set by set, then save it.
// Designed for a phone between two sets: big buttons, last load pre-filled,
// "Répéter la série" in one tap, and nothing lost if the app is closed.
import { useEffect, useState, type FormEvent } from 'react'

import {
  ApiError,
  createStrengthSession,
  deleteStrengthSession,
  fetchExercises,
  fetchStrengthSessions,
  type Exercise,
  type StrengthSession,
} from '../api/client'
import { rangeError, STRENGTH_BOUNDS } from '../utils/bounds'
import { formatDateTime } from '../utils/format'
import {
  addSet,
  defaultsFor,
  elapsedMinutes,
  formatSet,
  loadDraft,
  removeSet,
  repeatLast,
  saveDraft,
  summarize,
  type Draft,
} from '../utils/strengthDraft'

const OTHER = '__other__' // value of the "Autre exercice…" choice

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Le backend ne répond pas.'
}

/** Group the catalogue for the <optgroup>s of the exercise list, keeping the backend's order. */
function groupByMuscle(exercises: Exercise[]): [string, Exercise[]][] {
  const groups = new Map<string, Exercise[]>()
  for (const exercise of exercises) {
    groups.set(exercise.group, [...(groups.get(exercise.group) ?? []), exercise])
  }
  return [...groups]
}

const parse = (value: string) => Number(value.replace(',', '.'))

export default function StrengthPage() {
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [sessions, setSessions] = useState<StrengthSession[]>([])
  // useState(function): read localStorage once, on the first render only.
  const [draft, setDraft] = useState<Draft | null>(() => loadDraft())
  const [choice, setChoice] = useState('')
  const [customName, setCustomName] = useState('')
  const [reps, setReps] = useState('')
  const [weight, setWeight] = useState('')
  const [rpe, setRpe] = useState('')
  const [duration, setDuration] = useState('') // empty = time since the first set
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  // Keep the browser copy of the draft in sync with every change.
  useEffect(() => saveDraft(draft), [draft])

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchExercises(), fetchStrengthSessions()])
      .then(([catalogue, recent]) => {
        if (!cancelled) {
          setExercises(catalogue)
          setSessions(recent)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorText(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const exerciseName = choice === OTHER ? customName.trim() : choice

  function pick(value: string) {
    setChoice(value)
    if (value && value !== OTHER) {
      const defaults = defaultsFor(value, draft, exercises)
      setReps(defaults.reps)
      setWeight(defaults.weight)
    }
  }

  function add(event: FormEvent) {
    event.preventDefault()
    const repsValue = parse(reps)
    const weightValue = weight.trim() ? parse(weight) : null
    const rpeValue = rpe.trim() ? parse(rpe) : null
    const problem =
      (exerciseName ? null : 'Choisis un exercice') ??
      rangeError(repsValue, STRENGTH_BOUNDS.reps, 'répétitions') ??
      (weightValue === null ? null : rangeError(weightValue, STRENGTH_BOUNDS.weight_kg, 'kg')) ??
      (rpeValue === null ? null : rangeError(rpeValue, STRENGTH_BOUNDS.rpe)) ??
      ((draft?.sets.length ?? 0) >= STRENGTH_BOUNDS.max_sets ? 'Séance trop longue' : null)
    setError(problem)
    setMessage(null)
    if (problem) return
    setDraft(
      addSet(draft, {
        exercise: exerciseName,
        reps: repsValue,
        weight_kg: weightValue,
        rpe: rpeValue,
      }),
    )
  }

  async function finish() {
    if (!draft) return
    const minutes = duration.trim() ? parse(duration) : elapsedMinutes(draft)
    const problem = rangeError(minutes, STRENGTH_BOUNDS.duration_min, 'min')
    setError(problem)
    if (problem) return
    try {
      await createStrengthSession({
        performed_at: draft.startedAt,
        duration_min: Math.round(minutes),
        notes: notes.trim() || null,
        sets: draft.sets,
      })
      setDraft(null)
      setDuration('')
      setNotes('')
      setMessage('Séance enregistrée. Bravo !')
      const [catalogue, recent] = await Promise.all([fetchExercises(), fetchStrengthSessions()])
      setExercises(catalogue)
      setSessions(recent)
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function remove(id: number) {
    try {
      await deleteStrengthSession(id)
      setSessions(await fetchStrengthSessions())
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <>
      <h1>Musculation</h1>
      <p className="subtitle">Note tes séries pendant la séance</p>

      <section className="card" aria-labelledby="set-form-title">
        <h2 id="set-form-title">{draft ? 'Séance en cours' : 'Nouvelle séance'}</h2>
        <form className="form" onSubmit={add}>
          <label>
            Exercice
            <select value={choice} onChange={(event) => pick(event.target.value)}>
              <option value="">Choisir…</option>
              {groupByMuscle(exercises).map(([group, items]) => (
                <optgroup key={group} label={group}>
                  {items.map((exercise) => (
                    <option key={exercise.name} value={exercise.name}>
                      {exercise.name}
                    </option>
                  ))}
                </optgroup>
              ))}
              <option value={OTHER}>Autre exercice…</option>
            </select>
          </label>
          {choice === OTHER && (
            <label>
              Nom de l’exercice
              <input
                value={customName}
                maxLength={64}
                onChange={(event) => setCustomName(event.target.value)}
              />
            </label>
          )}
          <div className="form form--inline">
            <label>
              Répétitions
              <input inputMode="numeric" value={reps} onChange={(e) => setReps(e.target.value)} />
            </label>
            <label>
              Charge (kg)
              <input
                inputMode="decimal"
                placeholder="poids du corps"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
              />
            </label>
            <label>
              Effort (1 à 10)
              <input inputMode="numeric" value={rpe} onChange={(e) => setRpe(e.target.value)} />
            </label>
          </div>
          <div className="actions">
            <button type="submit">Ajouter la série</button>
            {draft && (
              <button
                type="button"
                className="secondary"
                onClick={() => setDraft(repeatLast(draft))}
              >
                Répéter la série
              </button>
            )}
          </div>
        </form>

        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}

        {draft && (
          <>
            <h3>
              {draft.sets.length} série{draft.sets.length > 1 ? 's' : ''}
            </h3>
            <ol className="set-list">
              {draft.sets.map((set, index) => (
                <li key={index}>
                  <span>
                    {set.exercise} : {formatSet(set)}
                    {set.rpe !== null && <span className="hint"> (effort {set.rpe})</span>}
                  </span>
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Retirer la série ${index + 1}`}
                    onClick={() => setDraft(removeSet(draft, index))}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ol>
            <div className="form form--inline">
              <label>
                Durée (min)
                <input
                  inputMode="numeric"
                  placeholder={String(elapsedMinutes(draft))}
                  value={duration}
                  onChange={(event) => setDuration(event.target.value)}
                />
              </label>
              <label>
                Notes
                <input value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} />
              </label>
            </div>
            <div className="actions">
              <button type="button" onClick={() => void finish()}>
                Terminer la séance
              </button>
              <button type="button" className="secondary" onClick={() => setDraft(null)}>
                Abandonner
              </button>
            </div>
          </>
        )}
      </section>

      <section className="card" aria-labelledby="recent-title">
        <h2 id="recent-title">Dernières séances</h2>
        {sessions.length === 0 ? (
          <p className="hint">Aucune séance enregistrée pour l’instant.</p>
        ) : (
          <ul className="goal-list">
            {sessions.map((session) => (
              <li key={session.id}>
                <div>
                  <strong>{formatDateTime(session.performed_at)}</strong>
                  {session.duration_min !== null && (
                    <span className="hint"> · {session.duration_min} min</span>
                  )}
                  {summarize(session.sets).map((line) => (
                    <div key={line} className="hint">
                      {line}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  className="secondary"
                  aria-label={`Supprimer la séance du ${formatDateTime(session.performed_at)}`}
                  onClick={() => void remove(session.id)}
                >
                  Supprimer
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
