// "Sources" page: connect Strava, sync Strava and Garmin, import files, see the sync journal.
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  ApiError,
  disconnectStrava,
  fetchGarminStatus,
  fetchStravaStatus,
  fetchSyncLogs,
  importHealthFile,
  startGarminSync,
  startStravaSync,
  stravaConnectUrl,
  type GarminStatus,
  type ImportResult,
  type StravaStatus,
  type SyncLog,
} from '../api/client'
import { formatDateTime, KIND_LABELS, SOURCE_LABELS, STATUS_LABELS } from '../utils/format'

// Messages for the `?strava=...` parameter added by the backend after the Strava consent page.
const STRAVA_RESULT_MESSAGES: Record<string, string> = {
  connected: 'Strava est connecté. Lance une première synchronisation.',
  denied: 'Connexion Strava annulée.',
  missing_scope:
    'Il faut laisser cochée l’autorisation « activités privées » sur Strava. Réessaie.',
  invalid_state: 'La connexion a expiré ou n’a pas été lancée depuis l’app. Réessaie.',
  error: 'Strava a refusé la connexion. Réessaie dans un instant.',
}

const REFRESH_WHILE_RUNNING_MS = 4000

/** Text of an error to show to the user. */
function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Le backend ne répond pas.'
}

export default function SourcesPage() {
  const [searchParams] = useSearchParams()
  const [strava, setStrava] = useState<StravaStatus | null>(null)
  const [garmin, setGarmin] = useState<GarminStatus | null>(null)
  const [logs, setLogs] = useState<SyncLog[]>([])
  const [message, setMessage] = useState<string | null>(
    STRAVA_RESULT_MESSAGES[searchParams.get('strava') ?? ''] ?? null,
  )
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [file, setFile] = useState<File | null>(null)

  // Load the three pieces of data together. Returns them instead of storing
  // them, so effects can decide what to do with the answer.
  const load = useCallback(
    () => Promise.all([fetchStravaStatus(), fetchGarminStatus(), fetchSyncLogs()]),
    [],
  )

  // useCallback keeps the same function between renders, so the effects below
  // don't re-run on every render.
  const refresh = useCallback(async () => {
    try {
      const [stravaStatus, garminStatus, syncLogs] = await load()
      setStrava(stravaStatus)
      setGarmin(garminStatus)
      setLogs(syncLogs)
    } catch (error) {
      setMessage(errorText(error))
    }
  }, [load])

  // First load, when the page opens.
  useEffect(() => {
    let cancelled = false
    load()
      .then(([stravaStatus, garminStatus, syncLogs]) => {
        if (cancelled) return
        setStrava(stravaStatus)
        setGarmin(garminStatus)
        setLogs(syncLogs)
      })
      .catch((error: unknown) => {
        if (!cancelled) setMessage(errorText(error))
      })
    return () => {
      cancelled = true
    }
  }, [load])

  // While a sync is running, reload every few seconds to show its progress.
  const anyRunning = logs.some((log) => log.status === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const timer = window.setInterval(() => void refresh(), REFRESH_WHILE_RUNNING_MS)
    return () => window.clearInterval(timer)
  }, [anyRunning, refresh])

  /** Run an action, show its message (or error), then reload the page data. */
  async function run(action: () => Promise<unknown>, success: string) {
    try {
      await action()
      setMessage(success)
    } catch (error) {
      setMessage(errorText(error))
    }
    await refresh()
  }

  async function onImport(event: FormEvent) {
    event.preventDefault() // stop the browser from reloading the page
    if (!file) return
    try {
      setImportResult(await importHealthFile(file))
      setMessage(null)
    } catch (error) {
      setMessage(errorText(error))
    }
    await refresh()
  }

  return (
    <>
      <h1>Sources de données</h1>
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}

      <section className="card" aria-labelledby="strava-title">
        <h2 id="strava-title">Strava</h2>
        {strava === null ? (
          <p>Chargement…</p>
        ) : !strava.configured ? (
          <p>
            Strava n’est pas encore configuré : ajoute <code>STRAVA_CLIENT_ID</code> et{' '}
            <code>STRAVA_CLIENT_SECRET</code> dans <code>.env</code> (voir le guide
            docs/learning/01-strava-setup.md).
          </p>
        ) : !strava.connected ? (
          <a className="button" href={stravaConnectUrl}>
            Connecter Strava
          </a>
        ) : (
          <>
            <p>
              {strava.activity_count} activités importées
              {strava.history_complete ? ', historique complet.' : ', historique en cours.'}
            </p>
            <div className="actions">
              <button
                type="button"
                onClick={() => void run(startStravaSync, 'Synchronisation Strava lancée.')}
              >
                Synchroniser maintenant
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => void run(disconnectStrava, 'Strava est déconnecté.')}
              >
                Déconnecter
              </button>
            </div>
          </>
        )}
      </section>

      <section className="card" aria-labelledby="garmin-title">
        <h2 id="garmin-title">Garmin</h2>
        {garmin === null ? (
          <p>Chargement…</p>
        ) : !garmin.configured ? (
          <p>
            Garmin n’est pas configuré (<code>GARMIN_EMAIL</code> et <code>GARMIN_PASSWORD</code>{' '}
            dans <code>.env</code>). Tu peux aussi importer un fichier ci-dessous.
          </p>
        ) : (
          <>
            <p>
              {garmin.night_count} nuits et {garmin.day_count} jours importés
              {garmin.latest_day ? `, dernier jour : ${garmin.latest_day}.` : '.'}
            </p>
            <button
              type="button"
              onClick={() => void run(startGarminSync, 'Synchronisation Garmin lancée.')}
            >
              Synchroniser maintenant
            </button>
          </>
        )}
      </section>

      <section className="card" aria-labelledby="import-title">
        <h2 id="import-title">Importer un fichier</h2>
        <p className="hint">
          CSV au format du modèle (docs/templates) ou fichier <code>*_sleepData.json</code> de
          l’export Garmin.
        </p>
        <form onSubmit={(event) => void onImport(event)} className="actions">
          <input
            type="file"
            accept=".csv,.json"
            aria-label="Fichier à importer"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <button type="submit" disabled={!file}>
            Importer
          </button>
        </form>
        {importResult && (
          <p role="status">
            {importResult.nights} nuits et {importResult.days} jours lus : {importResult.created}{' '}
            ajoutés, {importResult.updated} mis à jour.
            {importResult.warnings.length > 0 &&
              ` ${importResult.warnings.length} avertissement(s) : ${importResult.warnings
                .slice(0, 3)
                .join(' ; ')}`}
          </p>
        )}
      </section>

      <section className="card" aria-labelledby="logs-title">
        <h2 id="logs-title">Historique des synchronisations</h2>
        {logs.length === 0 ? (
          <p>Aucune synchronisation pour l’instant.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Source</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Ajoutés / mis à jour</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} title={log.error ?? undefined}>
                    <td>{formatDateTime(log.started_at)}</td>
                    <td>{SOURCE_LABELS[log.source] ?? log.source}</td>
                    <td>{KIND_LABELS[log.kind] ?? log.kind}</td>
                    <td className={`log-status log-status--${log.status}`}>
                      {STATUS_LABELS[log.status] ?? log.status}
                    </td>
                    <td>
                      {log.items_created} / {log.items_updated}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
