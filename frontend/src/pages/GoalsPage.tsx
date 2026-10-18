// "Objectifs" page: list, add, pause or delete weekly goals.
import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  ApiError,
  createGoal,
  deleteGoal,
  fetchGoals,
  updateGoal,
  type Goal,
  type GoalInput,
  type GoalKind,
  type GoalSport,
} from '../api/client'
import { GOAL_TARGET_BOUNDS, rangeError } from '../utils/bounds'
import { formatNumber, GOAL_KIND_LABELS, GOAL_UNITS, goalTitle } from '../utils/format'

const KINDS = Object.keys(GOAL_TARGET_BOUNDS) as GoalKind[]

// The goal from the specification, created in one tap.
const PRESET: GoalInput[] = [
  { kind: 'strength_sessions', target: 3 },
  { kind: 'cardio_sessions', target: 3 },
]

const STATUS_TEXT: Record<string, string> = { active: 'actif', paused: 'en pause', done: 'terminé' }

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Le backend ne répond pas.'
}

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [kind, setKind] = useState<GoalKind>('strength_sessions')
  const [target, setTarget] = useState('3')
  const [sport, setSport] = useState<GoalSport | ''>('')
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setGoals(await fetchGoals())
    } catch (err) {
      setError(errorText(err))
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchGoals()
      .then((data) => {
        if (!cancelled) setGoals(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorText(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await reload()
    } catch (err) {
      setError(errorText(err))
    }
  }

  function add(event: FormEvent) {
    event.preventDefault() // stay on the page instead of the browser's default form submit
    const value = Number(target.replace(',', '.'))
    const problem = rangeError(value, GOAL_TARGET_BOUNDS[kind], GOAL_UNITS[kind])
    if (problem) {
      setError(problem)
      return
    }
    const goal: GoalInput = { kind, target: value }
    if (kind === 'distance_km' && sport) goal.sport = sport
    void run(() => createGoal(goal))
  }

  const active = goals.filter((goal) => goal.status === 'active')

  return (
    <>
      <h1>Objectifs</h1>
      <p className="subtitle">Par semaine, du lundi au dimanche</p>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {active.length === 0 && (
        <section className="card">
          <p>Pas encore d’objectif actif. Pour commencer :</p>
          <button
            type="button"
            onClick={() => void run(() => Promise.all(PRESET.map((goal) => createGoal(goal))))}
          >
            3 muscu + 3 cardio par semaine
          </button>
        </section>
      )}

      {goals.length > 0 && (
        <section className="card" aria-labelledby="goal-list-title">
          <h2 id="goal-list-title">Mes objectifs</h2>
          <ul className="goal-list">
            {goals.map((goal) => (
              <li key={goal.id} className={goal.status === 'active' ? '' : 'goal--inactive'}>
                <span>
                  <strong>{goalTitle(goal.kind, goal.sport)}</strong> : {formatNumber(goal.target)}{' '}
                  {GOAL_UNITS[goal.kind]} <span className="hint">({STATUS_TEXT[goal.status]})</span>
                </span>
                <span className="actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      void run(() =>
                        updateGoal(goal.id, {
                          status: goal.status === 'active' ? 'paused' : 'active',
                        }),
                      )
                    }
                  >
                    {goal.status === 'active' ? 'Mettre en pause' : 'Réactiver'}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Supprimer ${goalTitle(goal.kind, goal.sport)}`}
                    onClick={() => void run(() => deleteGoal(goal.id))}
                  >
                    Supprimer
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card" aria-labelledby="goal-form-title">
        <h2 id="goal-form-title">Ajouter un objectif</h2>
        <form className="form" onSubmit={add}>
          <label>
            Type
            <select value={kind} onChange={(event) => setKind(event.target.value as GoalKind)}>
              {KINDS.map((value) => (
                <option key={value} value={value}>
                  {GOAL_KIND_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cible par semaine ({GOAL_UNITS[kind]})
            <input
              inputMode="decimal"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </label>
          {kind === 'distance_km' && (
            <label>
              Sport
              <select
                value={sport}
                onChange={(event) => setSport(event.target.value as GoalSport | '')}
              >
                <option value="">Tous</option>
                <option value="run">Course</option>
                <option value="ride">Vélo</option>
              </select>
            </label>
          )}
          <button type="submit">Ajouter</button>
        </form>
      </section>
    </>
  )
}
