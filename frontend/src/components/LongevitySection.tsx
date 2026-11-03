// "Longévité" tab of the Santé folder: the levers of long-term health, each
// against its public reference and with how solid the evidence is, then what
// quitting cigarettes has changed in the watch's data. Read-only: the numbers
// come from GET /api/longevity, the words from utils/longevity.ts.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchLongevity, type Longevity, type LongevityIndicator } from '../api/client'
import { formatNumber, formatShortDate } from '../utils/format'
import {
  COMPARISON_LABELS,
  EVIDENCE_LABELS,
  formatChange,
  formatIndicator,
  INDICATOR_TEXTS,
  milestoneProgress,
  STATUS_LABELS,
} from '../utils/longevity'

const plural = (count: number, word: string) => `${count} ${word}${count > 1 ? 's' : ''}`

export default function LongevitySection() {
  const [data, setData] = useState<Longevity | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchLongevity()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger le bilan longévité.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error)
    return (
      <p className="field-error" role="alert">
        {error}
      </p>
    )
  if (!data) return <p className="hint">Chargement…</p>

  return (
    <>
      <section className="card" aria-labelledby="levers-title">
        <h2 id="levers-title">Tes leviers</h2>
        <p className="hint">
          Chaque carte compare ton chiffre à un repère public quand il en existe un, et dit à quel
          point le lien avec la santé à long terme est solide.
        </p>
        <ul className="longevity-grid">
          {data.indicators.map((indicator) => (
            <IndicatorCard key={indicator.key} indicator={indicator} />
          ))}
        </ul>
      </section>
      <SmokeFreeCard data={data.smoke_free} />
      <p className="hint">
        <Link to="/longevite">En parler au coach longévité</Link>
      </p>
    </>
  )
}

function IndicatorCard({ indicator }: { indicator: LongevityIndicator }) {
  const text = INDICATOR_TEXTS[indicator.key]
  if (!text) return null // a key this version of the screen does not know yet
  const titleId = `lever-${indicator.key}`
  return (
    <li className="longevity-item" aria-labelledby={titleId}>
      <h3 id={titleId}>{text.label}</h3>
      <p className="tile-value">{formatIndicator(indicator, indicator.value)}</p>
      <p className="hint">
        {indicator.value === null ? 'Pas encore assez de données' : text.period}
        {indicator.previous !== null &&
          ` · ${text.previousLabel} : ${formatIndicator(indicator, indicator.previous)}`}
      </p>
      <p className="longevity-badges">
        {indicator.status && (
          <span className={`badge status--${indicator.status}`}>
            {STATUS_LABELS[indicator.status]}
          </span>
        )}
        <span className="badge">{EVIDENCE_LABELS[indicator.evidence]}</span>
      </p>
      <p className="hint">{text.reference}</p>
    </li>
  )
}

function SmokeFreeCard({ data }: { data: Longevity['smoke_free'] }) {
  const { reached, next } = milestoneProgress(data.days_since_quit)
  return (
    <section className="card" aria-labelledby="quit-title">
      <h2 id="quit-title">Depuis l’arrêt de la cigarette</h2>
      <dl className="stats">
        <div>
          <dt>Arrêt le</dt>
          <dd>
            {formatShortDate(data.quit_date)} {data.quit_date.slice(0, 4)}
          </dd>
        </div>
        <div>
          <dt>Jours depuis</dt>
          <dd>{data.days_since_quit}</dd>
        </div>
        <div>
          <dt>Série en cours</dt>
          <dd>{plural(data.current_streak, 'jour')}</dd>
        </div>
        <div>
          <dt>Cigarettes depuis</dt>
          <dd>{data.cigarettes}</dd>
        </div>
      </dl>
      <p className="hint">
        <Link to="/sante/tabac">Noter un jour avec cigarette</Link>
      </p>

      <h3>Ce que disent les repères de l’OMS</h3>
      {reached.length > 0 ? (
        <ul className="milestones">
          {reached.map((m) => (
            <li key={m.when}>
              <span aria-hidden="true">✓ </span>
              <strong>{m.when}</strong> : {m.text}
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">Le premier repère arrive dès le premier jour.</p>
      )}
      {next && (
        <p>
          Prochain repère dans {plural(next.daysLeft, 'jour')} ({next.milestone.when}) :{' '}
          {next.milestone.text}
        </p>
      )}
      <p className="hint">
        Ces repères décrivent un arrêt complet du tabac. La vapoteuse évite la combustion mais garde
        la nicotine, qui agit sur le cœur et les vaisseaux.
      </p>

      <h3>Tes données avant et depuis l’arrêt</h3>
      <ComparisonTable data={data} />
      <p className="hint">
        Ce tableau montre ce qui a changé, pas pourquoi : l’entraînement, la saison, le stress et la
        vapoteuse jouent aussi. Une moyenne demande au moins 7 jours de données.
      </p>
    </section>
  )
}

function ComparisonTable({ data }: { data: Longevity['smoke_free'] }) {
  const before = `${formatShortDate(data.before_start)} – ${formatShortDate(data.before_end)}`
  const since = `${formatShortDate(data.after_start)} – aujourd’hui`
  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th scope="col">Mesure</th>
            <th scope="col">Avant ({before})</th>
            <th scope="col">Depuis ({since})</th>
            <th scope="col">Écart</th>
          </tr>
        </thead>
        <tbody>
          {data.comparisons.map((row) => {
            const text = COMPARISON_LABELS[row.key] ?? { label: row.key, digits: 0 }
            const value = (v: number | null) =>
              v === null ? '–' : `${formatNumber(v, text.digits)} ${row.unit}`
            return (
              <tr key={row.key}>
                <th scope="row">{text.label}</th>
                <td>{value(row.before)}</td>
                <td>{value(row.after)}</td>
                <td>{formatChange(row.before, row.after, text.digits)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
