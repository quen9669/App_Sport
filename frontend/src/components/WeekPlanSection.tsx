// "Mon plan" page: the weekly plans accepted on the coach screen (this week and
// the next one). They are a guide: they never change the goals. Runs show their
// steps with paces and can be sent to the Garmin watch, one by one.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type CoachPlan, type CurrentPlans, fetchCurrentPlans } from '../api/client'
import PlanCard from './PlanCard'
import RunGarminActions from './RunGarminActions'

export default function WeekPlanSection() {
  const [plans, setPlans] = useState<CurrentPlans | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCurrentPlans()
      .then((data) => {
        if (!cancelled) setPlans(data)
      })
      .catch(() => {
        // Not essential on the home page: without plans, the section stays hidden.
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!plans) return null
  // After a send, a removal or an edit, the backend answers with the new plan.
  const replace = (changed: CoachPlan) =>
    setPlans(
      (current) =>
        current && {
          ...current,
          this_week: current.this_week?.id === changed.id ? changed : current.this_week,
          next_week: current.next_week?.id === changed.id ? changed : current.next_week,
        },
    )
  const shown = [plans.this_week, plans.next_week].filter((plan) => plan !== null)
  return (
    <section className="card" aria-labelledby="plan-title">
      <h2 id="plan-title">Semaines acceptées</h2>
      {shown.length === 0 ? (
        <p className="hint">
          Pas de plan accepté. <Link to="/coach">Demande un plan au coach</Link> : il s’affichera
          ici.
        </p>
      ) : (
        shown.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            paceTargets={plans.pace_targets}
            sessionActions={(index) => (
              <RunGarminActions plan={plan} index={index} onPlanChange={replace} />
            )}
          />
        ))
      )}
    </section>
  )
}
