import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { EventBanner } from './EventBanner'
import { createServerClockSnapshot, getServerNowMs } from './eventClock'
import { eventStatusUrl, server, upcomingEventStatus } from '../../test/server'

function renderBanner() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { gcTime: 0, retry: false } },
  })
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <EventBanner />
      </QueryClientProvider>,
    ),
  }
}

function status(state: 'draft_upcoming' | 'live' | 'paused' | 'ended') {
  return {
    ...upcomingEventStatus,
    state,
    start: state === 'draft_upcoming' ? upcomingEventStatus.start : '2026-01-01T10:00:00Z',
    end: state === 'live' ? upcomingEventStatus.end : upcomingEventStatus.end,
  }
}

describe('event status banner', () => {
  it.each([
    ['draft_upcoming', 'Upcoming'],
    ['live', 'Live'],
    ['paused', 'Paused'],
    ['ended', 'Ended'],
  ] as const)('renders the %s state', async (state, label) => {
    server.use(http.get(eventStatusUrl, () => HttpResponse.json(status(state))))
    renderBanner()

    expect(await screen.findByText(label)).toBeVisible()
  })

  it('explains when the schedule has not been set', async () => {
    server.use(http.get(eventStatusUrl, () => HttpResponse.json({
      ...upcomingEventStatus,
      start: null,
      end: null,
    })))
    renderBanner()

    expect(await screen.findByText('Event schedule not set yet')).toBeVisible()
  })

  it('uses the server offset with monotonic elapsed time', () => {
    const serverTime = '2026-01-01T12:00:00Z'
    const browserEpoch = Date.parse('2025-12-31T10:00:00Z')
    const snapshot = createServerClockSnapshot(serverTime, browserEpoch, 100)

    expect(snapshot.offsetMs).toBe(26 * 60 * 60 * 1000)
    expect(getServerNowMs(snapshot, 1_100)).toBe(Date.parse(serverTime) + 1_000)
  })

  it('keeps the last good banner data when a refetch fails', async () => {
    let requests = 0
    server.use(http.get(eventStatusUrl, () => {
      requests += 1
      return requests === 1
        ? HttpResponse.json(upcomingEventStatus)
        : HttpResponse.error()
    }))
    const { queryClient } = renderBanner()

    expect(await screen.findByText('Event starts in')).toBeVisible()
    await queryClient.refetchQueries({ queryKey: ['event-status'] })
    await waitFor(() => expect(requests).toBe(2))
    expect(screen.getByText('Event starts in')).toBeVisible()
  })

  it('announces only the state change, not countdown ticks', async () => {
    let current = status('draft_upcoming')
    server.use(http.get(eventStatusUrl, () => HttpResponse.json(current)))
    const { queryClient } = renderBanner()

    const announcement = await screen.findByText('Event state changed to Upcoming.')
    expect(announcement).toBeInTheDocument()
    current = status('live')
    await queryClient.invalidateQueries({ queryKey: ['event-status'] })
    await waitFor(() => expect(screen.getByText('Event state changed to Live.')).toBeInTheDocument())
    expect(screen.getAllByText(/Event state changed to/)).toHaveLength(1)
  })
})
