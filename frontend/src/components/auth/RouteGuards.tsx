import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks'
import { useMyTeam } from '../../hooks/useTeams'
import { ForbiddenPage } from '../../pages/ForbiddenPage'

function LoginRedirect() {
  const location = useLocation()
  const returnTo = encodeURIComponent(`${location.pathname}${location.search}` || '/')
  return <Navigate replace to={`/login?returnTo=${returnTo}`} />
}

function AuthLoading() {
  return (
    <section className="auth-loading" aria-label="Loading account">
      <span className="ui-skeleton auth-loading-line" />
      <span className="ui-skeleton auth-loading-line auth-loading-line-short" />
      <span className="ui-skeleton auth-loading-block" />
    </section>
  )
}

export function ProtectedRoute({ allowNoTeam = false }: { allowNoTeam?: boolean }) {
  const { isLoading, isAuthenticated, user } = useAuth()
  const team = useMyTeam(isAuthenticated)
  if (isLoading) return <AuthLoading />
  if (!isAuthenticated) return <LoginRedirect />
  if (!allowNoTeam && user?.role === 'player' && team.isFetched && !team.data) return <Navigate replace to="/team/onboarding" />
  return <Outlet />
}

export function PlayerHomeRoute() {
  const { isLoading, isAuthenticated, user } = useAuth()
  const team = useMyTeam(isAuthenticated)
  if (isLoading || (isAuthenticated && team.isPending)) return <AuthLoading />
  if (isAuthenticated && user?.role === 'player' && !team.data) return <Navigate replace to="/team/onboarding" />
  return <Outlet />
}

export function AdminRoute() {
  const { isLoading, user } = useAuth()
  if (isLoading) return <AuthLoading />
  if (!user) return <LoginRedirect />
  if (user.role !== 'admin') return <ForbiddenPage />
  return <Outlet />
}
