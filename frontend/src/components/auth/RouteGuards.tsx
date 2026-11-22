import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks'

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

export function ProtectedRoute() {
  const { isLoading, isAuthenticated } = useAuth()
  if (isLoading) return <AuthLoading />
  if (!isAuthenticated) return <LoginRedirect />
  return <Outlet />
}

export function AdminRoute() {
  const { isLoading, user } = useAuth()
  if (isLoading) return <AuthLoading />
  if (!user) return <LoginRedirect />
  if (user.role !== 'admin') return <Navigate replace to="/" />
  return <Outlet />
}
