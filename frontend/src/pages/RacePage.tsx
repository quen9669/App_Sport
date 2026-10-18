// "Course" page: current running form (VDOT), predicted race times, training
// paces, and the race FRANKS is preparing with its pace plan and feasibility.
// Every number is computed by the backend (app/services/race/); this page only
// displays it and sends the target race or a run to leave out.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  deleteRaceTarget,
  fetchRace,
  type Race,
  type RaceForm,
  type RaceTarget,
  type RaceTargetInput,
  saveRaceTarget,
  setRunExcluded,
} from '../api/client'
import { formatKm } from '../utils/activity'
import { RACE_BOUNDS, rangeError } from '../utils/bounds'
import { formatNumber, formatShortDate, todayIso } from '../utils/format'
import {
  FEASIBILITY_LABELS,
  formatPace,
  formatRaceTime,
  parseRaceTime,
  RACE_DISTANCES,
  ZONE_HINTS,
  ZONE_LABELS,
} from '../utils/race'

export default function RacePage() {
  const [race, setRace] = useState<Race | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchRace()
      .then((result) => {
        if (!cancelled) setRace(result)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger le prédicteur de course.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Every change answers with the whole screen: no second request needed.
  async function change(action: () => Promise<Race>): Promise<boolean> {
    setError(null)
    try {
      setRace(await action())
      return true
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le backend ne répond pas.')
      return false
    }
  }

  return (
    <>
      <h1>Course</h1>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {!race && !error && <p className="hint">Chargement…</p>}
      {race && (
        <>
          <FormCard form={race.form} />
          <TargetCard
            race={race}
            onSave={(target) => change(() => saveRaceTarget(target))}
            onDelete={() => change(() => deleteRaceTarget())}
          />
          {race.predictions.length > 0 && <PredictionsCard race={race} />}
          {race.zones.length > 0 && <ZonesCard race={race} />}
          <EffortsCard
            form={race.form}
            onExclude={(id, excluded) => change(() => setRunExcluded(id, excluded))}
          />
        </>
      )}
    </>
  )
}

const vdotText = (value: number) => formatNumber(value, 1)

function FormCard({ form }: { form: RaceForm }) {
  return (
    <section className="card" aria-labelledby="form-title">
      <h2 id="form-title">Ta forme</h2>
      {form.status === 'ok' && form.vdot !== null && form.low !== null && form.high !== null ? (
        <>
          <dl className="stats">
            <div>
              <dt>VDOT</dt>
              <dd>{vdotText(form.vdot)}</dd>
            </div>
            <div>
              <dt>Fourchette</dt>
              <dd>
                {vdotText(form.low)} à {vdotText(form.high)}
              </dd>
            </div>
          </dl>
          <p className="hint">
            Le VDOT (Jack Daniels) résume ta forme en course à pied : plus il est haut, plus tu vas
            vite. Il est calculé sur tes meilleures sorties récentes, avec ta fréquence cardiaque
            quand elle est connue.
          </p>
        </>
      ) : (
        <p className="notice" role="status">
          {form.reason ?? 'Pas assez de données pour estimer ta forme.'} Aucun temps n’est affiché
          tant que les données manquent.
        </p>
      )}
    </section>
  )
}

function PredictionsCard({ race }: { race: Race }) {
  return (
    <section className="card" aria-labelledby="predictions-title">
      <h2 id="predictions-title">Temps prédits</h2>
      <div className="table-scroll">
        <table className="activity-table" aria-label="Temps prédits">
          <thead>
            <tr>
              <th>Distance</th>
              <th className="num">Temps</th>
              <th className="num">Fourchette</th>
              <th className="num">Allure</th>
              <th className="num">Riegel</th>
            </tr>
          </thead>
          <tbody>
            {race.predictions.map((p) => (
              <tr key={p.label}>
                <td>{p.label}</td>
                <td className="num">
                  <strong>{formatRaceTime(p.time_s)}</strong>
                </td>
                <td className="num">
                  {formatRaceTime(p.fastest_s)} à {formatRaceTime(p.slowest_s)}
                </td>
                <td className="num">{formatPace(p.time_s / (p.distance_m / 1000))} /km</td>
                <td className="num">{formatRaceTime(p.riegel_s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        Temps possibles le jour J, bien préparé et à fond, sur un parcours plat. La colonne Riegel
        est un deuxième avis, calculé à partir du 5 km prédit : plus prudent sur les longues
        distances.
      </p>
    </section>
  )
}

function ZonesCard({ race }: { race: Race }) {
  return (
    <section className="card" aria-labelledby="zones-title">
      <h2 id="zones-title">Allures d’entraînement</h2>
      <div className="table-scroll">
        <table className="activity-table" aria-label="Allures d’entraînement">
          <thead>
            <tr>
              <th>Zone</th>
              <th className="num">Allure (min/km)</th>
              <th>Pour quoi</th>
            </tr>
          </thead>
          <tbody>
            {race.zones.map((zone) => (
              <tr key={zone.key}>
                <td>{ZONE_LABELS[zone.key]}</td>
                <td className="num">
                  {zone.slow_s_per_km === zone.fast_s_per_km
                    ? formatPace(zone.fast_s_per_km)
                    : `${formatPace(zone.slow_s_per_km)} à ${formatPace(zone.fast_s_per_km)}`}
                </td>
                <td>{ZONE_HINTS[zone.key]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

// --- The target race --------------------------------------------------------------

interface Draft {
  name: string
  distance: string // metres of a standard distance, or "other"
  otherKm: string
  date: string
  time: string // "50:00", may be empty
  gain: string // metres of climbing, "0" = flat
}

function draftOf(target: RaceTarget | null): Draft {
  if (!target) {
    return { name: '', distance: '10000', otherKm: '', date: '', time: '', gain: '0' }
  }
  const standard = RACE_DISTANCES.find((d) => d.meters === target.distance_m)
  return {
    name: target.name,
    distance: standard ? String(standard.meters) : 'other',
    otherKm: standard ? '' : String(target.distance_m / 1000),
    date: target.race_date,
    time: target.target_time_s === null ? '' : formatRaceTime(target.target_time_s),
    gain: String(target.elevation_gain_m),
  }
}

/** The draft as the backend expects it, or a French error message. */
function inputOf(draft: Draft): RaceTargetInput | string {
  const km = draft.distance === 'other' ? Number(draft.otherKm) : Number(draft.distance) / 1000
  const distanceError = rangeError(km, RACE_BOUNDS.distance_km, 'km')
  if (distanceError) return `Distance : ${distanceError.toLowerCase()}`
  if (!draft.date) return 'Choisis la date de la course.'
  const gain = Number(draft.gain || '0')
  const gainError = rangeError(gain, RACE_BOUNDS.elevation_gain_m, 'm')
  if (gainError) return `Dénivelé : ${gainError.toLowerCase()}`
  let time: number | null = null
  if (draft.time.trim()) {
    time = parseRaceTime(draft.time)
    if (time === null) return 'Temps visé : écris-le comme 50:00 ou 1:45:00.'
    if (rangeError(time, RACE_BOUNDS.target_time_s)) return 'Temps visé : entre 2:00 et 24:00:00.'
  }
  return {
    name: draft.name.trim(),
    distance_m: km * 1000,
    race_date: draft.date,
    target_time_s: time,
    elevation_gain_m: gain,
  }
}

function TargetCard({
  race,
  onSave,
  onDelete,
}: {
  race: Race
  onSave: (target: RaceTargetInput) => Promise<boolean>
  onDelete: () => Promise<boolean>
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(race.target))
  const [problem, setProblem] = useState<string | null>(null)
  const set = (field: keyof Draft) => (event: { target: { value: string } }) =>
    setDraft({ ...draft, [field]: event.target.value })

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const input = inputOf(draft)
    if (typeof input === 'string') {
      setProblem(input)
      return
    }
    setProblem(null)
    await onSave(input)
  }

  async function remove() {
    if (await onDelete()) setDraft(draftOf(null))
  }

  return (
    <section className="card" aria-labelledby="target-title">
      <h2 id="target-title">Ma course</h2>
      {race.target && <TargetResult target={race.target} form={race.form} />}
      <form className="form" aria-label="Préparer une course" onSubmit={submit} noValidate>
        <label>
          Nom (facultatif)
          <input value={draft.name} maxLength={120} onChange={set('name')} />
        </label>
        <label>
          Distance
          <select value={draft.distance} onChange={set('distance')}>
            {RACE_DISTANCES.map((d) => (
              <option key={d.meters} value={d.meters}>
                {d.label}
              </option>
            ))}
            <option value="other">Autre distance</option>
          </select>
        </label>
        {draft.distance === 'other' && (
          <label>
            Distance (km)
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={draft.otherKm}
              onChange={set('otherKm')}
            />
          </label>
        )}
        <label>
          Date
          <input type="date" min={todayIso()} value={draft.date} onChange={set('date')} />
        </label>
        <label>
          Temps visé (facultatif, ex. 50:00)
          <input
            inputMode="numeric"
            placeholder="50:00"
            value={draft.time}
            onChange={set('time')}
          />
        </label>
        <label>
          Dénivelé positif (m, 0 = plat)
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={draft.gain}
            onChange={set('gain')}
          />
        </label>
        {problem && (
          <p className="field-error" role="alert">
            {problem}
          </p>
        )}
        <div className="actions">
          <button type="submit" className="button">
            Enregistrer
          </button>
          {race.target && (
            <button type="button" className="secondary" onClick={remove}>
              Supprimer la course
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

const weeksText = (days: number) => {
  if (days < 0) return 'La course est passée.'
  if (days === 0) return 'C’est aujourd’hui !'
  if (days < 14) return `Dans ${days} jour${days > 1 ? 's' : ''}.`
  return `Dans ${Math.floor(days / 7)} semaines (${days} jours).`
}

function TargetResult({ target, form }: { target: RaceTarget; form: RaceForm }) {
  const title = target.name || `${formatKm(target.distance_m)}`
  return (
    <div aria-label="Plan de course" role="group">
      <p>
        <strong>{title}</strong>, le {formatShortDate(target.race_date)}{' '}
        {target.race_date.slice(0, 4)}. {weeksText(target.days_left)}
      </p>
      <FeasibilityText target={target} form={form} />
      {target.pace_plan && (
        <>
          <p>
            Allure moyenne :{' '}
            <strong>{formatPace(target.pace_plan.average_pace_s_per_km)} /km</strong> pour{' '}
            {formatRaceTime(target.pace_plan.target_time_s)}
            {target.pace_plan.hill_allowance_s > 0 &&
              `, dont environ ${formatRaceTime(target.pace_plan.hill_allowance_s)} pour le dénivelé`}
            . Pars un peu plus lentement (1 %) puis accélère sur la seconde moitié.
          </p>
          <div className="table-scroll">
            <table className="activity-table" aria-label="Passages au kilomètre">
              <thead>
                <tr>
                  <th className="num">Km</th>
                  <th className="num">Allure</th>
                  <th className="num">Passage</th>
                </tr>
              </thead>
              <tbody>
                {target.pace_plan.splits.map((split) => (
                  <tr key={split.km}>
                    <td className="num">{formatNumber(split.km, 2)}</td>
                    <td className="num">{formatPace(split.pace_s_per_km)}</td>
                    <td className="num">{formatRaceTime(split.elapsed_s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function FeasibilityText({ target, form }: { target: RaceTarget; form: RaceForm }) {
  if (target.predicted_s === null) {
    return <p className="hint">Prédiction indisponible tant que ta forme n’est pas estimée.</p>
  }
  const predicted = `Prédiction actuelle : ${formatRaceTime(target.predicted_s)}.`
  if (!target.feasibility || target.required_vdot === null || form.vdot === null) {
    return <p>{predicted}</p>
  }
  const { verdict, gap_s } = target.feasibility
  const needs = `Ton objectif demande un VDOT de ${vdotText(target.required_vdot)}, tu es à ${vdotText(form.vdot)}.`
  const explanation = {
    realistic: 'Il est dans tes cordes aujourd’hui : garde la régularité.',
    ambitious: `Il faut gagner environ ${formatRaceTime(-gap_s)} : c’est dans le haut de ta fourchette, jouable avec une bonne préparation.`,
    unlikely: `Il faut gagner environ ${formatRaceTime(-gap_s)} : au-delà de ta fourchette actuelle. Possible si ta forme progresse d’ici là, sinon vise un temps intermédiaire.`,
  }[verdict]
  return (
    <p>
      <span className={`badge feasibility--${verdict}`}>{FEASIBILITY_LABELS[verdict]}</span>{' '}
      {predicted} {needs} {explanation}
    </p>
  )
}

// --- The runs behind the estimate ------------------------------------------------------

function EffortsCard({
  form,
  onExclude,
}: {
  form: RaceForm
  onExclude: (activityId: number, excluded: boolean) => Promise<boolean>
}) {
  if (form.efforts.length === 0 && form.excluded.length === 0) return null
  return (
    <section className="card" aria-labelledby="efforts-title">
      <h2 id="efforts-title">Sorties utilisées</h2>
      <p className="hint">
        Sorties d’au moins 3 km des 120 derniers jours, peu vallonnées et à allure régulière. Une
        sortie compte deux fois moins au bout de 45 jours. En gras : celles qui font l’estimation. «
        FC » : estimée avec ta fréquence cardiaque ; « meilleur 5 km » : le passage le plus rapide
        d’une sortie plus longue.
      </p>
      {form.efforts.length > 0 && (
        <div className="table-scroll">
          <table className="activity-table" aria-label="Sorties utilisées">
            <thead>
              <tr>
                <th>Date</th>
                <th>Activité</th>
                <th className="num">Distance</th>
                <th className="num">Temps</th>
                <th className="num">VDOT</th>
                <th>Méthode</th>
                <th>
                  <span className="visually-hidden">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {form.efforts.map((effort) => (
                <tr key={effort.activity_id} className={effort.used ? 'row--used' : undefined}>
                  <td>{formatShortDate(effort.day)}</td>
                  <td className="name">
                    <Link to={`/activites/${effort.activity_id}`} title={effort.name}>
                      {effort.name || 'Course'}
                    </Link>
                  </td>
                  <td className="num">
                    {effort.segment
                      ? `meilleur ${formatKm(effort.distance_m)}`
                      : formatKm(effort.distance_m)}
                  </td>
                  <td className="num">{formatRaceTime(effort.time_s)}</td>
                  <td className="num">{vdotText(effort.vdot)}</td>
                  <td>{effort.method === 'heart_rate' ? 'FC' : 'Chrono'}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => onExclude(effort.activity_id, true)}
                      aria-label={`Exclure ${effort.name || 'cette sortie'}`}
                    >
                      Exclure
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {form.excluded.length > 0 && (
        <>
          <h3>Sorties exclues</h3>
          <ul className="goal-list">
            {form.excluded.map((run) => (
              <li key={run.activity_id}>
                {formatShortDate(run.day)} · {run.name || 'Course'} · {formatKm(run.distance_m)}{' '}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => onExclude(run.activity_id, false)}
                  aria-label={`Réintégrer ${run.name || 'cette sortie'}`}
                >
                  Réintégrer
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
