// One bar per ISO week (current week last), used for the training load and the
// Garmin intensity minutes. Loaded on demand (React.lazy in HealthPage).
// The weekly target of a goal, if any, is a dashed horizontal line.
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatShortDate } from '../utils/format'

export interface WeekValue {
  monday: string // ISO date of the week's Monday
  value: number
}

interface Props {
  weeks: WeekValue[]
  name: string // shown in the tooltip, e.g. "Charge"
  unit?: string // added after the value in the tooltip, e.g. "min"
  target: number | null
}

export default function WeeklyBarChart({ weeks, name, unit, target }: Props) {
  const rows = weeks.map((week) => ({ label: formatShortDate(week.monday), value: week.value }))
  const suffix = unit ? ` ${unit}` : ''
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={12} />
          {/* Without this domain, a target above every bar would be cut off. */}
          <YAxis
            stroke="var(--text-muted)"
            fontSize={12}
            domain={[0, (max: number) => Math.max(max, target ?? 0)]}
          />
          <Tooltip
            formatter={(value) => [`${String(value)}${suffix}`, name]}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            cursor={{ fill: 'var(--border)', opacity: 0.4 }}
          />
          <Bar
            dataKey="value"
            name={name}
            fill="var(--series-1)"
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          />
          {target !== null && (
            <ReferenceLine
              y={target}
              stroke="var(--accent)"
              strokeDasharray="6 4"
              strokeWidth={2}
              ifOverflow="extendDomain"
              label={{
                value: `Objectif ${target}${suffix}`,
                position: 'insideTopRight',
                fill: 'var(--text)',
                fontSize: 12,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
