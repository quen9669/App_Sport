// "Santé" page: sleep, resting heart rate, HRV and weight over 7, 30 or 90 days,
// and the training load of the last 12 weeks.
import { lazy, Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  fetchHealthMetrics,
  fetchTrainingLoad,
  type HealthDay,
  type HealthMetrics,
  type TrainingLoad,
} from '../api/client'
import { formatDuration, formatNumber, formatShortDate } from '../utils/format'
import {
  acwrLabel,
  formatClock,
  mean,
  regularityLabel,
  round,
  trendPoints,
  type TrendPoint,
} from '../utils/health'

// Loaded on demand: Recharts is only downloaded when this page is opened.
const TrendChart = lazy(() => import('../components/TrendChart'))
const LoadChart = lazy(() => import('../components/LoadChart'))

const PERIODS = [7, 30, 90] as const
type Period = (typeof PERIODS)[number]

const sleepHours = (day: HealthDay) => (day.sleep_s === null ? null : day.sleep_s / 3600)

/** A chart only makes sense with at least two values. */
const hasData = (points: TrendPoint[]) => points.filter((p) => p.value !== null).length >= 2

function Stat({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value ?? '–'}</dd>
    </div>
  )
}

function Chart(props: { points: TrendPoint[]; name: string; unit: string; digits?: number }) {
  if (!hasData(props.points)) return <p className="hint">Pas encore assez de données.</p>
  return (
    <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
      <TrendChart {...props} />
    </Suspense>
  )
}

