import { useEffect, useMemo, useState } from 'react'
import type { EventState, EventStatus } from '../../api/event'
import { useEventStatus } from '../../hooks/useEventStatus'
import { createServerClockSnapshot, getServerNowMs, type ServerClockSnapshot } from './eventClock'

function stateLabel(state: EventState): string {
  return state === 'draft_upcoming' ? 'Upcoming' : state[0].toUpperCase() + state.slice(1)
}

function formatRemaining(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000))
  const days = Math.floor(totalSeconds / 86_400)
  const hours = Math.floor((totalSeconds % 86_400) / 3_600)
  const minutes = Math.floor((totalSeconds % 3_600) / 60)
  const seconds = totalSeconds % 60
  const clock = [hours, minutes, seconds].map((part) => String(part).padStart(2, '0')).join(':')
  return days > 0 ? `${days}d ${clock}` : clock
}

function bannerCopy(status: EventStatus, serverNowMs: number) {
  if (!status.start) return { title: 'Event schedule not set yet', detail: 'An administrator has not published the event schedule.' }
  if (status.state === 'draft_upcoming') {
    return { title: 'Event starts in', detail: formatRemaining(Date.parse(status.start) - serverNowMs) }
  }
  if (status.state === 'live') {
    return status.end
      ? { title: 'Event ends in', detail: formatRemaining(Date.parse(status.end) - serverNowMs) }
      : { title: 'Event is live', detail: 'No end time has been set.' }
  }
  if (status.state === 'paused') return { title: 'Event paused', detail: 'Submissions are temporarily disabled.' }
  return { title: 'Event ended', detail: 'The competition is no longer accepting submissions.' }
}

function eventVariant(state: EventState): string {
  return `event-banner-${state}`
}

export function EventBanner() {
  const { data: status } = useEventStatus()
  const state = status?.state
  const serverTime = status?.server_time
  const [clockSnapshot, setClockSnapshot] = useState<ServerClockSnapshot | null>(null)
  const [serverNowMs, setServerNowMs] = useState<number | null>(null)
  const [announcedState, setAnnouncedState] = useState<EventState | null>(null)

  useEffect(() => {
    if (!serverTime) return
    const snapshot = createServerClockSnapshot(serverTime)
    setClockSnapshot(snapshot)
    setServerNowMs(getServerNowMs(snapshot))
  }, [serverTime])

  useEffect(() => {
    if (!clockSnapshot) return
    const tick = () => setServerNowMs(getServerNowMs(clockSnapshot))
    const interval = window.setInterval(tick, 1_000)
    return () => window.clearInterval(interval)
  }, [clockSnapshot])

  useEffect(() => {
    if (state && state !== announcedState) setAnnouncedState(state)
  }, [announcedState, state])

  const copy = useMemo(
    () => status && serverNowMs !== null ? bannerCopy(status, serverNowMs) : null,
    [serverNowMs, status],
  )

  if (!status || !copy) return null

  return (
    <section className={`event-banner page-container ${eventVariant(status.state)}`} role="status" aria-live="off">
      <div className="event-banner-copy">
        <span className="event-banner-kicker">{stateLabel(status.state)}</span>
        <strong>{copy.title}</strong>
        <span className="event-banner-detail">{copy.detail}</span>
      </div>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {announcedState === status.state ? `Event state changed to ${stateLabel(status.state)}.` : ''}
      </span>
    </section>
  )
}
