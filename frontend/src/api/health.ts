import { apiGet } from './client'

export type ServiceHealth = {
  status: 'ok' | 'error'
  detail: string | null
}

export type HealthResponse = {
  status: 'ok' | 'degraded'
  database: ServiceHealth
  redis: ServiceHealth
  version: string
}

function isServiceHealth(value: unknown): value is ServiceHealth {
  if (typeof value !== 'object' || value === null) return false
  const service = value as Record<string, unknown>
  return (service.status === 'ok' || service.status === 'error')
    && (service.detail === null || typeof service.detail === 'string')
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) return false
  const health = value as Record<string, unknown>
  return (health.status === 'ok' || health.status === 'degraded')
    && isServiceHealth(health.database)
    && isServiceHealth(health.redis)
    && typeof health.version === 'string'
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const payload: unknown = await apiGet<unknown>('/health', {
    signal,
    allowErrorStatuses: [503],
  })

  if (!isHealthResponse(payload)) {
    throw new Error('Health endpoint returned an invalid response')
  }
  return payload
}
