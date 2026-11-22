import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { brand } from '../../config/brand'
import { Badge } from '../ui'
import { BrandMark } from './BrandMark'

export function Header() {
  const [menuOpen, setMenuOpen] = useState(false)

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
        </nav>
        <Badge className="event-status" variant="info">
          <span className="event-status-mark" aria-hidden="true" />
          Event status: not configured
        </Badge>
      </div>
    </header>
  )
}
