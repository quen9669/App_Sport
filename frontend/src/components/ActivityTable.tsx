// The activity table shared by the home page (week sessions) and the map page
// (activities in view): one activity per line, with the columns FRANKS chose:
// flag, town, date, name, sport (emoji + colour), distance and duration.
// `extra` adds columns at the end (e.g. the category picker of the home page).
import type { CSSProperties, ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { ActivityRow } from '../api/client'
import {
  countryName,
  flagEmoji,
  formatKm,
  shownDistance,
  SPORT_COLOR_VARS,
  SPORT_EMOJIS,
  SPORT_LABELS,
} from '../utils/activity'
import { formatDuration, formatTableDate } from '../utils/format'

export interface ExtraColumn<T> {
  header: string
  cell: (row: T) => ReactNode
}

interface Props<T extends ActivityRow> {
  rows: T[]
  label: string // accessible name of the table
  extra?: ExtraColumn<T>[]
  rowClass?: (row: T) => string | undefined
}

export default function ActivityTable<T extends ActivityRow>({
  rows,
  label,
  extra = [],
  rowClass,
}: Props<T>) {
  return (
    <div className="table-scroll">
      <table className="activity-table" aria-label={label}>
        <thead>
          <tr>
            <th className="flag">
              <span className="visually-hidden">Pays</span>
            </th>
            <th>Ville</th>
            <th>Date</th>
            <th>Activité</th>
            <th>Sport</th>
            <th className="num">Distance</th>
            <th className="num">Durée</th>
            {extra.map((column) => (
              <th key={column.header}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={rowClass?.(row)}>
              <td className="flag" title={countryName(row.country_code)}>
                {flagEmoji(row.country_code)}
              </td>
              <td>{row.city ?? ''}</td>
              <td>{formatTableDate(row.start_time)}</td>
              <td className="name">
                <Link to={`/activites/${row.id}`} title={row.name}>
                  {row.name}
                </Link>
              </td>
              <td>
                <SportTag row={row} />
              </td>
              <td className="num">
                {shownDistance(row) === null ? '' : formatKm(shownDistance(row) ?? 0)}
              </td>
              <td className="num">{formatDuration(row.moving_time_s ?? row.elapsed_time_s)}</td>
              {extra.map((column) => (
                <td key={column.header}>{column.cell(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SportTag({ row }: { row: ActivityRow }) {
  // The tag reads its colour from a CSS variable set on the element itself.
  const style = { '--sport-color': `var(${SPORT_COLOR_VARS[row.sport]})` } as CSSProperties
  return (
    <span className="sport-tag" style={style}>
      <span aria-hidden="true">{SPORT_EMOJIS[row.sport]}</span>
      {SPORT_LABELS[row.sport]}
    </span>
  )
}
