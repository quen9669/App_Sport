// Small typed client for the backend API.
// Every call to the backend goes through this file, so the base URL and error
// handling live in one place. The interfaces mirror the backend's Pydantic models.

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Shape of the JSON returned by `GET /api/health` (mirrors the backend's HealthResponse). */
export interface HealthResponse {
  status: 'ok'
  version: string
}

export interface StravaStatus {
  configured: boolean
  connected: boolean
  athlete_id: string | null
  scope: string | null
  activity_count: number
  history_complete: boolean
}

export interface GarminStatus {
  configured: boolean
  night_count: number
  day_count: number
  latest_day: string | null
}

export type SyncStatus = 'running' | 'success' | 'partial' | 'failed'

export interface SyncLog {
  id: number
  source: string
  kind: string
  status: SyncStatus
  started_at: string
  finished_at: string | null
  items_created: number
  items_updated: number
  error: string | null
}

export interface ImportResult {
  nights: number
  days: number
  created: number
  updated: number
  warnings: string[]
}

/** Error thrown when the backend answers with a non-2xx status. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Send a request and parse the JSON answer. Errors carry the backend's `detail` message. */
async function request<T>(method: string, path: string, body?: BodyInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, body })
  if (!response.ok) {
    let message = `${method} ${path} failed with status ${response.status}`
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') message = data.detail
    } catch {
      // The body was not JSON: keep the generic message.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T // "No Content"
  // The caller chooses T; the backend's Pydantic models guarantee the shape.
  return (await response.json()) as T
}

export const fetchHealth = () => request<HealthResponse>('GET', '/api/health')
export const fetchStravaStatus = () => request<StravaStatus>('GET', '/api/strava/status')
export const fetchGarminStatus = () => request<GarminStatus>('GET', '/api/garmin/status')
export const fetchSyncLogs = (limit = 15) =>
  request<SyncLog[]>('GET', `/api/sync/logs?limit=${limit}`)
export const startStravaSync = () => request<{ status: string }>('POST', '/api/sync/strava')
export const startGarminSync = () => request<{ status: string }>('POST', '/api/sync/garmin')
export const disconnectStrava = () => request<void>('DELETE', '/api/strava/connection')

export function importHealthFile(file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)
  return request<ImportResult>('POST', '/api/import/health', form)
}

/** Strava's consent page is reached through the backend, which adds the secret parts. */
export const stravaConnectUrl = `${API_BASE_URL}/api/strava/connect`
