// Altitude, pace (or speed) and heart rate along an activity. The three charts
// share their cursor (Recharts `syncId`): moving on one moves the others, and
// `onActive` tells the page which sample is under the finger, for the map dot.
// Loaded on demand (React.lazy in ActivityPage).
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SportGroup } from '../api/client'
import { formatPace, type SeriesRow } from '../utils/activity'
import { formatNumber } from '../utils/format'

interface Props {
  rows: SeriesRow[]
  sport: SportGroup
  byDistance: boolean // x axis in km (true) or in minutes (false)
  onActive: (index: number | null) => void
}

type Metric = 'altitude' | 'speed' | 'heartrate'

export default function DetailCharts({ rows, sport, byDistance, onActive }: Props) {
  const has = (metric: Metric) => rows.some((row) => row[metric] !== null)
  const xLabel = (x: number) => (byDistance ? `${formatNumber(x)} km` : `${Math.round(x)} min`)
  const common = { rows, xLabel, onActive }
  return (
    <>
      {has('altitude') && (
        <ChartBlock title="Profil d’altitude" {...common}>
          {(props) => (
            <AreaChart {...props}>
              <Axes xLabel={xLabel} yLabel={(v) => `${Math.round(v)} m`} />
              <Tooltip
                labelFormatter={(x) => xLabel(Number(x))}
                formatter={(v) => [`${Math.round(Number(v))} m`, 'Altitude']}
                contentStyle={TOOLTIP_STYLE}
              />
              <Area
                dataKey="altitude"
                stroke="var(--series-3)"
                fill="var(--series-3)"
                fillOpacity={0.25}
                connectNulls
                isAnimationActive={false}
              />
            </AreaChart>
          )}
        </ChartBlock>
      )}
      {has('speed') && (
        <ChartBlock title={sport === 'run' ? 'Allure' : 'Vitesse'} {...common}>
          {(props) => (
            <LineChart {...props}>
              <Axes
                xLabel={xLabel}
                yLabel={(v) =>
                  sport === 'run' ? formatPace(v).replace(' /km', '') : `${Math.round(v)}`
                }
                // Pace: a smaller number is faster, so it is drawn higher.
                reversed={sport === 'run'}
              />
              <Tooltip
                labelFormatter={(x) => xLabel(Number(x))}
                formatter={(v) => [
                  sport === 'run' ? formatPace(Number(v)) : `${formatNumber(Number(v))} km/h`,
                  sport === 'run' ? 'Allure' : 'Vitesse',
                ]}
                contentStyle={TOOLTIP_STYLE}
              />
              <Line
                dataKey="speed"
                stroke="var(--series-1)"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            </LineChart>
          )}
        </ChartBlock>
      )}
      {has('heartrate') && (
        <ChartBlock title="Fréquence cardiaque" {...common}>
          {(props) => (
            <LineChart {...props}>
              <Axes xLabel={xLabel} yLabel={(v) => `${Math.round(v)}`} />
              <Tooltip
                labelFormatter={(x) => xLabel(Number(x))}
                formatter={(v) => [`${Math.round(Number(v))} bpm`, 'FC']}
                contentStyle={TOOLTIP_STYLE}
              />
              <Line
                dataKey="heartrate"
                stroke="var(--series-2)"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            </LineChart>
          )}
        </ChartBlock>
      )}
    </>
  )
}

const TOOLTIP_STYLE = { background: 'var(--surface)', border: '1px solid var(--border)' }

interface ChartProps {
  data: SeriesRow[]
  syncId: string
  margin: { top: number; right: number; bottom: number; left: number }
  onMouseMove: (state: { activeTooltipIndex?: number | string | null }) => void
  onMouseLeave: () => void
}

function ChartBlock({
  title,
  rows,
  onActive,
  children,
}: {
  title: string
  rows: SeriesRow[]
  xLabel: (x: number) => string
  onActive: (index: number | null) => void
  children: (props: ChartProps) => React.ReactElement
}) {
  const props: ChartProps = {
    data: rows,
    syncId: 'activity', // same id on every chart: one shared cursor
    margin: { top: 8, right: 8, bottom: 0, left: -16 },
    onMouseMove: (state) => {
      const index = Number(state.activeTooltipIndex)
      onActive(Number.isInteger(index) ? index : null)
    },
    onMouseLeave: () => onActive(null),
  }
  return (
    <div className="chart">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={160}>
        {children(props)}
      </ResponsiveContainer>
    </div>
  )
}

function Axes({
  xLabel,
  yLabel,
  reversed = false,
}: {
  xLabel: (x: number) => string
  yLabel: (y: number) => string
  reversed?: boolean
}) {
  return (
    <>
      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
      <XAxis
        dataKey="x"
        type="number"
        domain={['dataMin', 'dataMax']}
        tickFormatter={xLabel}
        stroke="var(--text-muted)"
        fontSize={12}
      />
      <YAxis
        domain={['auto', 'auto']}
        reversed={reversed}
        tickFormatter={yLabel}
        stroke="var(--text-muted)"
        fontSize={12}
      />
    </>
  )
}
