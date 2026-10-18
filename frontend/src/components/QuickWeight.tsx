// "+ Poids" in 2 taps: open, (adjust by ±0.1 kg if needed), save.
// The field starts at the last weigh-in, which is usually within a few hundred grams.
import { useState } from 'react'

import { ApiError, fetchBodyMetrics, saveBodyMetric } from '../api/client'
import { BODY_BOUNDS, rangeError } from '../utils/bounds'
import { formatNumber, todayIso } from '../utils/format'

const STEP = 0.1
const DEFAULT_WEIGHT = 75

/** Round to one decimal: 0.1 + 0.2 is 0.30000000000000004 in JavaScript. */
const round1 = (value: number) => Math.round(value * 10) / 10

export default function QuickWeight({ onSaved }: { onSaved?: () => void }) {
  const [open, setOpen] = useState(false)
  const [weight, setWeight] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function start() {
    setSaved(null)
    setError(null)
    setOpen(true)
    try {
      const recent = await fetchBodyMetrics(365)
      const last = recent.at(-1)
      setWeight(String(last ? last.weight_kg : DEFAULT_WEIGHT))
    } catch {
      setWeight(String(DEFAULT_WEIGHT))
    }
  }

  function nudge(delta: number) {
    const current = Number(weight.replace(',', '.'))
    if (!Number.isNaN(current)) setWeight(String(round1(current + delta)))
  }

  async function save() {
    const value = Number(weight.replace(',', '.')) // accept "79,6" as typed in French
    const problem = rangeError(value, BODY_BOUNDS.weight_kg, 'kg')
    if (problem) {
      setError(problem)
      return
    }
    setSaving(true)
    try {
      await saveBodyMetric({
        measured_on: todayIso(),
        weight_kg: round1(value),
        body_fat_pct: null,
        waist_cm: null,
      })
      setOpen(false)
      setSaved(`${formatNumber(round1(value))} kg enregistrés`)
      onSaved?.()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le backend ne répond pas.')
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <div className="actions">
        <button type="button" onClick={() => void start()}>
          + Poids
        </button>
        {saved && <span role="status">{saved}</span>}
      </div>
    )
  }

  return (
    <div className="quick-weight">
      <button
        type="button"
        className="secondary"
        aria-label="Moins 0,1 kg"
        onClick={() => nudge(-STEP)}
      >
        −0,1
      </button>
      <label>
        <input
          aria-label="Poids du jour (kg)"
          inputMode="decimal"
          value={weight}
          onChange={(event) => setWeight(event.target.value)}
          aria-invalid={error ? true : undefined}
          size={5}
        />{' '}
        kg
      </label>
      <button
        type="button"
        className="secondary"
        aria-label="Plus 0,1 kg"
        onClick={() => nudge(STEP)}
      >
        +0,1
      </button>
      <button type="button" onClick={() => void save()} disabled={saving}>
        Enregistrer
      </button>
      <button type="button" className="secondary" onClick={() => setOpen(false)}>
        Annuler
      </button>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
