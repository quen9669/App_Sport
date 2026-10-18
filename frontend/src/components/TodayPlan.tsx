// "Ma semaine": today's session from the accepted weekly plan, as one line
// that opens "Mon plan". Without a plan, a link to ask the coach for one.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchCurrentPlans, type CurrentPlans } from '../api/client'
import { todayIso } from '../utils/format'

export default function TodayPlan({ today = todayIso() }: { today?: string }) {
  const [plans, setPlans] = useState<CurrentPlans | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCurrentPlans()
      .then((data) => {
        if (!cancelled) setPlans(data)
      })
      .catch(() => {
        // Not essential: without an answer, the line stays hidden.
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!plans) return null
  const plan = plans.this_week
  if (!plan) {
    return (
      <Link to="/coach" className="card card-link">
        <span className="hint">Aujourd’hui dans ton plan</span>
        <span>Pas de plan accepté : demande-le au coach</span>
      </Link>
    )
  }
  const sessions = plan.sessions.filter((session) => session.day === today)
  const text =
    sessions.length === 0
      ? 'Rien de prévu'
      : sessions
          .map((s) =>
            [s.title, s.duration_min > 0 ? `${s.duration_min} min` : '', s.intensity]
              .filter(Boolean)
              .join(' · '),
          )
          .join(' + ')
  return (
    <Link to="/plan" className="card card-link">
      <span className="hint">Aujourd’hui dans ton plan</span>
      <strong>{text}</strong>
    </Link>
  )
}
