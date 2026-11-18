// The activity table shared by the home page (week sessions) and the map page
// (activities in view): one activity per line, with the columns FRANKS chose:
// flag, town, date, name, sport (pictogram + label), distance, duration, then the
// average and max heart rate (empty when the watch recorded none).
// `extra` adds columns at the end (e.g. the category picker of the home page).
import type { ReactNode } from 'react'
import { Picto } from '@quen9669/lignes/ui'
import { Link } from 'react-router-dom'

import type { ActivityRow } from '../api/client'
import {
  countryName,
  flagEmoji,
  formatKm,
  shownDistance,
  SPORT_PICTOS,
  SPORT_LABELS,
} from '../utils/activity'
import { formatDuration, formatHeartRate, formatTableDate } from '../utils/format'

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
            <th className="num">
              <abbr title="Fréquence cardiaque moyenne (bpm)">FC moy.</abbr>
            </th>
            <th className="num">
              <abbr title="Fréquence cardiaque maximale (bpm)">FC max</abbr>
            </th>
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
              <td className="num">{formatHeartRate(row.average_heartrate)}</td>
              <td className="num">{formatHeartRate(row.max_heartrate)}</td>
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
  return (
    <span className="sport-tag">
      <Picto nom={SPORT_PICTOS[row.sport]} taille={16} />
      {SPORT_LABELS[row.sport]}
    </span>
  )
}
