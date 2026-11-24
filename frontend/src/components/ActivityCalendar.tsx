// "Ma série d'activités" (Strava style): how many weeks in a row had at least one
// activity, this week day by day with a pictogram per sport, and the last 30 days
// as a table of dots (a bigger dot = a longer activity), one colour per sport.
import { Picto } from '@quen9669/lignes/ui'
import type { CSSProperties } from 'react'
import { useEffect, useState } from 'react'

import {
  fetchActivityCalendar,
  type ActivityCalendar as Calendar,
  type CalendarActivity,
} from '../api/client'
import { SPORT_LABELS, SPORT_PICTOS, sportColorVar } from '../utils/activity'
import { formatDuration } from '../utils/format'

const DAY_LETTERS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']
const DAY_NAMES = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
const DAY_MS = 86_400_000
const RECENT_DAYS = 30 // same value as the backend (RECENT_DAYS)
const SPORTS = ['run', 'walk', 'strength', 'ride', 'swim', 'other'] as const

/** "2026-11-24" -> a Date at UTC midnight (no timezone shift, days are only added). */
const parseDay = (day: string) => new Date(`${day}T00:00:00Z`)
const isoDay = (date: Date) => date.toISOString().slice(0, 10)
const colorOf = (sport: CalendarActivity['sport']): CSSProperties => ({
  ['--dot' as string]: `var(${sportColorVar(sport)})`,
})

/** Dot diameter in px: grows with the square root of the time (the eye compares areas). */
const dotSize = (seconds: number) => Math.round(10 + 22 * Math.min(1, Math.sqrt(seconds / 7200)))

const weekLabel = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'UTC',
  day: 'numeric',
  month: 'short',
})

export default function ActivityCalendar() {
  const [calendar, setCalendar] = useState<Calendar | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchActivityCalendar()
      .then((data) => {
        if (!cancelled) setCalendar(data)
      })
      .catch(() => {
        // Not essential: the card is simply not shown.
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!calendar) return null
  const byDay = new Map<string, CalendarActivity[]>()
  for (const activity of calendar.activities) {
    byDay.set(activity.day, [...(byDay.get(activity.day) ?? []), activity])
  }
  const monday = parseDay(calendar.monday)
  const firstDay = new Date(parseDay(calendar.today).getTime() - (RECENT_DAYS - 1) * DAY_MS)
  // Mondays of the weeks shown, most recent first (like the Strava journal).
  const weekStarts: Date[] = []
  for (let start = monday.getTime(); start + 7 * DAY_MS > firstDay.getTime(); start -= 7 * DAY_MS) {
    weekStarts.push(new Date(start))
  }
  const usedSports = SPORTS.filter((sport) => calendar.activities.some((a) => a.sport === sport))

  return (
    <section className="card activity-calendar" aria-labelledby="streak-title">
      <h2 id="streak-title">Ma série d’activités</h2>
      <div className="streak">
        <p className="streak-count">
          <strong>{calendar.streak_weeks}</strong>
          <span>{calendar.streak_weeks > 1 ? 'semaines d’affilée' : 'semaine d’affilée'}</span>
        </p>
        <ol className="streak-days" aria-label="Cette semaine">
          {DAY_LETTERS.map((letter, index) => {
            const date = new Date(monday.getTime() + index * DAY_MS)
            const done = byDay.get(isoDay(date)) ?? []
            const sports = SPORTS.filter((sport) => done.some((a) => a.sport === sport))
            return (
              <li
                key={index}
                aria-label={`${DAY_NAMES[index]} : ${sports.length ? sports.map((s) => SPORT_LABELS[s]).join(', ') : 'rien'}`}
              >
                <span className="hint">{letter}</span>
                <span className={sports.length ? 'streak-day streak-day--done' : 'streak-day'}>
                  {sports.length === 0 && date.getUTCDate()}
                  {sports.slice(0, 2).map((sport) => (
                    <span key={sport} style={colorOf(sport)} className="streak-picto">
                      <Picto nom={SPORT_PICTOS[sport]} taille={18} />
                    </span>
                  ))}
                </span>
              </li>
            )
          })}
        </ol>
      </div>

      <h3>30 derniers jours</h3>
      <div className="table-scroll">
        <table className="dots-table">
          <thead>
            <tr>
              <th scope="col">Semaine</th>
              {DAY_LETTERS.map((letter, index) => (
                <th key={index} scope="col" abbr={DAY_NAMES[index]}>
                  {letter}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weekStarts.map((start) => {
              const days = DAY_LETTERS.map((_, i) => new Date(start.getTime() + i * DAY_MS))
              const total = days
                .flatMap((d) => byDay.get(isoDay(d)) ?? [])
                .reduce((sum, a) => sum + a.duration_s, 0)
              const end = days[6] as Date
              return (
                <tr key={isoDay(start)}>
                  <th scope="row">
                    {weekLabel.format(start)} – {weekLabel.format(end)}
                    <span className="hint"> · {total > 0 ? formatDuration(total) : 'repos'}</span>
                  </th>
                  {days.map((day) => {
                    const inside = day >= firstDay && isoDay(day) <= calendar.today
                    return (
                      <td key={isoDay(day)}>
                        {inside &&
                          (byDay.get(isoDay(day)) ?? []).map((a) => {
                            const size = dotSize(a.duration_s)
                            const text = `${a.name} (${SPORT_LABELS[a.sport]}, ${formatDuration(a.duration_s)})`
                            return (
                              <span
                                key={a.id}
                                className="dot"
                                role="img"
                                aria-label={text}
                                title={text}
                                style={{ ...colorOf(a.sport), width: size, height: size }}
                              />
                            )
                          })}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <ul className="dots-legend" aria-label="Couleurs">
        {usedSports.map((sport) => (
          <li key={sport} style={colorOf(sport)}>
            <span className="dot" style={{ ...colorOf(sport), width: 10, height: 10 }} />
            {SPORT_LABELS[sport]}
          </li>
        ))}
        <li className="hint">Plus le point est gros, plus l’activité est longue.</li>
      </ul>
    </section>
  )
}
