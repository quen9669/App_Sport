// "Santé" folder: one page per tab (see navigation.ts). The summary shows one
// tile per measure, each opening its tab; the tabs hold the cards and charts:
// sleep, recovery (resting HR, HRV, training load), activity (intensity
// minutes, steps, floors), weight and the smoke-free counters.
import { lazy, Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  fetchHealthMetrics,
  fetchIntensityMinutes,
  fetchStepsAndFloors,
  fetchTrainingLoad,
  type HealthDay,
  type HealthMetrics,
  type IntensityMinutes,
  type StepsAndFloors,
  type TrainingLoad,
} from '../api/client'
import SmokeFreeSection from '../components/SmokeFreeSection'
import type { HealthSection } from '../navigation'
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
const WeeklyBarChart = lazy(() => import('../components/WeeklyBarChart'))

// The line under the title, so each tab says what it holds.
const SUBTITLES: Record<HealthSection, string> = {
  resume: 'Tes 7 derniers jours en un coup d’œil',
  sommeil: 'Durée, score et régularité de tes nuits',
  recuperation: 'FC au repos, HRV et charge d’entraînement',
  activite: 'Minutes d’intensité, pas et étages',
  poids: 'Tes pesées Garmin et celles saisies dans l’app',
  tabac: 'Tes jours sans cigarette',
}

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

function Chart(props: {
  points: TrendPoint[]
  name: string
  unit: string
  digits?: number
  smooth?: boolean
}) {
  if (!hasData(props.points)) return <p className="hint">Pas encore assez de données.</p>
  return (
    <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
      <TrendChart {...props} />
    </Suspense>
  )
}

export default function HealthPage({ section = 'resume' }: { section?: HealthSection }) {
  // The summary looks at the last week; the other tabs start on a month.
  const [period, setPeriod] = useState<Period>(section === 'resume' ? 7 : 30)
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null)
  const [load, setLoad] = useState<TrainingLoad | null>(null)
  const [intensity, setIntensity] = useState<IntensityMinutes | null>(null)
  const [steps, setSteps] = useState<StepsAndFloors | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Each tab only asks the backend for what it shows.
  const needs = {
    metrics: section !== 'tabac',
    load: section === 'resume' || section === 'recuperation',
    intensity: section === 'resume' || section === 'activite',
    steps: section === 'resume' || section === 'activite',
  }

  useEffect(() => {
    if (!needs.metrics) return
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
  }, [period, needs.metrics])

  useEffect(() => {
    let cancelled = false
    if (needs.load)
      fetchTrainingLoad()
        .then((data) => {
          if (!cancelled) setLoad(data)
        })
        .catch(() => {
          if (!cancelled) setError('Impossible de charger la charge d’entraînement.')
        })
    if (needs.intensity)
      fetchIntensityMinutes()
        .then((data) => {
          if (!cancelled) setIntensity(data)
        })
        .catch(() => {
          if (!cancelled) setError('Impossible de charger les minutes d’intensité.')
        })
    if (needs.steps)
      fetchStepsAndFloors()
        .then((data) => {
          if (!cancelled) setSteps(data)
        })
        .catch(() => {
          if (!cancelled) setError('Impossible de charger les pas et les étages.')
        })
    return () => {
      cancelled = true
    }
  }, [needs.load, needs.intensity, needs.steps])

  const days = metrics?.days ?? []

  return (
    <>
      <h1>Santé</h1>
      <p className="subtitle">{SUBTITLES[section]}</p>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {/* The summary always covers 7 days; the smoke-free card has no period. */}
      {section !== 'resume' && section !== 'tabac' && (
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
      )}

      {section === 'resume' && (
        <SummaryTiles days={days} load={load} intensity={intensity} steps={steps} />
      )}
      {section === 'sommeil' && metrics && (
        <>
          <SleepSection metrics={metrics} />
          <DaysTable days={days} />
        </>
      )}
      {section === 'recuperation' && (
        <>
          <RecoverySection days={days} />
          {load && <LoadSection load={load} />}
        </>
      )}
      {section === 'activite' && (
        <>
          {intensity && <IntensitySection intensity={intensity} />}
          {steps && <StepsSection steps={steps} days={days} />}
          {steps && <FloorsSection steps={steps} />}
        </>
      )}
      {section === 'poids' && <WeightSection days={days} />}
      {section === 'tabac' && <SmokeFreeSection />}
    </>
  )
}

