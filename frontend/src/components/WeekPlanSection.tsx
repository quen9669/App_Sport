// Accueil: the weekly plans accepted on the coach screen (this week and the
// next one). They are a guide: they never change the goals.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { type CurrentPlans, fetchCurrentPlans } from '../api/client'
import PlanCard from './PlanCard'

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
  const shown = [plans.this_week, plans.next_week].filter((plan) => plan !== null)
  return (
    <section className="card" aria-labelledby="plan-title">
      <h2 id="plan-title">Mon plan</h2>
      {shown.length === 0 ? (
        <p className="hint">
          Pas de plan accepté. <Link to="/coach">Demande un plan au coach</Link> : il s’affichera
          ici.
        </p>
      ) : (
        shown.map((plan) => <PlanCard key={plan.id} plan={plan} />)
      )}
    </section>
  )
}
