import { brand } from '../../config/brand'

export function Footer() {
  return (
    <footer className="page-footer page-container">
      <span className="footer-brand">{brand.name}</span>
      <span className="footer-tagline">{brand.tagline}</span>
      <span>Self-hosted event platform</span>
    </footer>
  )
}
