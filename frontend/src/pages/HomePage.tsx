// Home page: the week's goal rings, the week's sessions, the coach's accepted
// plan and the quick weigh-in.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  fetchHealth,
  fetchWeekProgress,
  setActivityCategory,
  setActivityHidden,
  type Category,
  type WeekActivity,
  type WeekProgress,
} from '../api/client'
import ActivityTable from '../components/ActivityTable'
import GoalRing from '../components/GoalRing'
import QuickWeight from '../components/QuickWeight'
import WeekPlanSection from '../components/WeekPlanSection'
import { CATEGORY_LABELS, formatDayTime, formatShortDate } from '../utils/format'

/** The three states of the backend check, shown with different messages. */
type BackendStatus = 'loading' | 'ok' | 'error'

const STATUS_LABELS: Record<BackendStatus, string> = {
  loading: 'Connexion au backend…',
  ok: 'Backend OK',
  error: 'Backend injoignable',
}

const CATEGORIES: Category[] = ['strength', 'cardio', 'transport', 'other']

export default function HomePage() {
  const [status, setStatus] = useState<BackendStatus>('loading')
  // undefined = current week; otherwise an ISO week such as "2026-W41".
  const [week, setWeek] = useState<string | undefined>(undefined)
  const [progress, setProgress] = useState<WeekProgress | null>(null)
  const [error, setError] = useState<string | null>(null)

  // useEffect runs after the first render: the right place to call the API.
  useEffect(() => {
    // If the component disappears before the answer arrives, ignore the answer
    // (otherwise React would try to update a component that no longer exists).
    let cancelled = false
    fetchHealth()
      .then(() => {
        if (!cancelled) setStatus('ok')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loadWeek = useCallback(() => fetchWeekProgress(week), [week])

  // Reload the week whenever the selected week changes.
  useEffect(() => {
    let cancelled = false
    loadWeek()
      .then((data) => {
        if (!cancelled) {
          setProgress(data)
          setError(null)
        }
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger la semaine.')
      })
    return () => {
      cancelled = true
    }
  }, [loadWeek])

  async function changeCategory(activity: WeekActivity, category: Category) {
    try {
      // Picking the automatic category again removes the manual correction.
      await setActivityCategory(
        activity.id,
        category === activity.automatic_category ? null : category,
      )
      setProgress(await loadWeek())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le backend ne répond pas.')
    }
  }

  async function toggleHidden(activity: WeekActivity) {
    try {
      await setActivityHidden(activity.id, !activity.hidden)
      setProgress(await loadWeek())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le backend ne répond pas.')
    }
  }

  return (
    <>
      <h1>App Sport</h1>
      <p className="subtitle">Ton application de sport personnelle</p>
      <p className={`status status--${status}`} role="status">
        {STATUS_LABELS[status]}
      </p>

      <section className="card" aria-labelledby="week-title">
        <div className="week-header">
          <button
            type="button"
            className="secondary"
            aria-label="Semaine précédente"
            disabled={!progress}
            onClick={() => setWeek(progress?.previous_week)}
          >
            ‹
          </button>
          <h2 id="week-title">
            {progress
              ? `Semaine du ${formatShortDate(progress.monday)} au ${formatShortDate(progress.sunday)}`
              : 'Ma semaine'}
          </h2>
          <button
            type="button"
            className="secondary"
            aria-label="Semaine suivante"
            disabled={!progress}
            onClick={() => setWeek(progress?.next_week)}
          >
            ›
          </button>
        </div>

        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}

        {progress && progress.goals.length === 0 && (
          <p className="hint">
            Aucun objectif actif. <Link to="/objectifs">Définis tes objectifs</Link>, par exemple 3
            séances de musculation et 3 de cardio par semaine.
          </p>
        )}
        {progress && progress.goals.length > 0 && (
          <div className="rings">
            {progress.goals.map((item) => (
              <GoalRing key={item.goal.id} progress={item} />
            ))}
          </div>
        )}

        {progress && (
          <>
            <h3>Séances de la semaine</h3>
            {progress.activities.length === 0 && progress.sessions.length === 0 && (
              <p className="hint">Aucune séance pour l’instant.</p>
            )}
            {progress.activities.length > 0 && (
              <ActivityTable
                rows={progress.activities}
                label="Séances de la semaine"
                rowClass={(activity) => (activity.hidden ? 'row--hidden' : undefined)}
                extra={[
                  {
                    header: 'Catégorie',
                    cell: (activity) => (
                      <CategoryCell
                        activity={activity}
                        onCategory={(category) => void changeCategory(activity, category)}
                        onToggleHidden={() => void toggleHidden(activity)}
                      />
                    ),
                  },
                ]}
              />
            )}
            {progress.sessions.length > 0 && (
              <>
                <h3>Musculation saisie</h3>
                <ul className="activity-list">
                  {progress.sessions.map((session) => (
                    <li key={session.id}>
                      <div>
                        <strong>{session.exercises.join(', ')}</strong>
                        <span className="hint">
                          {' '}
                          {formatDayTime(session.performed_at)} · {session.set_count} série
                          {session.set_count > 1 ? 's' : ''}
                        </span>
                      </div>
                      {!session.counted && <span className="hint">Déjà comptée via la montre</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </section>

      <WeekPlanSection />

      <section className="card" aria-labelledby="weight-title">
        <h2 id="weight-title">Poids</h2>
        <QuickWeight />
        <p className="hint">
          <Link to="/profil">Voir la courbe et mon profil</Link>
        </p>
      </section>
    </>
  )
}

/** Category picker, plus the duplicate/hidden badges and the hide button. */
function CategoryCell({
  activity,
  onCategory,
  onToggleHidden,
}: {
  activity: WeekActivity
  onCategory: (category: Category) => void
  onToggleHidden: () => void
}) {
  return (
    <span className="category-cell">
      {/* A correction is one tap on the list, a second one on the new category. */}
      <select
        aria-label={`Catégorie de ${activity.name}`}
        value={activity.category}
        onChange={(event) => onCategory(event.target.value as Category)}
      >
        {CATEGORIES.map((category) => (
          <option key={category} value={category}>
            {CATEGORY_LABELS[category]}
            {category === activity.automatic_category ? ' (auto)' : ''}
          </option>
        ))}
      </select>
      {/* Garmin and Strava may both have this session: let the user pick. */}
      {activity.possible_duplicate && !activity.hidden && (
        <span className="badge">Doublon possible</span>
      )}
      {activity.hidden && <span className="badge">Masquée</span>}
      {(activity.possible_duplicate || activity.hidden) && (
        <button
          type="button"
          className="secondary"
          aria-label={`${activity.hidden ? 'Réafficher' : 'Masquer'} ${activity.name}`}
          onClick={onToggleHidden}
        >
          {activity.hidden ? 'Réafficher' : 'Masquer'}
        </button>
      )}
    </span>
  )
}
