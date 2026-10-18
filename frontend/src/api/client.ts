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
  activity_count: number
  activity_history_complete: boolean
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

export type Category = 'strength' | 'cardio' | 'transport' | 'other'
export type GoalKind =
  | 'strength_sessions'
  | 'cardio_sessions'
  | 'active_minutes'
  | 'distance_km'
  | 'training_load'
  | 'intensity_minutes'
  | 'steps' // steps per day, averaged over the week
  | 'floors' // floors climbed per week
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
  session_ids: number[]
}

export interface WeekActivity extends ActivityRow {
  sport_type: string
  category: Category
  automatic_category: Category
  source: string
  /** Hidden by hand: listed greyed out, never counted. */
  hidden: boolean
  /** Maybe the same session as another activity (Garmin and Strava): can be hidden. */
  possible_duplicate: boolean
}

export interface WeekProgress {
  week: string
  previous_week: string
  next_week: string
  monday: string
  sunday: string
  goals: GoalProgress[]
  activities: WeekActivity[]
  sessions: WeekSession[]
}

/** A strength session typed in the app, as listed in the week. */
export interface WeekSession {
  id: number
  performed_at: string
  duration_min: number | null
  exercises: string[]
  set_count: number
  /** false: the same session was recorded on Strava and counts through that activity. */
  counted: boolean
}

export interface HistoryGoal {
  goal_id: number
  kind: GoalKind
  sport: GoalSport | null
  target: number
  done: number
  achieved: boolean
}

export interface HistoryWeek {
  week: string
  monday: string
  goals: HistoryGoal[]
  all_achieved: boolean
}

export interface GoalHistory {
  weeks: HistoryWeek[] // oldest first
  streak: number
}

export interface Exercise {
  name: string
  group: string
  bodyweight: boolean
  last_reps: number | null
  last_weight_kg: number | null
}

export interface StrengthSetInput {
  exercise: string
  reps: number
  weight_kg: number | null
  rpe: number | null
}

export interface StrengthSet extends StrengthSetInput {
  set_number: number
}

export interface StrengthSession {
  id: number
  performed_at: string
  duration_min: number | null
  notes: string | null
  activity_id: number | null
  sets: StrengthSet[]
}

export interface StrengthSessionInput {
  performed_at: string
  duration_min: number | null
  notes: string | null
  sets: StrengthSetInput[]
}

/** One day of the Santé screen; every value may be missing. */
export interface HealthDay {
  day: string
  sleep_s: number | null
  sleep_score: number | null
  /** Minutes from midnight, negative the evening before (23:30 -> -30). */
  bedtime_min: number | null
  wake_min: number | null
  resting_hr: number | null
  hrv_ms: number | null
  /** Last known weight, carried forward until the next weigh-in. */
  weight_kg: number | null
  weight_measured_on: string | null
  steps: number | null
  floors_ascended: number | null
  floors_descended: number | null
}

export interface HealthMetrics {
  days: HealthDay[] // oldest first
  regularity: { nights: number; bedtime_sd_min: number | null; wake_sd_min: number | null }
}

export interface WeekLoad {
  week: string
  monday: string
  load: number
  sessions: number
  with_heart_rate: number
}

export interface TrainingLoad {
  weeks: WeekLoad[] // oldest first, current week last
  acute: number
  chronic: number
  acwr: number | null
  heart_rate: {
    max_hr: number | null
    resting_hr: number | null
    max_source: 'profile' | 'observed' | 'age' | null
    resting_source: 'profile' | 'garmin' | null
  }
  target: number | null // weekly target of the training load goal, if any
}

/** Garmin intensity minutes of one week (mirrors WeekIntensityOut). */
export interface WeekIntensity {
  week: string
  monday: string
  moderate: number
  vigorous: number
  total: number // moderate + 2 x vigorous, like Garmin
  days: number // days with data in the week
}

export interface IntensityMinutes {
  weeks: WeekIntensity[] // oldest first, current week last
  target: number | null // weekly target of the intensity minutes goal, if any
}

/** Garmin steps and floors of one week (mirrors WeekStepsOut). */
export interface WeekSteps {
  week: string
  monday: string
  steps_per_day: number | null // average of the days with data
  steps: number
  step_days: number
  floors_ascended: number
  floors_descended: number
  floor_days: number
}

export interface StepsAndFloors {
  weeks: WeekSteps[] // oldest first, current week last
  steps_target: number | null // steps per day of the steps goal, if any
  floors_target: number | null // floors per week of the floors goal, if any
}

// --- Map and activity detail (phase 3b) ---