export default function HealthPage() {
  const [period, setPeriod] = useState<Period>(30)
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null)
  const [load, setLoad] = useState<TrainingLoad | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchHealthMetrics(period)
      .then((data) => {
        if (!cancelled) setMetrics(data)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger les données de santé.')
      })
    return () => {
      cancelled = true
    }
  }, [period])

  useEffect(() => {
    let cancelled = false
    fetchTrainingLoad()
      .then((data) => {
        if (!cancelled) setLoad(data)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger la charge d’entraînement.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const days = metrics?.days ?? []
  const pick = (getter: (day: HealthDay) => number | null) => days.map(getter)
  const sleepAverage = mean(pick(sleepHours))
  const bedtime = mean(pick((d) => d.bedtime_min))
  const wake = mean(pick((d) => d.wake_min))

  return (
    <>
      <h1>Santé</h1>
      <p className="subtitle">Sommeil, récupération et charge d’entraînement</p>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      <div className="segmented" role="group" aria-label="Période">
        {PERIODS.map((value) => (
          <button
            key={value}
            type="button"
            className="secondary"
            aria-pressed={period === value}
            onClick={() => setPeriod(value)}
          >
            {value} jours
          </button>
        ))}
      </div>

      <section className="card" aria-labelledby="sleep-title">
        <h2 id="sleep-title">Sommeil</h2>
        <dl className="stats">
          <Stat
            label="Durée moyenne"
            value={sleepAverage === null ? null : formatDuration(sleepAverage * 3600)}
          />
          <Stat label="Score moyen" value={formatOrNull(mean(pick((d) => d.sleep_score)), 0)} />
          <Stat label="Coucher moyen" value={bedtime === null ? null : formatClock(bedtime)} />
          <Stat label="Lever moyen" value={wake === null ? null : formatClock(wake)} />
        </dl>
        {metrics && (
          <p className="hint">
            Horaires : coucher {regularityLabel(metrics.regularity.bedtime_sd_min)}
            {metrics.regularity.bedtime_sd_min !== null &&
              ` (± ${metrics.regularity.bedtime_sd_min} min)`}
            , lever {regularityLabel(metrics.regularity.wake_sd_min)}
            {metrics.regularity.wake_sd_min !== null &&
              ` (± ${metrics.regularity.wake_sd_min} min)`}
            , sur {metrics.regularity.nights} nuits.
          </p>
        )}
        <Chart points={trendPoints(days, sleepHours)} name="Sommeil" unit="h" digits={1} />
      </section>

      <section className="card" aria-labelledby="recovery-title">
        <h2 id="recovery-title">Récupération</h2>
        <dl className="stats">
          <Stat label="FC repos moyenne" value={withUnit(mean(pick((d) => d.resting_hr)), 'bpm')} />
          <Stat label="HRV moyenne" value={withUnit(mean(pick((d) => d.hrv_ms)), 'ms')} />
        </dl>
        <h3>FC au repos</h3>
        <Chart points={trendPoints(days, (d) => d.resting_hr)} name="FC repos" unit="bpm" />
        <h3>HRV (variabilité cardiaque)</h3>
        <p className="hint">Plus haute que d’habitude : plutôt bien récupéré.</p>
        <Chart points={trendPoints(days, (d) => d.hrv_ms)} name="HRV" unit="ms" />
      </section>

      <section className="card" aria-labelledby="weight-title">
        <h2 id="weight-title">Poids</h2>
        <Chart points={trendPoints(days, (d) => d.weight_kg)} name="Pesée" unit="kg" digits={1} />
      </section>

      {days.length > 0 && (
        <details>
          <summary>Voir les valeurs jour par jour</summary>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th scope="col">Jour</th>
                  <th scope="col">Sommeil</th>
                  <th scope="col">Score</th>
                  <th scope="col">FC repos</th>
                  <th scope="col">HRV</th>
                  <th scope="col">Poids</th>
                </tr>
              </thead>
              <tbody>
                {[...days].reverse().map((day) => (
                  <tr key={day.day}>
                    <td>{formatShortDate(day.day)}</td>
                    <td>{day.sleep_s === null ? '–' : formatDuration(day.sleep_s)}</td>
                    <td>{day.sleep_score ?? '–'}</td>
                    <td>{day.resting_hr ?? '–'}</td>
                    <td>{formatOrNull(day.hrv_ms, 0) ?? '–'}</td>
                    <td>{formatOrNull(day.weight_kg, 1) ?? '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {load && <LoadSection load={load} />}
    </>
  )
}

function LoadSection({ load }: { load: TrainingLoad }) {
  const { heart_rate: hr } = load
  return (
    <section className="card" aria-labelledby="load-title">
      <h2 id="load-title">Charge d’entraînement</h2>
      <dl className="stats">
        <Stat label="7 derniers jours" value={String(load.acute)} />
        <Stat label="Moyenne des 4 semaines avant" value={String(load.chronic)} />
        <Stat label="Ratio" value={formatOrNull(load.acwr, 2)} />
      </dl>
      <p>{acwrLabel(load.acwr)}</p>
      <p className="hint">
        Le ratio compare ta dernière semaine à tes habitudes. C’est un repère grossier, pas un
        diagnostic : écoute aussi tes sensations.
      </p>
      <p className="hint">
        {hr.max_hr && hr.resting_hr
          ? `Calcul avec ta FC (TRIMP) : max ${hr.max_hr} bpm${
              hr.max_source === 'age' ? ' (estimée d’après ton âge)' : ''
            }, repos ${hr.resting_hr} bpm${hr.resting_source === 'garmin' ? ' (Garmin)' : ''}.`
          : 'FC max ou de repos inconnue : la charge est estimée d’après la durée.'}{' '}
        {hr.max_source !== 'profile' && (
          <Link to="/profil">Renseigne ta FC max dans le profil.</Link>
        )}
      </p>
      <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
        <LoadChart weeks={load.weeks} />
      </Suspense>
      <details>
        <summary>Voir le tableau</summary>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th scope="col">Semaine du</th>
                <th scope="col">Charge</th>
                <th scope="col">Séances</th>
                <th scope="col">Avec FC</th>
              </tr>
            </thead>
            <tbody>
              {[...load.weeks].reverse().map((week) => (
                <tr key={week.week}>
                  <td>{formatShortDate(week.monday)}</td>
                  <td>{week.load}</td>
                  <td>{week.sessions}</td>
                  <td>{week.with_heart_rate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}

function formatOrNull(value: number | null, digits: number): string | null {
  const rounded = round(value, digits)
  return rounded === null ? null : formatNumber(rounded, digits)
}

function withUnit(value: number | null, unit: string): string | null {
  const text = formatOrNull(value, 0)
  return text === null ? null : `${text} ${unit}`
}
