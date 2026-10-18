// Training load per week: one bar per ISO week, the current week last.
// Loaded on demand (React.lazy in HealthPage), like the other charts.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { WeekLoad } from '../api/client'
import { formatShortDate } from '../utils/format'

export default function LoadChart({ weeks }: { weeks: WeekLoad[] }) {
  const rows = weeks.map((week) => ({ label: formatShortDate(week.monday), load: week.load }))
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={12} />
          <YAxis stroke="var(--text-muted)" fontSize={12} />
          <Tooltip
            formatter={(value) => [String(value), 'Charge']}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            cursor={{ fill: 'var(--border)', opacity: 0.4 }}
          />
          <Bar
            dataKey="load"
            name="Charge"
            fill="var(--series-1)"
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
