// "Monitoring" (Réglages): is the app itself working? Syncs, nightly copies,
// coach budget, memory. Technical numbers only (GET /api/monitoring), never
// health data. Grafana, on the VPS, keeps watching from the outside: if the app
// is down this page is down too, so a button opens the Grafana dashboard.
import { useCallback, useEffect, useState } from 'react'

import { fetchMonitoring, type Monitoring, type MonitoringStatus } from '../api/client'
import { formatDateTime, SOURCE_LABELS } from '../utils/format'
import { formatAgo, formatBytes, MONITORING_LABELS } from '../utils/monitoring'

const OVERALL_TEXTS: Record<MonitoringStatus, string> = {
  ok: 'Tout fonctionne.',
  warning: 'Quelque chose est à surveiller.',
  error: 'Quelque chose ne fonctionne pas.',
  unknown: 'Pas encore assez de données.',
}

// Reuses the colours of the Longévité verdicts (green, amber, red).
const STATUS_CLASSES: Record<MonitoringStatus, string> = {
  ok: 'status--met',
  warning: 'status--partly',
  error: 'status--below',
  unknown: '',
}

function StatusBadge({ status }: { status: MonitoringStatus }) {
  return <span className={`badge ${STATUS_CLASSES[status]}`}>{MONITORING_LABELS[status]}</span>
}

const euros = (value: number) => `${value.toFixed(2).replace('.', ',')} €`

export default function MonitoringPage() {
  const [data, setData] = useState<Monitoring | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Only called from promises and clicks, never synchronously inside the effect.
  const load = useCallback(() => {
    fetchMonitoring()
      .then((result) => {
        setData(result)
        setError(null)
      })
      .catch(() => setError("Impossible de lire l'état de l'app."))
  }, [])

  useEffect(load, [load])

  return (
    <>
      <h1>Monitoring</h1>
      <p className="subtitle">L&apos;état technique de l&apos;app, sans aucune donnée de santé</p>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="hint">Chargement…</p>}
      {data && <MonitoringView data={data} onRefresh={load} />}
    </>
  )
}

function MonitoringView({ data, onRefresh }: { data: Monitoring; onRefresh: () => void }) {
  const now = data.checked_at
  const memory = data.memory
  return (
    <>
      <section className="card" aria-labelledby="overall-title">
        <h2 id="overall-title">
          {OVERALL_TEXTS[data.status]} <StatusBadge status={data.status} />
        </h2>
        <p className="hint">
          Vérifié le {formatDateTime(now)} · app démarrée {formatAgo(data.started_at, now)}
        </p>
        <div className="actions">
          <button type="button" className="secondary" onClick={onRefresh}>
            Actualiser
          </button>
          {data.grafana_url && (
            <a className="button" href={data.grafana_url} target="_blank" rel="noopener noreferrer">
              Ouvrir dans Grafana
            </a>
          )}
        </div>
        {data.grafana_url && (
          <p className="hint">
            Grafana surveille l&apos;app depuis l&apos;extérieur, même quand elle est arrêtée. Il
            s&apos;ouvre seulement sur tes appareils connectés à Tailscale.
          </p>
        )}
      </section>

      <section className="card" aria-labelledby="sync-title">
        <h2 id="sync-title">Synchronisations</h2>
        <ul className="longevity-grid">
          {data.sources.map((source) => (
            <li key={source.source} className="longevity-item">
              <h3>{SOURCE_LABELS[source.source] ?? source.source}</h3>
              <p>
                <StatusBadge status={source.status} />
              </p>
              <p className="tile-value">
                {source.last_success_at ? formatAgo(source.last_success_at, now) : 'Jamais'}
              </p>
              <p className="hint">
                Dernière synchro réussie
                {source.last_success_at && ` (${formatDateTime(source.last_success_at)})`}
              </p>
              <p className="hint">
                Échecs sur 7 jours : {source.failures_7d}
                {source.last_run_status === 'failed' && source.last_error && (
                  <> · dernière erreur : {source.last_error}</>
                )}
              </p>
            </li>
          ))}
        </ul>
        <p className="hint">Activités ajoutées sur 7 jours : {data.activities_7d}</p>
      </section>

      <section className="card" aria-labelledby="backup-title">
        <h2 id="backup-title">
          Sauvegarde de la nuit <StatusBadge status={data.backup.status} />
        </h2>
        <p>
          {data.backup.last_copy_at
            ? `Dernière copie : ${formatDateTime(data.backup.last_copy_at)} (${formatAgo(data.backup.last_copy_at, now)})`
            : 'Aucune copie pour le moment.'}
        </p>
        <p className="hint">
          {data.backup.copies} copie{data.backup.copies > 1 ? 's' : ''} gardée
          {data.backup.copies > 1 ? 's' : ''}
          {data.backup.last_copy_bytes !== null &&
            ` · ${formatBytes(data.backup.last_copy_bytes)} chacune`}
          . L&apos;envoi chiffré vers Google Drive est fait à part : il se suit dans Grafana.
        </p>
      </section>

      <section className="card" aria-labelledby="coach-title">
        <h2 id="coach-title">
          Coach IA <StatusBadge status={data.coach.status} />
        </h2>
        <p>
          {euros(data.coach.spent_eur)} dépensés sur {euros(data.coach.limit_eur)} ce mois-ci
        </p>
        {!data.coach.enabled && <p className="hint">Aucune clé d&apos;IA configurée.</p>}
      </section>

      <section className="card" aria-labelledby="server-title">
        <h2 id="server-title">
          Serveur <StatusBadge status={memory.status} />
        </h2>
        <p>
          Mémoire :{' '}
          {memory.used_bytes === null
            ? 'non mesurée ici (seulement dans Docker)'
            : memory.limit_bytes === null
              ? formatBytes(memory.used_bytes)
              : `${formatBytes(memory.used_bytes)} sur ${formatBytes(memory.limit_bytes)}`}
        </p>
        <p className="hint">
          Taille de la base :{' '}
          {data.database_bytes === null ? 'inconnue' : formatBytes(data.database_bytes)}
        </p>
      </section>
    </>
  )
}
