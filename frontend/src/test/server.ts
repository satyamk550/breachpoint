import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

export const healthUrl = 'http://localhost:3000/api/v1/health'

export const server = setupServer(
  http.get(healthUrl, () => HttpResponse.json({
    status: 'ok',
    database: { status: 'ok', detail: null },
    redis: { status: 'ok', detail: null },
    version: '1.0.0',
  })),
)
