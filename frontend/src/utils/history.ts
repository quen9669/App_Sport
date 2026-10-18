// Turn the goal history into rows for the bar chart and the table.
import type { GoalHistory } from '../api/client'
import { goalTitle } from './format'

export interface HistorySeries {
  key: string // "g12": the bar's data key for goal 12
  goalId: number
  label: string
}

export type HistoryRow = { week: string; label: string } & Record<string, number | string>

/** ISO week "2026-W42" -> "S42" ("semaine 42"), short enough for a phone axis. */
export const shortWeek = (week: string) => `S${week.slice(-2)}`

/**
 * One series per goal that appears in the history, ordered by goal id so a
 * goal keeps the same color whatever the period shown. Values are the
 * percentage of the target reached (different units can share one axis).
 */
export function historyRows(history: GoalHistory): { rows: HistoryRow[]; series: HistorySeries[] } {
  const seriesById = new Map<number, HistorySeries>()
  for (const week of history.weeks) {
    for (const goal of week.goals) {
      if (!seriesById.has(goal.goal_id)) {
        seriesById.set(goal.goal_id, {
          key: `g${goal.goal_id}`,
          goalId: goal.goal_id,
          label: goalTitle(goal.kind, goal.sport),
        })
      }
    }
  }
  const series = [...seriesById.values()].sort((a, b) => a.goalId - b.goalId)
  const rows = history.weeks.map((week) => {
    const row: HistoryRow = { week: week.week, label: shortWeek(week.week) }
    for (const goal of week.goals) {
      row[`g${goal.goal_id}`] = Math.round((goal.done / goal.target) * 100)
    }
    return row
  })
  return { rows, series }
}
