import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { brand } from '../config/brand'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui'

export function AuthPageFrame({
  title,
  description,
  footer,
  children,
}: {
  title: string
  description: string
  footer: ReactNode
  children: ReactNode
}) {
  return (
    <section className="auth-page">
      <div className="auth-intro">
        <p className="eyebrow">{brand.name} access</p>
        <h1 className="page-title">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      <Card className="auth-card">
        <CardHeader>
          <CardTitle>Account details</CardTitle>
          <CardDescription>Use your event account to continue.</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
        <div className="auth-card-footer">{footer}</div>
      </Card>
    </section>
  )
}

export function AuthLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link className="auth-link" to={to}>{children}</Link>
}