export type SportGroup = 'run' | 'ride' | 'walk' | 'strength' | 'other'

/** The columns of an activity table (mirrors ActivityRowFields). */
export interface ActivityRow {
  id: number
  name: string
  sport: SportGroup
  start_time: string
  distance_m: number | null
  moving_time_s: number | null
  elapsed_time_s: number
  city: string | null
  country_code: string | null // "LU", shown as a flag
  average_heartrate: number | null // bpm, from the watch
  max_heartrate: number | null
}

/** One route on the map (mirrors MapRouteOut). */
export interface MapRoute extends ActivityRow {
  sport_type: string
  elevation_gain_m: number | null
  average_speed_mps: number | null
  polyline: string // encoded, simplified for the zoom level
}

export interface MapPlace {
  id: number
  name: string
  latitude: number
  longitude: number
  activity_count: number
  activities: ActivityRow[] // the most recent ones, newest first
}

/** An activity with a start point but no route yet: a dot on the map. */
export interface MapPoint extends ActivityRow {
  latitude: number
  longitude: number
}

export interface Bounds {
  south: number
  west: number
  north: number
  east: number
}

export interface MapRoutes {
  routes: MapRoute[]
  points: MapPoint[]
  places: MapPlace[] // activities without GPS, grouped on their place
  bounds: Bounds | null // around every matching activity
  total: number
}

export interface MapQuery {
  sport?: SportGroup
  days?: number
  min_km?: number
  max_km?: number
  bbox?: string // "west,south,east,north"
  zoom?: number
}

export type PlaceRole = 'strength_default' | 'other_default'

export interface Place {
  id: number
  name: string
  latitude: number
  longitude: number
  city: string | null
  role: PlaceRole | null
  chosen_count: number
}

export interface PlaceInput {
  name?: string
  latitude?: number
  longitude?: number
  city?: string | null
  role?: PlaceRole | null
}

/** Aligned series: index i of each list is the same moment (null = no value). */
export interface ActivitySeries {
  time_s: number[]
  distance_m: (number | null)[]
  altitude_m: (number | null)[]
  heartrate: (number | null)[]
  speed_mps: (number | null)[]
  latlng: ([number, number] | null)[]
}

export interface ActivityDetail {
  id: number
  name: string
  sport_type: string
  sport: SportGroup
  category: Category
  source: string
  start_time: string
  elapsed_time_s: number
  moving_time_s: number | null
  distance_m: number | null
  elevation_gain_m: number | null
  average_speed_mps: number | null
  max_speed_mps: number | null
  average_heartrate: number | null
  max_heartrate: number | null
  average_cadence: number | null
  hidden: boolean
  polyline: string | null
  place: { id: number; name: string; latitude: number; longitude: number; chosen: boolean } | null
  series: ActivitySeries
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

export const setActivityHidden = (id: number, hidden: boolean) =>
  sendJson<{ id: number; hidden: boolean }>('PATCH', `/api/activities/${id}/hidden`, { hidden })

export const fetchGoalHistory = (weeks = 12) =>
  request<GoalHistory>('GET', `/api/goals/history?weeks=${weeks}`)

// --- Strength sessions (phase 2b) ---

export const fetchExercises = () => request<Exercise[]>('GET', '/api/strength/exercises')
export const fetchStrengthSessions = (limit = 10) =>
  request<StrengthSession[]>('GET', `/api/strength/sessions?limit=${limit}`)
export const createStrengthSession = (session: StrengthSessionInput) =>
  sendJson<StrengthSession>('POST', '/api/strength/sessions', session)
export const deleteStrengthSession = (id: number) =>
  request<void>('DELETE', `/api/strength/sessions/${id}`)

// --- Santé screen (phase 3a) ---

export const fetchHealthMetrics = (days = 30) =>
  request<HealthMetrics>('GET', `/api/health-metrics?days=${days}`)
export const fetchTrainingLoad = (weeks = 12) =>
  request<TrainingLoad>('GET', `/api/training-load?weeks=${weeks}`)

/** Query string from the defined values only: {sport: 'run', days: undefined} -> "?sport=run". */
function queryString(params: object): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined)
  const search = new URLSearchParams(entries.map(([key, value]) => [key, String(value)]))
  return entries.length ? `?${search.toString()}` : ''
}

export const fetchMapRoutes = (query: MapQuery) =>
  request<MapRoutes>('GET', `/api/map/routes${queryString(query)}`)
export const fetchActivity = (id: number) => request<ActivityDetail>('GET', `/api/activities/${id}`)
export const setActivityPlace = (id: number, placeId: number | null) =>
  sendJson<ActivityDetail>('PATCH', `/api/activities/${id}/place`, { place_id: placeId })
