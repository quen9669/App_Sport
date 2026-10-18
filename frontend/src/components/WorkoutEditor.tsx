// Edit the steps of a run before sending it to the watch: warm-up, blocks of
// repeats (effort + recovery), cool-down. Only lengths and pace ZONES are
// edited: the paces themselves come from the current form (backend).
import { useState, type FormEvent } from 'react'

import type { PaceKey, RunWorkout, WorkoutBlock, WorkoutStep } from '../api/client'
import { PACE_LABELS } from '../utils/workout'

// Same limits as app/services/workouts.py.
const MAX_BLOCKS = 6
const MAX_REPEATS = 30
type Unit = 'min' | 's' | 'm'

const DEFAULT_WARMUP: WorkoutStep = { duration_s: 900, distance_m: null, pace: 'easy' }
const DEFAULT_COOLDOWN: WorkoutStep = { duration_s: 600, distance_m: null, pace: 'easy' }
const DEFAULT_RECOVERY: WorkoutStep = { duration_s: 120, distance_m: null, pace: 'none' }
const DEFAULT_BLOCK: WorkoutBlock = {
  repeats: 1,
  work: { duration_s: 1200, distance_m: null, pace: 'easy' },
  recovery: null,
}

/** The unit a step is best shown in: metres for a distance, minutes when round. */
function unitOf(step: WorkoutStep): Unit {
  if (step.distance_m !== null) return 'm'
  return (step.duration_s ?? 0) % 60 === 0 ? 'min' : 's'
}

function valueIn(step: WorkoutStep, unit: Unit): number {
  if (unit === 'm') return step.distance_m ?? 0
  const seconds = step.duration_s ?? 0
  return unit === 'min' ? seconds / 60 : seconds
}

function stepFrom(value: number, unit: Unit, pace: PaceKey): WorkoutStep {
  if (unit === 'm') return { duration_s: null, distance_m: Math.round(value), pace }
  const seconds = unit === 'min' ? Math.round(value * 60) : Math.round(value)
  return { duration_s: seconds, distance_m: null, pace }
}

function StepFields({
  label,
  step,
  onChange,
}: {
  label: string
  step: WorkoutStep
  onChange: (step: WorkoutStep) => void
}) {
  // The unit is kept separately: typing "0" must not switch minutes to seconds.
  const [unit, setUnit] = useState<Unit>(unitOf(step))
  const value = valueIn(step, unit)
  return (
    <span className="step-fields">
      <input
        type="number"
        min={1}
        step="any"
        aria-label={`${label} : longueur`}
        value={Number.isFinite(value) ? value : ''}
        onChange={(e) => onChange(stepFrom(Number(e.target.value), unit, step.pace))}
      />
      <select
        aria-label={`${label} : unité`}
        value={unit}
        onChange={(e) => {
          const next = e.target.value as Unit
          setUnit(next)
          onChange(stepFrom(value, next, step.pace))
        }}
      >
        <option value="min">min</option>
        <option value="s">s</option>
        <option value="m">m</option>
      </select>
      <select
        aria-label={`${label} : allure`}
        value={step.pace}
        onChange={(e) => onChange({ ...step, pace: e.target.value as PaceKey })}
      >
        {(Object.keys(PACE_LABELS) as PaceKey[]).map((key) => (
          <option key={key} value={key}>
            {PACE_LABELS[key]}
          </option>
        ))}
      </select>
    </span>
  )
}

/** A checkbox that adds or removes an optional step (warm-up, recovery, cool-down). */
function OptionalStep({
  label,
  step,
  fallback,
  onChange,
}: {
  label: string
  step: WorkoutStep | null
  fallback: WorkoutStep
  onChange: (step: WorkoutStep | null) => void
}) {
  return (
    <div className="step-row">
      <label>
        <input
          type="checkbox"
          checked={step !== null}
          onChange={(e) => onChange(e.target.checked ? fallback : null)}
        />{' '}
        {label}
      </label>
      {step && <StepFields label={label} step={step} onChange={onChange} />}
    </div>
  )
}

/** A step outside Garmin's limits (checked again by the backend). */
function invalid(step: WorkoutStep | null): boolean {
  if (!step) return false
  if (step.distance_m !== null) return step.distance_m < 50 || step.distance_m > 50_000
  const seconds = step.duration_s ?? 0
  return seconds < 10 || seconds > 4 * 3600
}

interface Props {
  workout: RunWorkout
  onSave: (workout: RunWorkout) => Promise<void>
  onCancel: () => void
}

export default function WorkoutEditor({ workout, onSave, onCancel }: Props) {
  const [draft, setDraft] = useState<RunWorkout>(workout)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const setBlock = (index: number, block: WorkoutBlock) =>
    setDraft({ ...draft, blocks: draft.blocks.map((b, i) => (i === index ? block : b)) })

  async function submit(event: FormEvent) {
    event.preventDefault()
    const steps = [
      draft.warmup,
      draft.cooldown,
      ...draft.blocks.flatMap((b) => [b.work, b.recovery]),
    ]
    if (steps.some(invalid)) {
      setError('Chaque étape dure entre 10 s et 4 h, ou fait entre 50 m et 50 km.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave(draft)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Enregistrement impossible.')
      setSaving(false)
    }
  }

  return (
    <form className="workout-editor" onSubmit={submit} aria-label="Modifier les étapes">
      <OptionalStep
        label="Échauffement"
        step={draft.warmup}
        fallback={DEFAULT_WARMUP}
        onChange={(warmup) => setDraft({ ...draft, warmup })}
      />
      {draft.blocks.map((block, i) => (
        <fieldset key={i} className="workout-block">
          <legend>Bloc {i + 1}</legend>
          <div className="step-row">
            <label>
              Répétitions{' '}
              <input
                type="number"
                min={1}
                max={MAX_REPEATS}
                value={block.repeats}
                onChange={(e) =>
                  setBlock(i, {
                    ...block,
                    repeats: Math.min(MAX_REPEATS, Math.max(1, Number(e.target.value) || 1)),
                  })
                }
              />
            </label>
          </div>
          <div className="step-row">
            <span>Effort</span>
            <StepFields
              label={`Bloc ${i + 1} effort`}
              step={block.work}
              onChange={(work) => setBlock(i, { ...block, work })}
            />
          </div>
          <OptionalStep
            label={`Bloc ${i + 1} récupération`}
            step={block.recovery}
            fallback={DEFAULT_RECOVERY}
            onChange={(recovery) => setBlock(i, { ...block, recovery })}
          />
          {draft.blocks.length > 1 && (
            <button
              type="button"
              className="secondary"
              onClick={() => setDraft({ ...draft, blocks: draft.blocks.filter((_, j) => j !== i) })}
            >
              Supprimer ce bloc
            </button>
          )}
        </fieldset>
      ))}
      {draft.blocks.length < MAX_BLOCKS && (
        <button
          type="button"
          className="secondary"
          onClick={() => setDraft({ ...draft, blocks: [...draft.blocks, DEFAULT_BLOCK] })}
        >
          Ajouter un bloc
        </button>
      )}
      <OptionalStep
        label="Retour au calme"
        step={draft.cooldown}
        fallback={DEFAULT_COOLDOWN}
        onChange={(cooldown) => setDraft({ ...draft, cooldown })}
      />
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="plan-actions">
        <button type="submit" disabled={saving}>
          Enregistrer
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={saving}>
          Annuler
        </button>
      </div>
    </form>
  )
}