/** The summary: one tile per measure, Garmin style, each opening its tab. */
function SummaryTiles(props: {
  days: HealthDay[]
  load: TrainingLoad | null
  intensity: IntensityMinutes | null
  steps: StepsAndFloors | null
}) {
  const { days, load, intensity, steps } = props
  const pick = (getter: (day: HealthDay) => number | null) => days.map(getter)
  const sleep = mean(pick(sleepHours))
  const lastWeight = days.at(-1)
  const week = steps?.weeks.at(-1)
  const intensityWeek = intensity?.weeks.at(-1)
  return (
    // Links rather than a <dl>: each tile is a door to its tab.
    <nav className="tiles tiles--links" aria-label="Résumé santé">
      <SummaryTile
        to="/sante/sommeil"
        label="Sommeil moyen"
        value={sleep === null ? null : formatDuration(sleep * 3600)}
      />
      <SummaryTile
        to="/sante/recuperation"
        label="FC au repos"
        value={formatOrNull(mean(pick((d) => d.resting_hr)), 0)}
        unit="bpm"
      />
      <SummaryTile
        to="/sante/recuperation"
        label="HRV"
        value={formatOrNull(mean(pick((d) => d.hrv_ms)), 0)}
        unit="ms"
      />
      <SummaryTile
        to="/sante/recuperation"
        label="Charge 7 jours"
        value={load ? String(load.acute) : null}
      />
      <SummaryTile
        to="/sante/activite"
        label="Intensité cette semaine"
        value={intensityWeek && intensityWeek.days > 0 ? String(intensityWeek.total) : null}
        unit="min"
      />
      <SummaryTile
        to="/sante/activite"
        label="Pas par jour"
        value={week?.steps_per_day != null ? formatNumber(week.steps_per_day, 0) : null}
      />
      <SummaryTile
        to="/sante/activite"
        label="Étages cette semaine"
        value={week && week.floor_days > 0 ? String(week.floors_ascended) : null}
      />
      <SummaryTile
        to="/sante/poids"
        label="Poids"
        value={lastWeight?.weight_kg != null ? formatNumber(lastWeight.weight_kg) : null}
        unit="kg"
      />
    </nav>
  )
}

function SummaryTile(props: { to: string; label: string; value: string | null; unit?: string }) {
  return (
    <Link to={props.to} className="tile">
      <span className="tile-label">{props.label}</span>
      <span className="tile-value">
        {props.value ?? '–'}
        {props.value !== null && props.unit && <span className="tile-unit"> {props.unit}</span>}
      </span>
    </Link>
  )
}

function SleepSection({ metrics }: { metrics: HealthMetrics }) {
  const days = metrics.days
  const pick = (getter: (day: HealthDay) => number | null) => days.map(getter)
  const sleepAverage = mean(pick(sleepHours))
  const bedtime = mean(pick((d) => d.bedtime_min))
  const wake = mean(pick((d) => d.wake_min))
  return (
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
      <p className="hint">
        Horaires : coucher {regularityLabel(metrics.regularity.bedtime_sd_min)}
        {metrics.regularity.bedtime_sd_min !== null &&
          ` (± ${metrics.regularity.bedtime_sd_min} min)`}
        , lever {regularityLabel(metrics.regularity.wake_sd_min)}
        {metrics.regularity.wake_sd_min !== null && ` (± ${metrics.regularity.wake_sd_min} min)`},
        sur {metrics.regularity.nights} nuits.
      </p>
      <Chart points={trendPoints(days, sleepHours)} name="Sommeil" unit="h" digits={1} />
    </section>
  )
}

function RecoverySection({ days }: { days: HealthDay[] }) {
  const pick = (getter: (day: HealthDay) => number | null) => days.map(getter)
  return (
    <section className="card" aria-labelledby="recovery-title">
      <h2 id="recovery-title">FC au repos et HRV</h2>
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
  )
}

