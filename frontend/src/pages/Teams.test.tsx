import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { ReactNode } from 'react'
import { TeamOnboardingPage } from './TeamOnboardingPage'
import { TeamsPage } from './TeamsPage'
import { server } from '../test/server'
import { ToastProvider } from '../components/ui'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'

const base = 'http://localhost:3000/api/v1'
const team = { id: 'team-1', name: 'Byte Wardens', member_count: 2, captain_id: 'u1', is_banned: false, is_hidden: false, created_at: '2026-01-01T00:00:00Z', members: [] }
function renderPage(page: ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ToastProvider><TooltipPrimitive.Provider><MemoryRouter>{page}</MemoryRouter></TooltipPrimitive.Provider></ToastProvider></QueryClientProvider>) }

describe('team frontend flows', () => {
  it('shows a newly created secret once with a copy affordance', async () => {
    server.use(http.get(`${base}/teams/me`, () => HttpResponse.json(null)), http.post(`${base}/teams`, () => HttpResponse.json({ team, join_secret: 'once-secret' }, { status: 201 })))
    const user = userEvent.setup(); renderPage(<TeamOnboardingPage />)
    await user.type(screen.getByLabelText('Team name'), 'Byte Wardens'); await user.click(screen.getByRole('button', { name: 'Create team' }))
    expect(await screen.findByText('once-secret')).toBeVisible(); expect(screen.getByText('Save this now. It will not be shown again.')).toBeVisible(); expect(screen.getByRole('button', { name: 'Copy join secret' })).toBeVisible()
  })

  it('maps wrong or unknown teams to one generic join error', async () => {
    server.use(http.get(`${base}/teams/me`, () => HttpResponse.json(null)), http.post(`${base}/teams/join`, () => HttpResponse.json({ detail: 'Invalid team name or join secret' }, { status: 401 })))
    const user = userEvent.setup(); renderPage(<TeamOnboardingPage />); await user.click(screen.getByRole('tab', { name: 'Join' })); await user.type(screen.getByLabelText('Team name'), 'Unknown'); await user.type(screen.getByLabelText('Join secret'), 'bad'); await user.click(screen.getByRole('button', { name: 'Join team' }))
    expect(await screen.findByText('The team name or join secret is incorrect.')).toBeVisible()
  })

  it('shows public names and counts and filters to an empty state', async () => {
    server.use(http.get(`${base}/teams`, () => HttpResponse.json([{ id: 'team-1', name: 'Byte Wardens', member_count: 2 }])))
    const user = userEvent.setup(); renderPage(<TeamsPage />); expect(await screen.findByText('Byte Wardens')).toBeVisible(); expect(screen.getByText('2 members')).toBeVisible(); await user.type(screen.getByRole('textbox', { name: 'Search teams' }), 'missing'); expect(await screen.findByText('No teams found')).toBeVisible()
  })

  it('reports roster lock and rate-limit messages clearly', async () => {
    server.use(http.get(`${base}/teams/me`, () => HttpResponse.json(null)), http.post(`${base}/teams`, () => new HttpResponse(null, { status: 429, headers: { 'Retry-After': '19' } })))
    const user = userEvent.setup(); renderPage(<TeamOnboardingPage />); await user.type(screen.getByLabelText('Team name'), 'Byte Wardens'); await user.click(screen.getByRole('button', { name: 'Create team' })); expect(await screen.findByText('Too many requests. Try again in 19 seconds.', { selector: '.ui-toast p' })).toBeVisible()
  })
})
