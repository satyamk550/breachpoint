import { Link } from 'react-router-dom'

export function ForbiddenPage() {
  return (
    <section className="error-page" aria-labelledby="forbidden-title">
      <p className="not-found-code">403 / Forbidden</p>
      <h1 className="page-title" id="forbidden-title">Admin access required.</h1>
      <p className="page-description">
        This control surface is reserved for event administrators.
      </p>
      <Link className="ui-button ui-button-primary" to="/">Return to status</Link>
    </section>
  )
}
