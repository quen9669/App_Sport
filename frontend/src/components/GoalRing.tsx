// A progress ring for one goal: "2 / 3" in the middle, the circle fills up.
import type { GoalProgress } from '../api/client'
import { formatNumber, GOAL_UNITS, goalTitle } from '../utils/format'

const SIZE = 96
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export default function GoalRing({ progress }: { progress: GoalProgress }) {
  const { goal, done, achieved } = progress
  const ratio = Math.min(done / goal.target, 1)
  const title = goalTitle(goal.kind, goal.sport)
  const unit = GOAL_UNITS[goal.kind] ?? ''
  const label = `${title} : ${formatNumber(done)} sur ${formatNumber(goal.target)} ${unit}`

  return (
    <figure className={`ring${achieved ? ' ring--achieved' : ''}`} aria-label={label}>
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
        <circle
          className="ring__track"
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          strokeWidth={STROKE}
        />
        {/* The dash trick: a dash as long as the done part, then a gap for the rest.
            rotate(-90) starts the ring at the top instead of the right. */}
        <circle
          className="ring__value"
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          strokeWidth={STROKE}
          strokeDasharray={`${ratio * CIRCUMFERENCE} ${CIRCUMFERENCE}`}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="ring__text">
          {formatNumber(done)}/{formatNumber(goal.target)}
        </text>
      </svg>
      <figcaption>
        {title}
        {achieved ? ' ✓' : ''}
      </figcaption>
    </figure>
  )
}
