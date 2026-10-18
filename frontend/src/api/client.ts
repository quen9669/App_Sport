// Small typed client for the backend API.
// Every call to the backend goes through this file, so the base URL and error
// handling live in one place.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Shape of the JSON returned by `GET /api/health` (mirrors the backend's HealthResponse). */
export interface HealthResponse {
  status: 'ok'
  version: string
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

/** Call `GET {path}` on the backend and return the parsed JSON body. */
async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with status ${response.status}`)
  }
  // The caller chooses T; the backend's Pydantic models guarantee the shape.
  return (await response.json()) as T
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>('/api/health')
}