export const fetchPlaces = () => request<Place[]>('GET', '/api/places')
export const createPlace = (place: PlaceInput) => sendJson<Place>('POST', '/api/places', place)
export const updatePlace = (id: number, place: PlaceInput) =>
  sendJson<Place>('PATCH', `/api/places/${id}`, place)
export const deletePlace = (id: number) => request<void>('DELETE', `/api/places/${id}`)

export const fetchIntensityMinutes = (weeks = 12) =>
  request<IntensityMinutes>('GET', `/api/intensity-minutes?weeks=${weeks}`)
export const fetchStepsAndFloors = (weeks = 12) =>
  request<StepsAndFloors>('GET', `/api/steps-floors?weeks=${weeks}`)

// --- Smoke-free tracking ---

/** A day with at least one cigarette (every other day since the quit date is smoke-free). */
export interface CigaretteDay {
  day: string // "2026-10-18", local date
  cigarettes: number
  note: string | null
}

export interface SmokingMonth {
  month: string // "2026-09"
  days: number // days of the month since the quit date, up to today
  smoke_free_days: number
  cigarettes: number
}

export interface Smoking {
  quit_date: string
  quit_date_is_default: boolean
  today: string
  days_since_quit: number
  smoke_free_days: number
  cigarette_days: number
  cigarettes: number
  current_streak: number
  longest_streak: number
  months: SmokingMonth[]
  entries: CigaretteDay[] // newest first
}

export const fetchSmoking = () => request<Smoking>('GET', '/api/smoking')
/** Write (or correct) the cigarettes of one day; returns the updated counters. */
export const saveCigaretteDay = (day: string, cigarettes: number, note: string | null) =>
  sendJson<Smoking>('PUT', `/api/smoking/days/${day}`, { cigarettes, note })
export const deleteCigaretteDay = (day: string) =>
  request<Smoking>('DELETE', `/api/smoking/days/${day}`)
export const saveQuitDate = (quitDate: string) =>
  sendJson<Smoking>('PUT', '/api/smoking/quit-date', { quit_date: quitDate })

// --- Race predictor ---

/** One run used (or considered) by the form estimate. */
export interface RaceEffort {
  activity_id: number
  name: string
  day: string // local date
  distance_m: number
  time_s: number
  vdot: number
  method: 'race' | 'heart_rate'
  segment: boolean // the best 5/10 km inside a longer run
  average_heartrate: number | null // of the whole run
  max_heartrate: number | null
  weight: number // 1 today, 0.5 after 45 days
  used: boolean // part of the estimate
}

export interface ExcludedRun {
  activity_id: number
  name: string
  day: string
  distance_m: number
}

export interface RaceForm {
  status: 'ok' | 'insufficient'
  vdot: number | null
  low: number | null
  high: number | null
  reason: string | null // French, shown as is
  efforts: RaceEffort[]
  excluded: ExcludedRun[]
}

export interface RacePrediction {
  label: string
  distance_m: number
  time_s: number
  fastest_s: number
  slowest_s: number
  riegel_s: number
}

export type PaceZoneKey = 'easy' | 'marathon' | 'threshold' | 'interval' | 'repetition'

export interface PaceZone {
  key: PaceZoneKey
  slow_s_per_km: number
  fast_s_per_km: number
}

export interface RaceSplit {
  km: number
  pace_s_per_km: number
  elapsed_s: number
}

export type Feasibility = 'realistic' | 'ambitious' | 'unlikely'

export interface RaceTarget {
  name: string
  distance_m: number
  race_date: string
  target_time_s: number | null
  elevation_gain_m: number
  days_left: number
  predicted_s: number | null
  required_vdot: number | null
  pace_plan: {
    target_time_s: number
    average_pace_s_per_km: number
    hill_allowance_s: number
    splits: RaceSplit[]
  } | null
  feasibility: { verdict: Feasibility; gap_s: number; gap_pct: number } | null
}

export interface Race {
  form: RaceForm
  predictions: RacePrediction[]
  zones: PaceZone[]
  target: RaceTarget | null
}

export interface RaceTargetInput {
  name: string
  distance_m: number
  race_date: string
  target_time_s: number | null
  elevation_gain_m: number
}

export const fetchRace = () => request<Race>('GET', '/api/race')
/** Every change answers with the whole screen (the predictions may change). */
export const saveRaceTarget = (target: RaceTargetInput) =>
  sendJson<Race>('PUT', '/api/race/target', target)
