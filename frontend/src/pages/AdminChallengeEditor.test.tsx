import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/ui'
import { server } from '../test/server'
import { AdminChallengeEditorPage } from './AdminChallengeEditorPage'

beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) Element.prototype.hasPointerCapture = () => false
  if (!Element.prototype.releasePointerCapture) Element.prototype.releasePointerCapture = () => undefined
  if (!Element.prototype.setPointerCapture) Element.prototype.setPointerCapture = () => undefined
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined
})

const categoriesUrl = 'http://localhost:3000/api/v1/admin/categories'
const challengesUrl = 'http://localhost:3000/api/v1/admin/challenges'
const category = { id: 'cat-1', name: 'Web', sort_order: 1 }
const challenge = { id: 'challenge-1', title: 'Created', description_md: 'desc', category_id: 'cat-1', points: 10, scoring_mode: 'static', initial: 0, minimum: 0, decay: 1, function: 'linear', visibility: 'draft', max_attempts: null, connection_info: null, author: null, created_at: '2026-01-01T00:00:00Z', tags: [], prerequisites: [], solve_count: 0, solved_by_my_team: false }
function renderPage() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}><ToastProvider><MemoryRouter initialEntries={['/admin/challenges/new']}><AdminChallengeEditorPage /></MemoryRouter></ToastProvider></QueryClientProvider>) }
function setup(categories: unknown[] = [category]) { server.use(http.get(categoriesUrl, () => HttpResponse.json(categories)), http.get(challengesUrl, () => HttpResponse.json([]))) }
async function chooseCategory(user: ReturnType<typeof userEvent.setup>) { await user.click((await screen.findAllByRole('combobox'))[0]); await user.click(await screen.findByRole('option', { name: 'Web' })) }

describe('admin challenge editor', () => {
  it('explains the empty category state and creates an inline category', async () => { let available: unknown[] = []; server.use(http.get(categoriesUrl, () => HttpResponse.json(available)), http.get(challengesUrl, () => HttpResponse.json([])), http.post(categoriesUrl, () => { available = [category]; return HttpResponse.json(category) })); renderPage(); expect(await screen.findByText('Create a category first.')).toBeVisible(); expect(screen.getByRole('link', { name: 'Open categories' })).toHaveAttribute('href', '/admin/categories'); const user = userEvent.setup(); await user.type(screen.getByRole('textbox', { name: 'New category name' }), 'Crypto'); await user.click(screen.getByRole('button', { name: 'New category' })); await waitFor(() => expect(screen.queryByText('Create a category first.')).not.toBeInTheDocument()) })
  it('validates a missing category before posting', async () => { setup([category]); renderPage(); const user = userEvent.setup(); await user.click(await screen.findByRole('button', { name: 'Create challenge' })); expect(await screen.findByText('Category is required.')).toBeVisible() })
  it('maps a FastAPI 422 detail to the matching field', async () => { setup([category]); server.use(http.post(challengesUrl, () => HttpResponse.json({ detail: [{ loc: ['body', 'points'], msg: 'Input should be greater than or equal to 0' }] }, { status: 422 }))); renderPage(); const user = userEvent.setup(); await chooseCategory(user); await user.click(screen.getByRole('button', { name: 'Create challenge' })); expect(await screen.findByText('Input should be greater than or equal to 0')).toBeVisible(); expect(screen.queryByText('Unprocessable Entity')).not.toBeInTheDocument() })
  it('shows static and draft as the defaults', async () => { setup([category]); renderPage(); const selects = await screen.findAllByRole('combobox'); expect(selects[1]).toHaveTextContent('Static'); expect(selects[2]).toHaveTextContent('Draft') })
  it('adds a masked draft flag and creates it after the challenge', async () => { setup([category]); const calls: string[] = []; server.use(http.post(challengesUrl, async () => { calls.push('challenge'); return HttpResponse.json(challenge) }), http.post(`${challengesUrl}/challenge-1/flags`, async () => { calls.push('flag'); return HttpResponse.json({ id: 'flag-1', type: 'static', case_insensitive: false }) })); renderPage(); const user = userEvent.setup(); await chooseCategory(user); await user.type(screen.getByPlaceholderText('Flag content'), 'FLAG{secret}'); await user.click(screen.getByRole('button', { name: 'Add flag' })); expect(screen.getByText('••••••••')).toBeVisible(); expect(screen.queryByText('FLAG{secret}')).not.toBeInTheDocument(); await user.click(screen.getByRole('button', { name: 'Create challenge' })); await waitFor(() => expect(calls).toEqual(['challenge', 'flag'])) })
  it('warns when visible has no flags', async () => { setup([category]); renderPage(); const user = userEvent.setup(); const selects = await screen.findAllByRole('combobox'); await user.click(selects[2]); await user.click(await screen.findByRole('option', { name: 'Visible' })); expect(screen.getByText(/no flags yet/)).toBeVisible() })
  it('does not log flag text', async () => { setup([category]); const log = vi.spyOn(console, 'log').mockImplementation(() => undefined); renderPage(); const user = userEvent.setup(); await user.type(await screen.findByPlaceholderText('Flag content'), 'FLAG{private}'); await user.click(screen.getByRole('button', { name: 'Add flag' })); expect(log).not.toHaveBeenCalledWith(expect.stringContaining('FLAG{private}')); log.mockRestore() })
})
