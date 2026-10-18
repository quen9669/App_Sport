// Under a run of the accepted plan (Mon plan page): send it to the Garmin watch,
// take it back, or edit its steps first. Nothing goes to Garmin without a click.
import { useState } from 'react'

import {
  type CoachPlan,
  removeSessionFromGarmin,
  sendSessionToGarmin,
  updateSessionWorkout,
} from '../api/client'
import { formatShortDate, todayIso } from '../utils/format'
import WorkoutEditor from './WorkoutEditor'

interface Props {
  plan: CoachPlan
  index: number
  /** The backend answers with the updated plan: the page redraws it. */
  onPlanChange: (plan: CoachPlan) => void
}

export default function RunGarminActions({ plan, index, onPlanChange }: Props) {
  const session = plan.sessions[index]
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!session?.workout) return null

  async function run(action: () => Promise<CoachPlan>) {
    setBusy(true)
    setError(null)
    try {
      onPlanChange(await action())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Garmin n’a pas répondu.')
    } finally {
      setBusy(false)
    }
  }

  if (editing) {
    return (
      <WorkoutEditor
        workout={session.workout}
        onCancel={() => setEditing(false)}
        onSave={async (workout) => {
          // Errors go back to the editor, which shows them.
          onPlanChange(await updateSessionWorkout(plan.id, index, workout))
          setEditing(false)
        }}
      />
    )
  }

  const past = session.day < todayIso()
  return (
    <div className="garmin-actions">
      {session.garmin ? (
        <>
          <span className="garmin-sent">
            ⌚ Sur ta Garmin (envoyée le {formatShortDate(session.garmin.sent_at.slice(0, 10))})
          </span>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => run(() => removeSessionFromGarmin(plan.id, index))}
          >
            Retirer de ma Garmin
          </button>
        </>
      ) : past ? (
        <span className="hint">Séance passée</span>
      ) : (
        <>
          <button
            type="button"
            disabled={busy}
            onClick={() => run(() => sendSessionToGarmin(plan.id, index))}
          >
            {busy ? 'Envoi…' : 'Envoyer sur ma Garmin'}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => setEditing(true)}
          >
            Modifier les étapes
          </button>
        </>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
