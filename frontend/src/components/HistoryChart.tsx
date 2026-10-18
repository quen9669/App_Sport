// Bars of the last weeks: for each goal, the percentage of its target reached.
// Loaded on demand (React.lazy in GoalsPage), like the weight chart.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { HistoryRow, HistorySeries } from '../utils/history'

// Fixed order of colors: goal 1 always gets the first color, and so on.
// Defined as CSS variables in theme.css (one step for light, one for dark).
const SERIES_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']

export default function HistoryChart({
  rows,
  series,
}: {
  rows: HistoryRow[]
  series: HistorySeries[]
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={12} />
          {/* Capped at 150 % so one exceptional week doesn't crush the others. */}
          <YAxis
            domain={[0, 150]}
            ticks={[0, 50, 100, 150]}
            allowDataOverflow
            tickFormatter={(value: number) => `${value} %`}
            stroke="var(--text-muted)"
            fontSize={12}
          />
          {/* The line to reach: 100 % of the target. */}
          <ReferenceLine y={100} stroke="var(--text-muted)" strokeDasharray="4 4" />
          <Tooltip
            formatter={(value) => `${String(value)} %`}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            cursor={{ fill: 'var(--border)', opacity: 0.4 }}
          />
          <Legend />
          {series.map((item, index) => (
            <Bar
              key={item.key}
              dataKey={item.key}
              name={item.label}
              // Slots beyond the 4th reuse a neutral color instead of inventing hues.
              fill={SERIES_COLORS[index] ?? 'var(--text-muted)'}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