export const deleteRaceTarget = () => request<Race>('DELETE', '/api/race/target')
export const setRunExcluded = (activityId: number, excluded: boolean) =>
  sendJson<Race>('PATCH', `/api/race/efforts/${activityId}`, { excluded })

// --- AI coaches ---

export type CoachName = 'training' | 'longevity'

export interface CoachStatus {
  configured: boolean // an API key is set in .env
  model: string
  budget: {
    month: string
    spent_eur: number
    limit_eur: number
    warning: boolean // 80 % of the budget reached
    exhausted: boolean
  }
}

export interface CoachConversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export type PlanSessionKind =
  'run' | 'ride' | 'strength' | 'class' | 'walk' | 'mobility' | 'rest' | 'other'

/** One session of a weekly plan (mirrors PlanSessionOut). */
export interface PlanSession {
  day: string // ISO date
  kind: PlanSessionKind
  title: string
  duration_min: number
  intensity: string
  details: string
  why: string
}

/** A week proposed by the coach (mirrors PlanOut). */
export interface CoachPlan {
  id: number
  coach: CoachName
  week_start: string // Monday
  summary: string
  sessions: PlanSession[]
  status: 'proposed' | 'accepted' | 'rejected' | 'replaced'
}

export interface CurrentPlans {
  this_week: CoachPlan | null
  next_week: CoachPlan | null
}

export interface CoachShownMessage {
  role: 'user' | 'assistant'
  text: string
  tools: string[] // French labels of the tools used, e.g. "lit ton sommeil"
  plans: CoachPlan[] // weekly plans proposed in this answer
}

export interface CoachConversationDetail extends CoachConversation {
  messages: CoachShownMessage[]
}

export interface CoachMemory {
  id: number
  text: string
  status: 'proposed' | 'accepted'
}

/** One event of a streamed answer (mirrors app/api/coach.py `_sse`). */
export type CoachEvent =
  | { type: 'text'; text: string }
  | { type: 'tool'; name: string; label: string }
  | ({ type: 'plan' } & CoachPlan)
  | { type: 'done'; cost_eur: number; month_spent_eur: number; month_limit_eur: number }
  | { type: 'error'; message: string }

export const fetchCoachStatus = () => request<CoachStatus>('GET', '/api/coach/status')
export const fetchConversations = (coach: CoachName) =>
  request<CoachConversation[]>('GET', `/api/coach/${coach}/conversations`)
export const createConversation = (coach: CoachName) =>
  request<CoachConversationDetail>('POST', `/api/coach/${coach}/conversations`)
export const fetchConversation = (id: number) =>
  request<CoachConversationDetail>('GET', `/api/coach/conversations/${id}`)
export const deleteConversation = (id: number) =>
  request<void>('DELETE', `/api/coach/conversations/${id}`)
export const fetchMemories = (coach: CoachName) =>
  request<CoachMemory[]>('GET', `/api/coach/${coach}/memories`)
export const addMemory = (coach: CoachName, text: string) =>
  sendJson<CoachMemory>('POST', `/api/coach/${coach}/memories`, { text })
export const updateMemory = (id: number, change: { text?: string; accepted?: boolean }) =>
  sendJson<CoachMemory>('PATCH', `/api/coach/memories/${id}`, change)
export const deleteMemory = (id: number) => request<void>('DELETE', `/api/coach/memories/${id}`)
export const fetchCurrentPlans = () => request<CurrentPlans>('GET', '/api/coach/plans/current')
export const decidePlan = (id: number, accepted: boolean) =>
  sendJson<CoachPlan>('PATCH', `/api/coach/plans/${id}`, { accepted })

/**
 * Ask the coach and receive its answer piece by piece.
 *
 * The backend answers with Server-Sent Events: blocks separated by a blank
 * line, each with an `event:` line and a JSON `data:` line. EventSource only
 * does GET requests, so the stream is read by hand with fetch.
 */
export async function askCoach(
  conversationId: number,
  text: string,
  onEvent: (event: CoachEvent) => void,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/coach/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    },
  )
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, `Le coach ne répond pas (${response.status}).`)
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += value
    // Handle every complete block; keep an unfinished one for the next chunk.
    let end = buffer.indexOf('\n\n')
    while (end !== -1) {
      const event = parseSseBlock(buffer.slice(0, end))
      if (event) onEvent(event)
      buffer = buffer.slice(end + 2)
      end = buffer.indexOf('\n\n')
    }
  }
}

function parseSseBlock(block: string): CoachEvent | null {
  let name = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) name = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!name || !data) return null
  return { type: name, ...(JSON.parse(data) as object) } as CoachEvent
}
