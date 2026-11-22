const API_BASE_URL = '/api/v1'
const DEFAULT_TIMEOUT_MS = 10_000

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly retryAfter?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type ApiRequestOptions = Omit<RequestInit, 'body' | 'credentials' | 'signal'> & {
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
  allowErrorStatuses?: readonly number[]
  redirectOnUnauthorized?: boolean
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload !== 'object' || payload === null) return fallback
  const candidate = payload as Record<string, unknown>
  if (typeof candidate.detail === 'string') return candidate.detail
  if (typeof candidate.message === 'string') return candidate.message
  return fallback
}

function getCookie(name: string): string | undefined {
  const prefix = `${name}=`
  const cookie = document.cookie.split('; ').find((value) => value.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : undefined
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    allowErrorStatuses = [],
    body,
    signal,
    timeoutMs,
    redirectOnUnauthorized = true,
    ...requestOptions
  } = options
  const controller = new AbortController()
  const timeoutId = window.setTimeout(
    () => controller.abort(new DOMException('Request timed out', 'TimeoutError')),
    timeoutMs ?? DEFAULT_TIMEOUT_MS,
  )
  const abortFromCaller = () => controller.abort(signal?.reason)
  signal?.addEventListener('abort', abortFromCaller, { once: true })

  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes((requestOptions.method ?? 'GET').toUpperCase())) {
    const csrfToken = getCookie('csrf_token')
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  }

  // Future CSRF hook: add the cookie-backed CSRF header here when cookie auth is introduced.
  try {
    const url = new URL(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, window.location.origin)
    const response = await fetch(url, {
      ...requestOptions,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'include',
      signal: controller.signal,
    })

    const responseText = response.status === 204 ? '' : await response.text()
    let payload: unknown
    if (responseText) {
      try {
        payload = JSON.parse(responseText) as unknown
      } catch {
        payload = undefined
      }
    }

    if (!response.ok && !allowErrorStatuses.includes(response.status)) {
      const retryAfter = response.status === 429
        ? Number(response.headers.get('Retry-After') ?? 0) || undefined
        : undefined
      const message = retryAfter
        ? `Too many requests. Try again in ${retryAfter} seconds.`
        : getErrorMessage(payload, response.statusText || 'Request failed')

      if (response.status === 429) {
        window.dispatchEvent(new CustomEvent('api:rate-limit', {
          detail: { retryAfter, message },
        }))
      }
      if (response.status === 401 && redirectOnUnauthorized) {
        const currentPath = `${window.location.pathname}${window.location.search}`
        if (!currentPath.startsWith('/login')) {
          const returnTo = encodeURIComponent(currentPath || '/')
          window.history.pushState({}, '', `/login?returnTo=${returnTo}`)
          window.dispatchEvent(new PopStateEvent('popstate'))
        }
      }
      throw new ApiError(response.status, message, retryAfter)
    }
    if (responseText && payload === undefined) {
      throw new ApiError(response.status, 'The API returned invalid JSON')
    }

    return payload as T
  } finally {
    window.clearTimeout(timeoutId)
    signal?.removeEventListener('abort', abortFromCaller)
  }
}

export function apiGet<T>(
  path: string,
  options: Pick<ApiRequestOptions, 'signal' | 'timeoutMs' | 'allowErrorStatuses' | 'redirectOnUnauthorized'> = {},
): Promise<T> {
  return apiRequest<T>(path, { ...options, method: 'GET' })
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  options: Pick<ApiRequestOptions, 'signal' | 'timeoutMs' | 'allowErrorStatuses' | 'redirectOnUnauthorized'> = {},
): Promise<T> {
  return apiRequest<T>(path, { ...options, method: 'POST', body })
}
