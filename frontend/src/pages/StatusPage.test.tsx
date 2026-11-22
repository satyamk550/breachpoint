import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ToastProvider } from '../components/ui'
import { healthUrl, server } from '../test/server'
import { StatusPage } from './StatusPage'

function renderStatusPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { gcTime: 0, retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <StatusPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('status page', () => {
  it('shows all three services healthy when the API reports success', async () => {
    renderStatusPage()

    expect(await screen.findByRole('heading', { name: 'All services operational' })).toBeVisible()
    expect(screen.getByText('3 / 3 healthy')).toBeVisible()
    expect(screen.getAllByRole('status', { name: 'Operational' })).toHaveLength(3)
  })

  it('shows degraded service status and derives the healthy counter from service data', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.json({
      status: 'degraded',
      database: { status: 'error', detail: 'unavailable' },
      redis: { status: 'ok', detail: null },
      version: '1.0.0',
    }, { status: 503 })))
    renderStatusPage()

    expect(await screen.findByRole('heading', { name: 'Service degradation detected' })).toBeVisible()
    expect(screen.getByText('2 / 3 healthy')).toBeVisible()
    expect(screen.getByText('Unavailable')).toBeVisible()
  })

  it('reports an unreachable backend when the health request fails', async () => {
    server.use(http.get(healthUrl, () => HttpResponse.error()))
    renderStatusPage()

    expect(await screen.findByRole('heading', { name: 'Health service unreachable' })).toBeVisible()
    expect(screen.getByText('0 / 3 healthy')).toBeVisible()
    expect(screen.getByText('No health data available')).toBeVisible()
  })

  it('disables Refresh while a manual check is in progress', async () => {
    let requestCount = 0
    let releaseResponse = () => {}
    const responseGate = new Promise<void>((resolve) => {
      releaseResponse = resolve
    })
    server.use(http.get(healthUrl, async () => {
      requestCount += 1
      if (requestCount > 1) await responseGate
      return HttpResponse.json({
        status: 'ok',
        database: { status: 'ok', detail: null },
        redis: { status: 'ok', detail: null },
        version: '1.0.0',
      })
    }))
    const user = userEvent.setup()
    renderStatusPage()

    const refresh = await screen.findByRole('button', { name: 'Refresh health status' })
    await screen.findByText('3 / 3 healthy')
    await user.click(refresh)
    await waitFor(() => expect(refresh).toBeDisabled())
    await waitFor(() => expect(requestCount).toBe(2))
    releaseResponse()
    await waitFor(() => expect(refresh).toBeEnabled())

    expect(requestCount).toBe(2)
  })

  it('has no accessibility violations in the healthy state', async () => {
    const { container } = renderStatusPage()
    await screen.findByRole('heading', { name: 'All services operational' })

    expect(await axe(container)).toHaveProperty('violations', [])
  })
})
