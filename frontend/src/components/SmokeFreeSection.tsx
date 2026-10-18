// "Sans cigarette" card of the Santé page: smoke-free days since the quit date,
// the current streak, and the occasional day with a cigarette, written in a few
// taps. Only the days WITH a cigarette are saved: every other day counts as
// smoke-free. Vaping is not counted here.
import { useEffect, useState } from 'react'

import {
  ApiError,
  deleteCigaretteDay,
  fetchSmoking,
  saveCigaretteDay,
  saveQuitDate,
  type Smoking,
} from '../api/client'
import { CIGARETTE_BOUNDS, rangeError } from '../utils/bounds'
import { formatNumber, formatShortDate, todayIso } from '../utils/format'

const plural = (count: number, word: string) => `${count} ${word}${count > 1 ? 's' : ''}`

/** "2026-09" -> "septembre 2026". */
function monthLabel(month: string): string {
  const [year, number] = month.split('-').map(Number) as [number, number]
  return new Date(Date.UTC(year, number - 1, 1)).toLocaleDateString('fr-FR', {
    timeZone: 'UTC',
    month: 'long',
    year: 'numeric',
  })
}

/** "1 sept. 2026": the short date, with the year (the quit date can be years ago). */
const longDate = (isoDate: string) => `${formatShortDate(isoDate)} ${isoDate.slice(0, 4)}`

export default function SmokeFreeSection() {
  const [data, setData] = useState<Smoking | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchSmoking()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger le suivi tabac.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Every change answers with the new counters: no second request needed.
  async function change(action: () => Promise<Smoking>): Promise<boolean> {
    setError(null)
    try {
      setData(await action())
      return true
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le backend ne répond pas.')
      return false
    }
  }

  return (
    <section className="card" aria-labelledby="smoke-title">
      <h2 id="smoke-title">Sans cigarette</h2>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {data && <Counters data={data} />}
      {data && (
        <CigaretteForm
          today={data.today}
          onSave={(day, count, note) => change(() => saveCigaretteDay(day, count, note))}
        />
      )}
      {data && data.months.length > 0 && <Months data={data} />}
      {data && data.entries.length > 0 && (
        <CigaretteList data={data} onDelete={(day) => change(() => deleteCigaretteDay(day))} />
      )}
      {data && <QuitDate data={data} onSave={(quitDate) => change(() => saveQuitDate(quitDate))} />}
    </section>
  )
}

function Counters({ data }: { data: Smoking }) {
  const share = data.days_since_quit
    ? `${formatNumber((100 * data.smoke_free_days) / data.days_since_quit, 0)} %`
    : '–'
  return (
    <>
      <p className="hint">
        Depuis le {longDate(data.quit_date)} : {plural(data.days_since_quit, 'jour')}.
      </p>
      <dl className="stats">
        <div>
          <dt>Jours sans cigarette</dt>
          <dd>
            {data.smoke_free_days} ({share})
          </dd>
        </div>
        <div>
          <dt>Série en cours</dt>
          <dd>{plural(data.current_streak, 'jour')}</dd>
        </div>
        <div>
          <dt>Record</dt>
          <dd>{plural(data.longest_streak, 'jour')}</dd>
        </div>
        <div>
          <dt>Cigarettes depuis l’arrêt</dt>
          <dd>{data.cigarettes}</dd>
        </div>
      </dl>
    </>
  )
}

/** "+ J'ai fumé": the day (today by default), how many, and an optional note. */
function CigaretteForm({
  today,
  onSave,
}: {
  today: string
  onSave: (day: string, count: number, note: string | null) => Promise<boolean>
}) {
  const [open, setOpen] = useState(false)
  const [day, setDay] = useState(today)
  const [count, setCount] = useState('1')
  const [note, setNote] = useState('')
  const [problem, setProblem] = useState<string | null>(null)

  async function save() {
    const value = Number(count)
    const invalid = !Number.isInteger(value)
      ? 'Nombre entier attendu'
      : rangeError(value, CIGARETTE_BOUNDS)
    if (invalid) {
      setProblem(invalid)
      return
    }
    setProblem(null)
    if (await onSave(day, value, note.trim() || null)) {
      setOpen(false)
      setNote('')
      setCount('1')
    }
  }

  if (!open) {
    return (
      <div className="actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setDay(todayIso())
            setOpen(true)
          }}
        >
          + J’ai fumé
        </button>
      </div>
    )
  }
  return (
    <div className="inline-fields">
      <label>
        Jour
        <input type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} />
      </label>
      <label>
        Cigarettes
        <input
          type="number"
          inputMode="numeric"
          min={CIGARETTE_BOUNDS.min}
          max={CIGARETTE_BOUNDS.max}
          value={count}
          onChange={(e) => setCount(e.target.value)}
          aria-invalid={problem ? true : undefined}
        />
      </label>
      <label>
        Note (facultatif)
        <input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void save()}>
          Enregistrer
        </button>
        <button type="button" className="secondary" onClick={() => setOpen(false)}>
          Annuler
        </button>
      </div>
      {problem && (
        <p className="field-error" role="alert">
          {problem}
        </p>
      )}
    </div>
  )
}

function Months({ data }: { data: Smoking }) {
  return (
    <>
      <h3>Mois par mois</h3>
      <ul className="activity-list">
        {[...data.months].reverse().map((month) => (
          <li key={month.month}>
            <div>
              <strong>{monthLabel(month.month)}</strong>
              <span className="hint">
                {' '}
                {month.smoke_free_days}/{month.days} jours sans cigarette
                {month.cigarettes > 0 && ` · ${plural(month.cigarettes, 'cigarette')}`}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}

function CigaretteList({
  data,
  onDelete,
}: {
  data: Smoking
  onDelete: (day: string) => Promise<boolean>
}) {
  return (
    <>
      <h3>Jours avec cigarette</h3>
      <ul className="activity-list">
        {data.entries.map((entry) => (
          <li key={entry.day}>
            <div>
              <strong>{longDate(entry.day)}</strong>
              <span className="hint">
                {' '}
                {plural(entry.cigarettes, 'cigarette')}
                {entry.note && ` · ${entry.note}`}
              </span>
            </div>
            <button
              type="button"
              className="secondary"
              aria-label={`Supprimer le ${longDate(entry.day)}`}
              onClick={() => void onDelete(entry.day)}
            >
              Supprimer
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

/** The quit date: the app's default (1 September 2026) until changed here. */
function QuitDate({
  data,
  onSave,
}: {
  data: Smoking
  onSave: (quitDate: string) => Promise<boolean>
}) {
  const [value, setValue] = useState(data.quit_date)
  return (
    <details>
      <summary>Modifier la date d’arrêt</summary>
      <div className="inline-fields">
        <label>
          Date d’arrêt
          <input
            type="date"
            value={value}
            max={data.today}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <div className="actions">
          <button type="button" onClick={() => void onSave(value)} disabled={!value}>
            Enregistrer la date
          </button>
        </div>
      </div>
      {data.quit_date_is_default && (
        <p className="hint">Date par défaut, pas encore enregistrée.</p>
      )}
    </details>
  )
}
