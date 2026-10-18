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

export type Category = 'strength' | 'cardio' | 'other'
export type GoalKind = 'strength_sessions' | 'cardio_sessions' | 'active_minutes' | 'distance_km'
export type GoalSport = 'run' | 'ride'
export type GoalStatus = 'active' | 'paused' | 'done'

export interface Profile {
  height_cm: number | null
  sex: 'male' | 'female' | 'other' | null
  birth_date: string | null
  max_heartrate: number | null
  resting_heartrate: number | null
  experience_level: 'beginner' | 'intermediate' | 'advanced' | null
  injuries: string | null
  age: number | null
  updated_at: string
}

/** What the profile form sends (age and updated_at are computed by the backend). */
export type ProfileInput = Omit<Profile, 'age' | 'updated_at'>

export interface BodyMetric {
  id: number
  measured_on: string
  weight_kg: number
  body_fat_pct: number | null
  waist_cm: number | null
}

export type BodyMetricInput = Omit<BodyMetric, 'id'>

export interface Goal {
  id: number
  kind: GoalKind
  target: number
  sport: GoalSport | null
  start_date: string
  end_date: string | null
  status: GoalStatus
}

export interface GoalInput {
  kind: GoalKind
  target: number
  sport?: GoalSport | null
}

export interface GoalProgress {
  goal: Goal
  done: number
  achieved: boolean
  activity_ids: number[]
}

export interface WeekActivity {
  id: number
  name: string
  sport_type: string
  start_time: string
  moving_time_s: number | null
  elapsed_time_s: number
  distance_m: number | null
  category: Category
  automatic_category: Category
}

export interface WeekProgress {
  week: string
  previous_week: string
  next_week: string
  monday: string
  sunday: string
  goals: GoalProgress[]
  activities: WeekActivity[]
}

export interface CategoryResult {
  id: number
  category: Category
  automatic_category: Category
  overridden: boolean
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
async function request<T>(
  method: string,
  path: string,
  body?: BodyInit,
  headers?: HeadersInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, body, headers })
  if (!response.ok) {
    let message = `${method} ${path} failed with status ${response.status}`
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') message = data.detail
      // Validation errors (422) come as a list: [{ loc: [...], msg: "..." }, ...].
      if (Array.isArray(data.detail)) {
        const first = data.detail[0] as { msg?: unknown } | undefined
        if (typeof first?.msg === 'string') message = first.msg
      }
    } catch {
      // The body was not JSON: keep the generic message.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T // "No Content"
  // The caller chooses T; the backend's Pydantic models guarantee the shape.
  return (await response.json()) as T
}

/** Same as `request`, with a JSON body. */
const sendJson = <T>(method: string, path: string, data: unknown) =>
  request<T>(method, path, JSON.stringify(data), { 'Content-Type': 'application/json' })

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

// --- Profile, weight, goals (phase 2) ---

export const fetchProfile = () => request<Profile>('GET', '/api/profile')
export const saveProfile = (profile: ProfileInput) =>
  sendJson<Profile>('PUT', '/api/profile', profile)

export const fetchBodyMetrics = (days?: number) =>
  request<BodyMetric[]>('GET', `/api/body-metrics${days ? `?days=${days}` : ''}`)
export const saveBodyMetric = (metric: BodyMetricInput) =>
  sendJson<BodyMetric>('POST', '/api/body-metrics', metric)
export const deleteBodyMetric = (id: number) => request<void>('DELETE', `/api/body-metrics/${id}`)

export const fetchGoals = () => request<Goal[]>('GET', '/api/goals')
export const createGoal = (goal: GoalInput) => sendJson<Goal>('POST', '/api/goals', goal)
export const updateGoal = (id: number, changes: Partial<Pick<Goal, 'target' | 'status'>>) =>
  sendJson<Goal>('PATCH', `/api/goals/${id}`, changes)
export const deleteGoal = (id: number) => request<void>('DELETE', `/api/goals/${id}`)

export const fetchWeekProgress = (week?: string) =>
  request<WeekProgress>('GET', `/api/goals/progress${week ? `?week=${week}` : ''}`)

/** `null` removes the manual correction and goes back to the automatic category. */
export const setActivityCategory = (id: number, category: Category | null) =>
  sendJson<CategoryResult>('PATCH', `/api/activities/${id}/category`, { category })
