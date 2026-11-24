import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ToastProvider } from '../components/ui'
import { server } from '../test/server'
import { AdminChallengesPage } from './AdminChallengesPage'

const listUrl = 'http://localhost:3000/api/v1/admin/challenges'
const categoriesUrl = 'http://localhost:3000/api/v1/admin/categories'
const rows = [{ id: 'c-1', title: 'Visible one', description_md: 'x', category_id: 'cat-1', points: 10, scoring_mode: 'static', initial: 0, minimum: 0, decay: 1, function: 'linear', visibility: 'visible', max_attempts: null, connection_info: null, author: null, created_at: '2026-01-01T00:00:00Z', tags: [], prerequisites: [], solve_count: 3, solved_by_my_team: false }, { id: 'c-2', title: 'Hidden two', description_md: 'x', category_id: 'cat-1', points: 20, scoring_mode: 'static', initial: 0, minimum: 0, decay: 1, function: 'linear', visibility: 'hidden', max_attempts: null, connection_info: null, author: null, created_at: '2026-01-01T00:00:00Z', tags: [], prerequisites: [], solve_count: 0, solved_by_my_team: false }]
function renderPage() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}><ToastProvider><MemoryRouter><AdminChallengesPage /></MemoryRouter></ToastProvider></QueryClientProvider>) }
function setup() { server.use(http.get(listUrl, () => HttpResponse.json(rows)), http.get(categoriesUrl, () => HttpResponse.json([{ id: 'cat-1', name: 'Web', sort_order: 1 }])), http.post('http://localhost:3000/api/v1/admin/challenges/visibility', () => HttpResponse.json(null, { status: 204 }))) }
describe('admin challenge catalog', () => {
  it('filters by title search', async () => { setup(); renderPage(); const user = userEvent.setup(); expect(await screen.findByText('Visible one')).toBeVisible(); const search = screen.getByRole('textbox', { name: 'Search challenges' }); await user.type(search, 'Hidden'); expect(screen.queryByText('Visible one')).not.toBeInTheDocument(); expect(screen.getByText('Hidden two')).toBeVisible() })
  it('supports selecting rows for bulk visibility', async () => { setup(); renderPage(); const user = userEvent.setup(); await screen.findByText('Visible one'); await user.click(screen.getByRole('checkbox', { name: 'Select Visible one' })); expect(screen.getByText('1 selected')).toBeVisible(); expect(screen.getByRole('button', { name: 'Hide selected' })).toBeEnabled() })
  it('shows the full delete confirmation copy', async () => { setup(); renderPage(); const user = userEvent.setup(); await screen.findByText('Visible one'); await user.click(screen.getAllByRole('button', { name: 'Delete' })[0]); expect(await screen.findByRole('heading', { name: 'Delete Visible one?' })).toBeVisible(); expect(screen.getByText(/must be hidden instead/)).toBeVisible() })
})
