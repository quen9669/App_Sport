// Weight curve with its 7-day rolling average, drawn with Recharts.
// This file is loaded only when the chart is shown (see React.lazy in ProfilePage):
// Recharts is big, the home page does not need to download it.
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

import type { WeightPoint } from '../utils/weight'
import { formatNumber } from '../utils/format'

const dateLabel = (time: number) =>
  new Date(time).toLocaleDateString('fr-FR', { timeZone: 'UTC', day: 'numeric', month: 'short' })

export default function WeightChart({ points }: { points: WeightPoint[] }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          {/* type="number" + scale="time": points are spaced by real dates, gaps stay visible. */}
          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            tickFormatter={dateLabel}
            stroke="var(--text-muted)"
            fontSize={12}
          />
          {/* Start a bit below the lowest value: starting at 0 would flatten the curve. */}
          <YAxis
            domain={['dataMin - 1', 'dataMax + 1']}
            tickFormatter={(value: number) => formatNumber(value, 0)}
            stroke="var(--text-muted)"
            fontSize={12}
          />
          <Tooltip
            labelFormatter={(time) => dateLabel(Number(time))}
            formatter={(value) => `${formatNumber(Number(value))} kg`}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          />
          {/* Legend text in the normal text color: the colored square carries the identity. */}
          <Legend
            formatter={(value: string) => <span style={{ color: 'var(--text)' }}>{value}</span>}
          />
          <Line
            name="Pesée"
            dataKey="weight"
            stroke="var(--text-muted)"
            strokeWidth={1}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
          <Line
            name="Moyenne 7 jours"
            dataKey="average"
            stroke="var(--accent)"
            strokeWidth={3}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
