// Governance made visible (SPT-11, référentiel R-23): how fresh each sync is (DE),
// whether the data is complete (DG), where each calculation comes from, and the
// colour legend of the app. Built only from the shared library's components.
import { BadgeLigne, Etat, LegendeLignes, Valide } from '@quen9669/lignes/ui'
import type { ReactNode } from 'react'

import type { GarminStatus, StravaStatus, SyncLog } from '../api/client'

/** The scheduler runs every 3 h: a sync older than 6 h means one run was missed. */
const FRESH_HOURS = 6

type Etat = 'en_service' | 'degrade' | 'arrete'

/** Freshness of a source from the sync journal (newest first): state + short text. */
function freshness(logs: SyncLog[], source: string, now = Date.now()) {
  const own = logs.filter((log) => log.source === source)
  const last = own.find((log) => log.status === 'success' || log.status === 'partial')
  if (!last?.finished_at) return { etat: 'arrete' as Etat, text: 'jamais synchronisé' }
  const hours = Math.max(0, (now - new Date(last.finished_at).getTime()) / 3_600_000)
  const text =
    hours < 1
      ? 'il y a moins d’1 h'
      : hours < 48
        ? `il y a ${Math.floor(hours)} h`
        : `il y a ${Math.floor(hours / 24)} j`
  // A failed latest run is degraded even if an older one worked.
  const failed = own[0]?.status === 'failed'
  return { etat: (hours > FRESH_HOURS || failed ? 'degrade' : 'en_service') as Etat, text }
}

/** Where a number comes from: the source (DE) and the method, in one line. */
export function CalcSource({ children }: { children: ReactNode }) {
  return (
    <p className="hint governance-source">
      <BadgeLigne ligne="de">Source</BadgeLigne> {children}
    </p>
  )
}

interface Props {
  logs: SyncLog[]
  garmin: GarminStatus | null
  strava: StravaStatus | null
}

export default function Governance({ logs, garmin, strava }: Props) {
  const rows = [
    { name: 'Garmin', source: 'garmin', on: garmin?.configured },
    { name: 'Strava', source: 'strava', on: strava?.connected },
  ]
  const complete =
    (garmin?.configured ? garmin.activity_history_complete : true) &&
    (strava?.connected ? strava.history_complete : true)
  return (
    <section className="card" aria-labelledby="governance-title">
      <h2 id="governance-title">Fraîcheur et qualité des données</h2>
      <ul className="governance-list">
        {rows
          .filter((row) => row.on)
          .map((row) => {
            const { etat, text } = freshness(logs, row.source)
            return (
              <li key={row.source}>
                <BadgeLigne ligne="de">{row.name}</BadgeLigne>{' '}
                <Etat etat={etat}>Synchro {text}</Etat>
              </li>
            )
          })}
        <li>
          <BadgeLigne ligne="dg">Complétude</BadgeLigne>{' '}
          {complete ? (
            <Valide>Historique complet</Valide>
          ) : (
            <Etat etat="degrade">Historique en cours d’import</Etat>
          )}
        </li>
      </ul>
      <h3>Carte des couleurs</h3>
      <LegendeLignes
        lignes={[
          { ligne: 'de', texte: 'Synchro Garmin et Strava, fraîcheur' },
          { ligne: 'dg', texte: 'Données complètes ✓' },
          { ligne: 'ds', texte: 'Prédictions (temps de course, charge à venir)' },
          { ligne: 'ai', texte: 'Messages du coach' },
          { ligne: 'ml', texte: 'Objectifs, série, progression, longévité, traces' },
        ]}
      />
    </section>
  )
}