function WeightSection({ days }: { days: HealthDay[] }) {
  const lastWeight = days.at(-1)
  return (
    <section className="card" aria-labelledby="weight-title">
      <h2 id="weight-title">Poids</h2>
      {lastWeight?.weight_kg != null && lastWeight.weight_measured_on ? (
        <>
          <dl className="stats">
            <Stat label="Dernier poids" value={`${formatNumber(lastWeight.weight_kg)} kg`} />
            <Stat label="Pesé le" value={formatShortDate(lastWeight.weight_measured_on)} />
          </dl>
          <p className="hint">Ce poids reste affiché jusqu’à ta prochaine pesée.</p>
          <Chart
            points={trendPoints(days, (d) => d.weight_kg)}
            name="Poids"
            unit="kg"
            digits={1}
            smooth={false}
          />
        </>
      ) : (
        <p className="hint">Aucune pesée pour l’instant (Garmin Connect ou saisie dans l’app).</p>
      )}
      <p className="hint">
        <Link to="/profil">Saisir une pesée dans mon profil</Link>
      </p>
    </section>
  )
}

/** Every day of the period, for the curious (and for screen readers). */
function DaysTable({ days }: { days: HealthDay[] }) {
  if (days.length === 0) return null
  return (
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
        {load.target !== null && <Stat label="Objectif par semaine" value={String(load.target)} />}
      </dl>
      <p>{acwrLabel(load.acwr)}</p>
      <p className="hint">
        Le ratio compare ta dernière semaine à tes habitudes. C’est un repère grossier, pas un
        diagnostic : écoute aussi tes sensations.
      </p>
      <p className="hint">
        {hr.max_hr && hr.resting_hr
          ? `Calcul avec ta FC (TRIMP) : max ${hr.max_hr} bpm${MAX_SOURCE_NOTE[hr.max_source ?? 'profile']}, repos ${hr.resting_hr} bpm${hr.resting_source === 'garmin' ? ' (Garmin)' : ''}.`
          : 'FC max ou de repos inconnue : la charge est estimée d’après la durée.'}{' '}
        {hr.max_source !== 'profile' && (
          <Link to="/profil">Renseigne ta FC max dans le profil.</Link>
        )}
      </p>
      <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
        <WeeklyBarChart
          weeks={load.weeks.map((week) => ({ date: week.monday, value: week.load }))}
          name="Charge"
          target={load.target}
        />
      </Suspense>
      {load.target === null && <GoalHint kind="Charge d’entraînement" />}
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

function IntensitySection({ intensity }: { intensity: IntensityMinutes }) {
  const current = intensity.weeks.at(-1)
  const hasData = intensity.weeks.some((week) => week.days > 0)
  return (
    <section className="card" aria-labelledby="intensity-title">
      <h2 id="intensity-title">Minutes d’intensité</h2>
      <dl className="stats">
        <Stat label="Cette semaine" value={current ? `${current.total} min` : null} />
        {intensity.target !== null && (
          <Stat label="Objectif par semaine" value={`${intensity.target} min`} />
        )}
      </dl>
      <p className="hint">
        Comptées par ta montre Garmin sur toute la journée : une minute intense compte double.
      </p>
      {hasData ? (
        <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
          <WeeklyBarChart
            weeks={intensity.weeks.map((week) => ({ date: week.monday, value: week.total }))}
            name="Minutes d’intensité"
            unit="min"
            target={intensity.target}
          />
        </Suspense>
      ) : (
        <p className="hint">Pas encore de minutes d’intensité : lance une synchro Garmin.</p>
      )}
      {intensity.target === null && <GoalHint kind="Minutes d’intensité (Garmin)" />}
      <details>
        <summary>Voir le tableau</summary>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th scope="col">Semaine du</th>
                <th scope="col">Total</th>
                <th scope="col">Modérées</th>
                <th scope="col">Intenses</th>
              </tr>
            </thead>
            <tbody>
              {[...intensity.weeks].reverse().map((week) => (
                <tr key={week.week}>
                  <td>{formatShortDate(week.monday)}</td>
                  <td>{week.days > 0 ? week.total : '–'}</td>
                  <td>{week.days > 0 ? week.moderate : '–'}</td>
                  <td>{week.days > 0 ? week.vigorous : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}

function StepsSection({ steps, days }: { steps: StepsAndFloors; days: HealthDay[] }) {
  const current = steps.weeks.at(-1)
  const daily = days.filter((day) => day.steps !== null)
  const target = steps.steps_target
  return (
    <section className="card" aria-labelledby="steps-title">
      <h2 id="steps-title">Pas</h2>
      <dl className="stats">
        <Stat
          label="Moyenne par jour cette semaine"
          value={current?.steps_per_day != null ? formatNumber(current.steps_per_day, 0) : null}
        />
        <Stat
          label="Moyenne sur la période"
          value={formatOrNull(mean(daily.map((day) => day.steps)), 0)}
        />
        {target !== null && <Stat label="Objectif par jour" value={formatNumber(target, 0)} />}
      </dl>
      {daily.length > 0 ? (
        <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
          {/* One bar per day of the chosen period; the goal is a daily target. */}
          <WeeklyBarChart
            weeks={daily.map((day) => ({ date: day.day, value: day.steps ?? 0 }))}
            name="Pas"
            target={target}
          />
        </Suspense>
      ) : (
        <p className="hint">Pas encore de pas sur cette période : lance une synchro Garmin.</p>
      )}
      {target === null && <GoalHint kind="Pas par jour (Garmin)" />}
    </section>
  )
}

function FloorsSection({ steps }: { steps: StepsAndFloors }) {
  const current = steps.weeks.at(-1)
  const hasFloors = steps.weeks.some((week) => week.floor_days > 0)
  const target = steps.floors_target
  return (
    <section className="card" aria-labelledby="floors-title">
      <h2 id="floors-title">Étages</h2>
      <dl className="stats">
        <Stat
          label="Montés cette semaine"
          value={current && current.floor_days > 0 ? String(current.floors_ascended) : null}
        />
        <Stat
          label="Descendus cette semaine"
          value={current && current.floor_days > 0 ? String(current.floors_descended) : null}
        />
        {target !== null && <Stat label="Objectif par semaine" value={`${target} étages`} />}
      </dl>
      <p className="hint">Comptés par ta montre : un étage correspond à environ 3 m de dénivelé.</p>
      {hasFloors ? (
        <Suspense fallback={<p className="hint">Chargement du graphique…</p>}>
          <WeeklyBarChart
            weeks={steps.weeks.map((week) => ({ date: week.monday, value: week.floors_ascended }))}
            name="Étages montés"
            unit="étages"
            target={target}
          />
        </Suspense>
      ) : (
        <p className="hint">Pas encore d’étages : lance une synchro Garmin.</p>
      )}
      {target === null && <GoalHint kind="Étages montés (Garmin)" />}
      <details>
        <summary>Voir le tableau</summary>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th scope="col">Semaine du</th>
                <th scope="col">Pas par jour</th>
                <th scope="col">Étages montés</th>
                <th scope="col">Étages descendus</th>
              </tr>
            </thead>
            <tbody>
              {[...steps.weeks].reverse().map((week) => (
                <tr key={week.week}>
                  <td>{formatShortDate(week.monday)}</td>
                  <td>{week.steps_per_day !== null ? formatNumber(week.steps_per_day, 0) : '–'}</td>
                  <td>{week.floor_days > 0 ? week.floors_ascended : '–'}</td>
                  <td>{week.floor_days > 0 ? week.floors_descended : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}

/** Link to the goals page when a chart has no goal line yet. */
function GoalHint({ kind }: { kind: string }) {
  return (
    <p className="hint">
      <Link to="/objectifs">Ajoute un objectif « {kind} »</Link> pour le voir sur ce graphique.
    </p>
  )
}

// Where the max HR comes from, shown after its value.
const MAX_SOURCE_NOTE = {
  profile: '',
  observed: ' (la plus haute mesurée par ta montre sur un an)',
  age: ' (estimée d’après ton âge)',
} as const

function formatOrNull(value: number | null, digits: number): string | null {
  const rounded = round(value, digits)
  return rounded === null ? null : formatNumber(rounded, digits)
}

function withUnit(value: number | null, unit: string): string | null {
  const text = formatOrNull(value, 0)
  return text === null ? null : `${text} ${unit}`
}
