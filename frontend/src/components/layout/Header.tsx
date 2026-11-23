import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { brand } from '../../config/brand'
import { Badge, Button, useToast } from '../ui'
import { useAuth } from '../../hooks'
import { useEventStatus } from '../../hooks'
import { useMyTeam } from '../../hooks/useTeams'
import { BrandMark } from './BrandMark'

export function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { data: myTeam } = useMyTeam(Boolean(user))
  const { data: eventStatus } = useEventStatus()
  const { showToast } = useToast()

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
      showToast({ title: 'Signed out', description: 'Your session has ended.', variant: 'success' })
      navigate('/login', { replace: true })
    } catch {
      showToast({ title: 'Unable to sign out', description: 'Try again in a moment.', variant: 'danger' })
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <header className="topbar page-container">
      <NavLink className="brand" to="/" aria-label={`${brand.name} home`}>
        <BrandMark />
        <span className="brand-name">{brand.name}</span>
      </NavLink>

      <div className="header-actions">
        <button
          className="mobile-nav-toggle"
          type="button"
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span aria-hidden="true">{menuOpen ? '×' : '☰'}</span>
        </button>
        <nav
          className={`primary-nav ${menuOpen ? 'is-open' : ''}`.trim()}
          id="primary-navigation"
          aria-label="Primary navigation"
        >
          <NavLink to="/" end onClick={() => setMenuOpen(false)}>
            Status
          </NavLink>
          {user ? (
            <>
              {user.role === 'player' && <NavLink to={myTeam ? '/team' : '/team/onboarding'} onClick={() => setMenuOpen(false)}>My team</NavLink>}
              {user.role === 'player' && <NavLink to="/teams" onClick={() => setMenuOpen(false)}>Teams</NavLink>}
              {user.role === 'admin' && <NavLink to="/admin/event" onClick={() => setMenuOpen(false)}>Admin</NavLink>}
              <NavLink to="/profile" onClick={() => setMenuOpen(false)}>Profile</NavLink>
              <span className="header-user">{user.username}</span>
              <Button variant="ghost" loading={loggingOut} onClick={handleLogout}>Log out</Button>
            </>
          ) : (
            <>
              <NavLink to="/login" onClick={() => setMenuOpen(false)}>Sign in</NavLink>
              <NavLink to="/register" onClick={() => setMenuOpen(false)}>Register</NavLink>
            </>
          )}
        </nav>
        <Badge className={`event-status event-status-${eventStatus?.state ?? 'draft_upcoming'}`} variant={eventStatus?.state === 'live' ? 'success' : eventStatus?.state === 'paused' ? 'warning' : eventStatus?.state === 'ended' ? 'neutral' : 'info'} aria-label={`Event status: ${eventStatus?.state === 'draft_upcoming' ? 'Upcoming' : eventStatus?.state ? eventStatus.state[0].toUpperCase() + eventStatus.state.slice(1) : 'Upcoming'}`}>
          <span className="event-status-mark" aria-hidden="true" />
          {eventStatus?.state === 'draft_upcoming' ? 'Upcoming' : eventStatus?.state ? eventStatus.state[0].toUpperCase() + eventStatus.state.slice(1) : 'Upcoming'}
        </Badge>
      </div>
    </header>
  )
}
