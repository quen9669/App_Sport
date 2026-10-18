// A week of sessions proposed by the coach. In the chat it has "Accepter",
// "Modifier" and "Refuser"; on the Accueil page (accepted plan) it is read-only.
// Built from React elements only: the texts come from the model.
import type { CoachPlan, PlanSessionKind } from '../api/client'
import { formatShortDate } from '../utils/format'

const KINDS: Record<PlanSessionKind, { emoji: string; label: string }> = {
  run: { emoji: '🏃', label: 'Course' },
  ride: { emoji: '🚴', label: 'Vélo' },
  strength: { emoji: '🏋️', label: 'Muscu' },
  class: { emoji: '🤸', label: 'Cours collectif' },
  walk: { emoji: '🚶', label: 'Marche' },
  mobility: { emoji: '🧘', label: 'Mobilité' },
  rest: { emoji: '😴', label: 'Repos' },
  other: { emoji: '✳️', label: 'Autre' },
}

const STATUS_TEXT: Record<CoachPlan['status'], string> = {
  proposed: 'Proposé',
  accepted: 'Accepté : il est sur l’Accueil',
  rejected: 'Refusé',
  replaced: 'Remplacé par un plan plus récent',
}

/** "lun. 19 oct." from a plain ISO date (no timezone shift). */
function dayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number) as [number, number, number]
  const weekday = new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('fr-FR', {
    timeZone: 'UTC',
    weekday: 'short',
  })
  return `${weekday} ${formatShortDate(isoDate)}`
}

interface Props {
  plan: CoachPlan
  /** Chat only: accept or reject the plan. */
  onDecide?: (accepted: boolean) => void
  /** Chat only: start a message asking the coach to change the plan. */
  onModify?: () => void
  disabled?: boolean
}

export default function PlanCard({ plan, onDecide, onModify, disabled }: Props) {
  const title = `Plan de la semaine du ${formatShortDate(plan.week_start)}`
  return (
    <article className="plan-card" aria-label={title}>
      <h3>{title}</h3>
      <p>{plan.summary}</p>
      <ol className="plan-sessions">
        {plan.sessions.map((session, i) => {
          const kind = KINDS[session.kind]
          return (
            <li key={i} className={`plan-session plan-session--${session.kind}`}>
              <span className="plan-day">{dayLabel(session.day)}</span>
              <span>
                <span aria-hidden="true">{kind.emoji} </span>
                <strong>{session.title}</strong>
                <span className="visually-hidden"> ({kind.label})</span>
                {session.duration_min > 0 && ` · ${session.duration_min} min`}
                {session.intensity && ` · ${session.intensity}`}
                {session.details && <span className="plan-details">{session.details}</span>}
                <span className="hint plan-why">{session.why}</span>
              </span>
            </li>
          )
        })}
      </ol>
      {plan.status === 'proposed' && onDecide ? (
        <div className="plan-actions">
          <button type="button" onClick={() => onDecide(true)} disabled={disabled}>
            Accepter
          </button>
          <button type="button" className="secondary" onClick={onModify} disabled={disabled}>
            Modifier
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => onDecide(false)}
            disabled={disabled}
          >
            Refuser
          </button>
        </div>
      ) : (
        onDecide && <p className="hint">{STATUS_TEXT[plan.status]}</p>
      )}
    </article>
  )
}
