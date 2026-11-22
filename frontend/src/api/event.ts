import { apiGet } from './client'

export type EventState = 'draft_upcoming' | 'live' | 'paused' | 'ended'

export type EventCapabilities = {
  can_view_challenges: boolean
  can_submit: boolean
  can_unlock_hints: boolean
  can_change_roster: boolean
  can_view_scoreboard: boolean
}

export type EventStatus = {
  state: EventState
  capabilities: EventCapabilities
  server_time: string
  start: string | null
  end: string | null
  freeze_enabled: boolean
  freeze_time: string | null
}

const eventStatusUrl = '/event/status'

function isIsoDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function isCapabilities(value: unknown): value is EventCapabilities {
  if (typeof value !== 'object' || value === null) return false
  const capabilities = value as Record<string, unknown>
  return Object.keys({
    can_view_challenges: true,
    can_submit: true,
    can_unlock_hints: true,
    can_change_roster: true,
    can_view_scoreboard: true,
  }).every((key) => typeof capabilities[key] === 'boolean')
}

function isEventStatus(value: unknown): value is EventStatus {
  if (typeof value !== 'object' || value === null) return false
  const status = value as Record<string, unknown>
  return (status.state === 'draft_upcoming'
    || status.state === 'live'
    || status.state === 'paused'
    || status.state === 'ended')
    && isCapabilities(status.capabilities)
    && isIsoDate(status.server_time)
    && (status.start === null || isIsoDate(status.start))
    && (status.end === null || isIsoDate(status.end))
    && typeof status.freeze_enabled === 'boolean'
    && (status.freeze_time === null || isIsoDate(status.freeze_time))
}

export async function fetchEventStatus(signal?: AbortSignal): Promise<EventStatus> {
  const payload: unknown = await apiGet<unknown>(eventStatusUrl, { signal })
  if (!isEventStatus(payload)) throw new Error('Event status endpoint returned an invalid response')
  return payload
}
