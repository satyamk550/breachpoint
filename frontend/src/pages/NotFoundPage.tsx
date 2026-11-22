import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="not-found-page" aria-labelledby="not-found-title">
      <p className="not-found-code">404 / Page not found</p>
      <h1 className="page-title" id="not-found-title">This page is not available.</h1>
      <p className="page-description">The address may be incorrect or the page may have moved.</p>
      <Link className="ui-button ui-button-primary" to="/">Return to status</Link>
    </section>
  )
}
