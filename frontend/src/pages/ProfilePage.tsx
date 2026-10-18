// "Profil" page: personal data form, weight curve and body measurements.
import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  ApiError,
  deleteBodyMetric,
  fetchBodyMetrics,
  fetchProfile,
  saveBodyMetric,
  saveProfile,
  type BodyMetric,
} from '../api/client'
import { BODY_BOUNDS, rangeError } from '../utils/bounds'
import { formatNumber, formatShortDate, todayIso } from '../utils/format'
import {
  parseNumber,
  toForm,
  toInput,
  validateProfile,
  type FormErrors,
  type ProfileForm,
} from '../utils/profileForm'
import { withRollingAverage } from '../utils/weight'

// Loaded on demand: see the comment at the top of WeightChart.tsx.
const WeightChart = lazy(() => import('../components/WeightChart'))

const PERIODS = [30, 90, 365] as const
type Period = (typeof PERIODS)[number]

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Le backend ne répond pas.'
}

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileForm | null>(null)
  const [age, setAge] = useState<number | null>(null)
  const [errors, setErrors] = useState<FormErrors>({})
  const [message, setMessage] = useState<string | null>(null)
  const [period, setPeriod] = useState<Period>(90)
  const [metrics, setMetrics] = useState<BodyMetric[]>([])
  const [entry, setEntry] = useState({ weight: '', fat: '', waist: '' })
  const [entryError, setEntryError] = useState<string | null>(null)

  const loadMetrics = useCallback(() => fetchBodyMetrics(period), [period])

  useEffect(() => {
    let cancelled = false
    fetchProfile()
      .then((profile) => {
        if (!cancelled) {
          setForm(toForm(profile))
          setAge(profile.age)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setMessage(errorText(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    loadMetrics()
      .then((data) => {
        if (!cancelled) setMetrics(data)
      })
      .catch(() => {
        // The profile error message already says the backend is down.
      })
    return () => {
      cancelled = true
    }
  }, [loadMetrics])

  function update(field: keyof ProfileForm, value: string) {
    setForm((current) => (current ? { ...current, [field]: value } : current))
  }

  async function submitProfile(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    const found = validateProfile(form)
    setErrors(found)
    setMessage(null)
    if (Object.keys(found).length > 0) return
    try {
      const saved = await saveProfile(toInput(form))
      setForm(toForm(saved))
      setAge(saved.age)
      setMessage('Profil enregistré.')
    } catch (err) {
      setMessage(errorText(err))
    }
  }

  async function submitEntry(event: FormEvent) {
    event.preventDefault()
    const weight = parseNumber(entry.weight)
    const fat = entry.fat.trim() ? parseNumber(entry.fat) : null
    const waist = entry.waist.trim() ? parseNumber(entry.waist) : null
    const problem =
      rangeError(weight, BODY_BOUNDS.weight_kg, 'kg') ??
      (fat === null ? null : rangeError(fat, BODY_BOUNDS.body_fat_pct, '%')) ??
      (waist === null ? null : rangeError(waist, BODY_BOUNDS.waist_cm, 'cm'))
    setEntryError(problem)
    if (problem) return
    try {
      await saveBodyMetric({
        measured_on: todayIso(),
        weight_kg: weight,
        body_fat_pct: fat,
        waist_cm: waist,
      })
      setEntry({ weight: '', fat: '', waist: '' })
      setMetrics(await loadMetrics())
    } catch (err) {
      setEntryError(errorText(err))
    }
  }

  async function removeMetric(id: number) {
    try {
      await deleteBodyMetric(id)
      setMetrics(await loadMetrics())
    } catch (err) {
      setEntryError(errorText(err))
    }
  }

  const fieldError = (field: keyof ProfileForm) =>
    errors[field] && (
      <span className="field-error" id={`${field}-error`}>
        {errors[field]}
      </span>
    )
  const invalid = (field: keyof ProfileForm) =>
    errors[field] ? { 'aria-invalid': true, 'aria-describedby': `${field}-error` } : {}

  return (
    <>
      <h1>Profil</h1>

      <section className="card" aria-labelledby="weight-chart-title">
        <h2 id="weight-chart-title">Courbe de poids</h2>
        <div className="actions" role="group" aria-label="Période">
          {PERIODS.map((days) => (
            <button
              key={days}
              type="button"
              className={days === period ? '' : 'secondary'}
              aria-pressed={days === period}
              onClick={() => setPeriod(days)}
            >
              {days} j
            </button>
          ))}
        </div>
        {metrics.length === 0 ? (
          <p className="hint">Pas encore de pesée sur cette période.</p>
        ) : (
          <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
            <WeightChart points={withRollingAverage(metrics)} />
          </Suspense>
        )}

        <h3>Nouvelle mesure (aujourd’hui)</h3>
        <form className="form form--inline" onSubmit={(event) => void submitEntry(event)}>
          <label>
            Poids (kg)
            <input
              inputMode="decimal"
              value={entry.weight}
              onChange={(event) => setEntry({ ...entry, weight: event.target.value })}
              required
            />
          </label>
          <label>
            Masse grasse (%)
            <input
              inputMode="decimal"
              value={entry.fat}
              onChange={(event) => setEntry({ ...entry, fat: event.target.value })}
            />
          </label>
          <label>
            Tour de taille (cm)
            <input
              inputMode="decimal"
              value={entry.waist}
              onChange={(event) => setEntry({ ...entry, waist: event.target.value })}
            />
          </label>
          <button type="submit">Enregistrer la mesure</button>
        </form>
        {entryError && (
          <p className="field-error" role="alert">
            {entryError}
          </p>
        )}

        {metrics.length > 0 && (
          <details>
            <summary>Dernières mesures</summary>
            <ul className="goal-list">
              {[...metrics]
                .reverse()
                .slice(0, 10)
                .map((metric) => (
                  <li key={metric.id}>
                    <span>
                      {formatShortDate(metric.measured_on)} : {formatNumber(metric.weight_kg)} kg
                      {metric.body_fat_pct !== null && ` · ${formatNumber(metric.body_fat_pct)} %`}
                      {metric.waist_cm !== null && ` · ${formatNumber(metric.waist_cm)} cm`}
                    </span>
                    <button
                      type="button"
                      className="secondary"
                      aria-label={`Supprimer la mesure du ${formatShortDate(metric.measured_on)}`}
                      onClick={() => void removeMetric(metric.id)}
                    >
                      Supprimer
                    </button>
                  </li>
                ))}
            </ul>
          </details>
        )}
      </section>

      <section className="card" aria-labelledby="profile-title">
        <h2 id="profile-title">Mes informations</h2>
        <p className="hint">
          Elles servent à personnaliser les graphiques et, plus tard, les conseils des coachs. Tout
          reste sur ta machine.
        </p>
        {form && (
          <form className="form" onSubmit={(event) => void submitProfile(event)} noValidate>
            <label>
              Taille (cm)
              <input
                inputMode="decimal"
                value={form.height_cm}
                onChange={(event) => update('height_cm', event.target.value)}
                {...invalid('height_cm')}
              />
              {fieldError('height_cm')}
            </label>
            <label>
              Sexe
              <select value={form.sex} onChange={(event) => update('sex', event.target.value)}>
                <option value="">Non renseigné</option>
                <option value="male">Homme</option>
                <option value="female">Femme</option>
                <option value="other">Autre</option>
              </select>
            </label>
            <label>
              Date de naissance {age !== null && <span className="hint">({age} ans)</span>}
              <input
                type="date"
                value={form.birth_date}
                onChange={(event) => update('birth_date', event.target.value)}
                {...invalid('birth_date')}
              />
              {fieldError('birth_date')}
            </label>
            <label>
              FC max (si connue)
              <input
                inputMode="numeric"
                value={form.max_heartrate}
                onChange={(event) => update('max_heartrate', event.target.value)}
                {...invalid('max_heartrate')}
              />
              {fieldError('max_heartrate')}
            </label>
            <label>
              FC repos (si connue)
              <input
                inputMode="numeric"
                value={form.resting_heartrate}
                onChange={(event) => update('resting_heartrate', event.target.value)}
                {...invalid('resting_heartrate')}
              />
              {fieldError('resting_heartrate')}
            </label>
            <label>
              Niveau
              <select
                value={form.experience_level}
                onChange={(event) => update('experience_level', event.target.value)}
              >
                <option value="">Non renseigné</option>
                <option value="beginner">Débutant</option>
                <option value="intermediate">Intermédiaire</option>
                <option value="advanced">Confirmé</option>
              </select>
            </label>
            <label>
              Blessures et limitations
              <textarea
                rows={3}
                value={form.injuries}
                onChange={(event) => update('injuries', event.target.value)}
                {...invalid('injuries')}
              />
              {fieldError('injuries')}
            </label>
            <button type="submit">Enregistrer le profil</button>
          </form>
        )}
        {message && <p role="status">{message}</p>}
      </section>
    </>
  )
}
