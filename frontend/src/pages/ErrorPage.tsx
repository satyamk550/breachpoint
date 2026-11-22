import { Link } from 'react-router-dom'

export function ErrorPage() {
  return (
    <section className="error-page" aria-labelledby="error-title">
      <p className="not-found-code">Application error</p>
      <h1 className="page-title" id="error-title">Something went wrong.</h1>
      <p className="page-description">
        The page could not be displayed. Return to the status page to continue.
      </p>
      <Link className="ui-button ui-button-primary" to="/">Return to status</Link>
    </section>
  )
}
