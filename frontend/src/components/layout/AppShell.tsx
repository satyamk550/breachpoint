import { Outlet } from 'react-router-dom'
import { Footer } from './Footer'
import { Header } from './Header'
import { EventBanner } from './EventBanner'

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header />
      <EventBanner />
      <main className="page-main page-container" id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
