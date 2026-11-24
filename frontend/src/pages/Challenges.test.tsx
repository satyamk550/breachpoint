import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ToastProvider } from '../components/ui'
import { eventStatusUrl, server, teamMeUrl } from '../test/server'
import { ChallengesPage } from './ChallengesPage'
import { MarkdownPreview } from '../components/MarkdownPreview'

const challengesUrl = 'http://localhost:3000/api/v1/challenges'
const playerTeam = { id: 'team-1', name: 'Blue', member_count: 1, captain_id: 'player-1', is_banned: false, is_hidden: false, created_at: '2026-01-01T00:00:00Z', members: [] }
const live = { state: 'live', capabilities: { can_view_challenges: true, can_submit: true, can_unlock_hints: true, can_change_roster: false, can_view_scoreboard: true }, server_time: '2026-01-01T11:00:00Z', start: null, end: null, freeze_enabled: false, freeze_time: null }
const challenge = { id: 'c-1', title: 'Warmup', description_md: 'Read **this**', category_id: 'cat-1', points: 100, connection_info: 'nc example 1', tags: ['web'], solve_count: 4, solved_by_my_team: false }
function client() { return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }) }
function renderPage() { return render(<QueryClientProvider client={client()}><ToastProvider><MemoryRouter initialEntries={['/challenges']}><Routes><Route path="/challenges" element={<ChallengesPage />} /><Route path="/team/onboarding" element={<h1>Create or join a team</h1>} /></Routes></MemoryRouter></ToastProvider></QueryClientProvider>) }
function setup(status = live, team: typeof playerTeam | null = playerTeam, data = [{ category_id: 'cat-1', category_name: 'Web', sort_order: 1, challenges: [challenge] }]) { server.use(http.get(teamMeUrl, () => HttpResponse.json(team)), http.get(eventStatusUrl, () => HttpResponse.json(status)), http.get(challengesUrl, () => HttpResponse.json(data))) }

describe('player challenge board', () => {
  it('groups returned challenges by category and shows solve metadata', async () => { setup(); renderPage(); expect(await screen.findByRole('heading', { name: 'Web' })).toBeVisible(); expect(screen.getByText('Warmup')).toBeVisible(); expect(screen.getByText('4 solves')).toBeVisible() })
  it('redirects a player without a team to create or join', async () => { setup(live, null); renderPage(); expect(await screen.findByRole('heading', { name: 'Create or join a team' })).toBeVisible() })
  it.each([['draft_upcoming', 'The event has not started'], ['paused', 'The event is paused'], ['ended', 'The event has ended']])('shows the %s capability message', async (state, message) => { setup({ ...live, state, capabilities: { ...live.capabilities, can_view_challenges: false } }); renderPage(); expect(await screen.findByText(message)).toBeVisible() })
  it('shows the empty state when no eligible challenges are returned', async () => { setup(live, playerTeam, []); renderPage(); expect(await screen.findByText('No challenges yet')).toBeVisible() })
  it('opens a detail drawer and handles a player 404', async () => { setup(); server.use(http.get(`${challengesUrl}/c-1`, () => new HttpResponse(null, { status: 404 }))); renderPage(); await screen.findByRole('button', { name: /Warmup/ }); screen.getByRole('button', { name: /Warmup/ }).click(); expect(await screen.findByRole('heading', { name: 'Challenge not available' })).toBeVisible() })
  it('sanitizes script tags in Markdown previews', () => { const { container } = render(<MarkdownPreview markdown={'Hello<script>alert("x")</script>'} />); expect(container.querySelector('script')).not.toBeInTheDocument(); expect(container).toHaveTextContent('Hello') })
})
