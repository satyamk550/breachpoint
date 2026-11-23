import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

export const healthUrl = 'http://localhost:3000/api/v1/health'
export const eventStatusUrl = 'http://localhost:3000/api/v1/event/status'
export const teamMeUrl = 'http://localhost:3000/api/v1/teams/me'

export const upcomingEventStatus = {
  state: 'draft_upcoming',
  capabilities: {
    can_view_challenges: false,
    can_submit: false,
    can_unlock_hints: false,
    can_change_roster: true,
    can_view_scoreboard: false,
  },
  server_time: '2026-01-01T11:00:00Z',
  start: '2026-01-01T12:00:00Z',
  end: '2026-01-01T14:00:00Z',
  freeze_enabled: false,
  freeze_time: null,
}

export const server = setupServer(
  http.get(healthUrl, () => HttpResponse.json({
    status: 'ok',
    database: { status: 'ok', detail: null },
    redis: { status: 'ok', detail: null },
    version: '1.0.0',
  })),
  http.get(eventStatusUrl, () => HttpResponse.json(upcomingEventStatus)),
  http.get(teamMeUrl, () => HttpResponse.json(null)),
)
