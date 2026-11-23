import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Header } from '../components/layout/Header'
import { AuthProvider } from '../hooks'
import { ToastProvider } from '../components/ui'
import { server } from '../test/server'
import { LoginPage } from './LoginPage'
import { ProfilePage } from './ProfilePage'
import { ProtectedRoute } from '../components/auth/RouteGuards'
import { PlayerHomeRoute } from '../components/auth/RouteGuards'
import { teamMeUrl } from '../test/server'

const loginUrl = 'http://localhost:3000/api/v1/auth/login'
const meUrl = 'http://localhost:3000/api/v1/auth/me'
const logoutUrl = 'http://localhost:3000/api/v1/auth/logout'

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { gcTime: 0, retry: false } } })
}

function renderLogin() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <MemoryRouter initialEntries={['/login']}>
          <LoginPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

function renderGuardedProfile() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={['/profile']}>
            <Routes>
              <Route path="login" element={<div>Login destination</div>} />
              <Route element={<ProtectedRoute />}>
                <Route path="profile" element={<div>Private profile</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

function renderHeader() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={['/']}>
            <Header />
          </MemoryRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

async function fillLoginForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Username'), 'runner')
  await user.type(screen.getByLabelText('Password'), 'long-enough-password')
}

describe('authentication UI', () => {
  it('shows My team and Teams links for a signed-in player with a team', async () => {
    server.use(
      http.get(meUrl, () => HttpResponse.json({ id: 'user-1', username: 'runner', email: 'runner@example.com', role: 'player', created_at: '2026-01-01T00:00:00Z', last_login_at: null })),
      http.get(teamMeUrl, () => HttpResponse.json({ id: 'team-1', name: 'Byte Wardens', member_count: 2, captain_id: 'user-1', is_banned: false, is_hidden: false, created_at: '2026-01-01T00:00:00Z', members: [] })),
    )
    renderHeader()
    await waitFor(() => expect(screen.getByRole('link', { name: 'My team' })).toHaveAttribute('href', '/team'))
    expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute('href', '/teams')
  })

  it('redirects a player without a team from home to onboarding', async () => {
    server.use(
      http.get(meUrl, () => HttpResponse.json({ id: 'user-1', username: 'runner', email: 'runner@example.com', role: 'player', created_at: '2026-01-01T00:00:00Z', last_login_at: null })),
      http.get(teamMeUrl, () => HttpResponse.json(null)),
    )
    render(
      <QueryClientProvider client={createQueryClient()}><ToastProvider><AuthProvider><MemoryRouter initialEntries={['/']}><Routes><Route element={<PlayerHomeRoute />}><Route index element={<div>Status destination</div>} /></Route><Route path="team/onboarding" element={<div>Onboarding destination</div>} /></Routes></MemoryRouter></AuthProvider></ToastProvider></QueryClientProvider>,
    )
    expect(await screen.findByText('Onboarding destination')).toBeVisible()
  })

  it('shows the team card on Profile for a player with a team', async () => {
    server.use(
      http.get(meUrl, () => HttpResponse.json({ id: 'user-1', username: 'runner', email: 'runner@example.com', role: 'player', created_at: '2026-01-01T00:00:00Z', last_login_at: null })),
      http.get(teamMeUrl, () => HttpResponse.json({ id: 'team-1', name: 'Byte Wardens', member_count: 2, captain_id: 'user-1', is_banned: false, is_hidden: false, created_at: '2026-01-01T00:00:00Z', members: [] })),
    )
    render(<QueryClientProvider client={createQueryClient()}><ToastProvider><AuthProvider><MemoryRouter><ProfilePage /></MemoryRouter></AuthProvider></ToastProvider></QueryClientProvider>)
    expect(await screen.findByText('Your team')).toBeVisible()
    expect(screen.getByText('Byte Wardens')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Manage team' })).toHaveAttribute('href', '/team')
  })

  it('logs in successfully and shows a welcome toast', async () => {
    document.cookie = 'csrf_token=test-csrf'
    server.use(http.post(loginUrl, () => HttpResponse.json({
      id: 'user-1', username: 'runner', email: 'runner@example.com', role: 'player', created_at: '2026-01-01T00:00:00Z', last_login_at: null,
    })))
    const user = userEvent.setup()
    renderLogin()
    await fillLoginForm(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Welcome back, runner.')).toBeVisible()
  })

  it('shows a field-level form error when login fails', async () => {
    document.cookie = 'csrf_token=test-csrf'
    server.use(http.post(loginUrl, () => HttpResponse.json({ detail: 'Invalid username or password' }, { status: 401 })))
    const user = userEvent.setup()
    renderLogin()
    await fillLoginForm(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Invalid username or password')).toBeVisible()
  })

  it('redirects unauthenticated users from protected routes with a return path', async () => {
    server.use(http.get(meUrl, () => HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })))
    renderGuardedProfile()

    expect(await screen.findByText('Login destination')).toBeVisible()
  })

  it('shows the Retry-After message for rate-limited login attempts', async () => {
    document.cookie = 'csrf_token=test-csrf'
    server.use(http.post(loginUrl, () => new HttpResponse(null, {
      status: 429,
      headers: { 'Retry-After': '17' },
    })))
    const user = userEvent.setup()
    renderLogin()
    await fillLoginForm(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Too many requests. Try again in 17 seconds.', { selector: '.ui-toast p' })).toBeVisible()
  })

  it('logs out from the signed-in header', async () => {
    server.use(
      http.get(meUrl, () => HttpResponse.json({
        id: 'user-1', username: 'runner', email: 'runner@example.com', role: 'player', created_at: '2026-01-01T00:00:00Z', last_login_at: null,
      })),
      http.post(logoutUrl, () => new HttpResponse(null, { status: 204 })),
    )
    const user = userEvent.setup()
    renderHeader()
    expect(await screen.findByText('runner')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' })).toBeVisible())
  })
})
