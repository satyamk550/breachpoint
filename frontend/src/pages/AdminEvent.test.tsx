import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ToastProvider } from '../components/ui'
import { AuthProvider } from '../hooks'
import { AdminRoute } from '../components/auth/RouteGuards'
import { server, eventStatusUrl } from '../test/server'
import { AdminEventPage } from './AdminEventPage'

const meUrl = 'http://localhost:3000/api/v1/auth/me'
const auditUrl = 'http://localhost:3000/api/v1/event/admin/audit'
const actionUrl = (action: string) => `http://localhost:3000/api/v1/event/admin/${action}`
const timesUrl = 'http://localhost:3000/api/v1/event/admin/times'

const admin = { id: 'admin-1', username: 'operator', email: 'operator@example.com', role: 'admin', created_at: '2026-01-01T00:00:00Z', last_login_at: null }
const player = { ...admin, id: 'player-1', username: 'runner', role: 'player' }

function client() { return new QueryClient({ defaultOptions: { queries: { gcTime: 0, retry: false } } }) }

function renderRoute() {
  return render(<QueryClientProvider client={client()}><ToastProvider><AuthProvider><MemoryRouter initialEntries={['/admin/event']}><Routes><Route element={<AdminRoute />}><Route path="admin/event" element={<AdminEventPage />} /></Route><Route path="*" element={<div>Other page</div>} /></Routes></MemoryRouter></AuthProvider></ToastProvider></QueryClientProvider>)
}

const upcoming = {
  state: 'draft_upcoming', capabilities: { can_view_challenges: false, can_submit: false, can_unlock_hints: false, can_change_roster: true, can_view_scoreboard: false }, server_time: '2026-01-01T11:00:00Z', start: '2026-01-01T12:00:00Z', end: '2026-01-01T14:00:00Z', freeze_enabled: false, freeze_time: null,
}

function setupPage(user = admin, status = upcoming) {
  server.use(
    http.get(meUrl, () => HttpResponse.json(user)),
    http.get(auditUrl, () => HttpResponse.json([])),
    http.get(eventStatusUrl, () => HttpResponse.json(status)),
  )
}

describe('admin event controls', () => {
  it('shows the admin page and header link for an admin', async () => {
    setupPage()
    renderRoute()
    expect(await screen.findByRole('heading', { name: 'Control room' })).toBeVisible()
  })

  it('shows a 403 page to players', async () => {
    setupPage(player)
    renderRoute()
    expect(await screen.findByRole('heading', { name: 'Admin access required.' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Control room' })).not.toBeInTheDocument()
  })

  it.each([
    ['Start now', 'start', 'Start the event now?', 'draft_upcoming'],
    ['Pause', 'pause', 'Pause the event?', 'live'],
    ['Resume', 'resume', 'Resume the event?', 'paused'],
    ['End', 'end', 'End the event?', 'live'],
  ])('confirms the %s flow', async (label, action, title, state) => {
    setupPage(admin, { ...upcoming, state })
    server.use(http.post(actionUrl(action), () => HttpResponse.json({ ...upcoming, state: action === 'pause' ? 'paused' : action === 'end' ? 'ended' : 'live' })))
    const user = userEvent.setup()
    renderRoute()
    const button = await screen.findByRole('button', { name: label })
    expect(button).toBeEnabled()
    await user.click(button)
    expect(await screen.findByRole('heading', { name: title })).toBeVisible()
    await user.click(screen.getByRole('button', { name: `Confirm ${label}` }))
    await waitFor(() => expect(screen.queryByRole('heading', { name: title })).not.toBeInTheDocument())
  })

  it('shows the end-before-start validation error without sending a request', async () => {
    setupPage()
    let saveCount = 0
    server.use(http.put(timesUrl, () => { saveCount += 1; return HttpResponse.json(upcoming) }))
    const user = userEvent.setup()
    renderRoute()
    const start = await screen.findByLabelText('Start time')
    const end = screen.getByLabelText('End time')
    await user.clear(start); await user.type(start, '2026-01-01T15:00')
    await user.clear(end); await user.type(end, '2026-01-01T14:00')
    await user.click(screen.getByRole('button', { name: 'Save schedule' }))
    expect(await screen.findByText('Event end must be after event start.')).toBeVisible()
    expect(saveCount).toBe(0)
  })

  it.each([
    ['draft_upcoming', ['Pause', 'Resume', 'End']],
    ['live', ['Start now', 'Resume']],
    ['paused', ['Start now', 'Pause']],
    ['ended', ['Start now', 'Pause', 'Resume', 'End']],
  ])('disables actions that do not apply in %s', async (state, disabledLabels) => {
    setupPage(admin, { ...upcoming, state })
    renderRoute()
    await screen.findByRole('heading', { name: 'Control room' })
    for (const label of disabledLabels) expect(screen.getByRole('button', { name: label })).toBeDisabled()
  })

  it('shows reset only for paused or ended and confirms the reset flow', async () => {
    setupPage(admin, { ...upcoming, state: 'paused' })
    server.use(http.post('http://localhost:3000/api/v1/event/admin/reset', () => HttpResponse.json(upcoming)))
    const user = userEvent.setup()
    const rendered = renderRoute()
    await user.click(await screen.findByRole('button', { name: 'Reset to upcoming' }))
    expect(await screen.findByRole('heading', { name: 'Reset the event to upcoming?' })).toBeVisible()
    expect(screen.getByText(/Teams, users, and other data will not be deleted/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Confirm Reset to upcoming' }))
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Reset the event to upcoming?' })).not.toBeInTheDocument())

    rendered.unmount()
    setupPage(admin, { ...upcoming, state: 'ended' })
    renderRoute()
    expect(await screen.findByRole('button', { name: 'Reset to upcoming' })).toBeEnabled()
  })

  it.each(['draft_upcoming', 'live'])('does not show reset in %s', async (state) => {
    setupPage(admin, { ...upcoming, state })
    renderRoute()
    await screen.findByRole('heading', { name: 'Control room' })
    expect(screen.queryByRole('button', { name: 'Reset to upcoming' })).not.toBeInTheDocument()
  })
})
