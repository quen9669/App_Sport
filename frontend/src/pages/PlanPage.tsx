// "Mon plan" (Coach folder): the weekly plans accepted on the coach screen,
// this week and the next one. Ma semaine only shows today's session.
import WeekPlanSection from '../components/WeekPlanSection'

export default function PlanPage() {
  return (
    <>
      <h1>Mon plan</h1>
      <p className="subtitle">Les semaines proposées par le coach et acceptées</p>
      <WeekPlanSection />
    </>
  )
}
