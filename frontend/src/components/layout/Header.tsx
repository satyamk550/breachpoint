import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { brand } from '../../config/brand'
import { Badge, Button, useToast } from '../ui'
import { useAuth } from '../../hooks'
import { BrandMark } from './BrandMark'

export function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const navigate = useNavigate()
  const { user, logout } = useAuth()
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
        <Badge className="event-status" variant="info">
          <span className="event-status-mark" aria-hidden="true" />
          Event status: not configured
        </Badge>
      </div>
    </header>
  )
}
