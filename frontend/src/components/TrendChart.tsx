// One health metric per day (thin line) and its 7-day rolling average (thick line).
// With `smooth={false}` (weight), a single step line: the value stays flat
// until the next measurement.
// Loaded on demand (React.lazy in HealthPage): Recharts is only downloaded there.
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatNumber } from '../utils/format'
import type { TrendPoint } from '../utils/health'

const dateLabel = (time: number) =>
  new Date(time).toLocaleDateString('fr-FR', { timeZone: 'UTC', day: 'numeric', month: 'short' })

export default function TrendChart({
  points,
  name,
  unit,
  digits = 0,
  smooth = true,
}: {
  points: TrendPoint[]
  name: string
  unit: string
  digits?: number
  smooth?: boolean
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            tickFormatter={dateLabel}
            stroke="var(--text-muted)"
            fontSize={12}
          />
          {/* Not from 0: a resting heart rate between 45 and 55 would look flat. */}
          <YAxis
            domain={['auto', 'auto']}
            tickFormatter={(value: number) => formatNumber(value, digits)}
            stroke="var(--text-muted)"
            fontSize={12}
          />
          <Tooltip
            labelFormatter={(time) => dateLabel(Number(time))}
            formatter={(value) => `${formatNumber(Number(value), digits)} ${unit}`}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          />
          <Legend
            formatter={(value: string) => <span style={{ color: 'var(--text)' }}>{value}</span>}
          />
          {smooth ? (
            <Line
              name={name}
              dataKey="value"
              stroke="var(--text-muted)"
              strokeWidth={1}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          ) : (
            <Line
              name={name}
              dataKey="value"
              type="stepAfter"
              stroke="var(--accent)"
              strokeWidth={3}
              dot={false}
              isAnimationActive={false}
            />
          )}
          {/* connectNulls: the average line continues over a night without data. */}
          {smooth && (
            <Line
              name="Moyenne 7 jours"
              dataKey="average"
              stroke="var(--accent)"
              strokeWidth={3}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
