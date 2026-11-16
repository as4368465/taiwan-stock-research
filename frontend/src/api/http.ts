const API_BASE_URL = 'http://127.0.0.1:8000'
const ACCESS_TOKEN_KEY = 'taiwan-stock-research.access-token'

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function saveAccessToken(token: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  const body = await response.json().catch(() => ({})) as { detail?: unknown }
  if (response.status === 401) {
    clearAccessToken()
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }
  if (!response.ok) {
    const message = typeof body.detail === 'string'
      ? body.detail
      : `API 請求失敗（HTTP ${response.status}）`
    throw new ApiError(message, response.status)
  }
  return body as T
}

export function postJson<T>(path: string, payload: unknown): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', body: JSON.stringify(payload) })
}
