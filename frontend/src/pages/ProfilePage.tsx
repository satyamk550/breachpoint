import { useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import { changePassword } from '../api/auth'
import { Link } from 'react-router-dom'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, FieldError, Input, Label, useToast } from '../components/ui'
import { useAuth } from '../hooks'
import { useMyTeam } from '../hooks/useTeams'

export function ProfilePage() {
  const { user } = useAuth()
  const { data: team } = useMyTeam(Boolean(user))
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [values, setValues] = useState({ current: '', next: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (values.next.length < 10 || values.next.length > 128) {
      setError('Use 10 to 128 characters for the new password.')
      return
    }
    if (values.next !== values.confirm) {
      setError('New passwords do not match.')
      return
    }
    setError('')
    setLoading(true)
    try {
      await changePassword({ current_password: values.current, new_password: values.next })
      queryClient.setQueryData(['auth', 'me'], null)
      showToast({ title: 'Password changed', description: 'Sign in again with your new password.', variant: 'success' })
      window.history.pushState({}, '', '/login')
      window.dispatchEvent(new PopStateEvent('popstate'))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to change your password. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="profile-page">
      <div className="profile-heading">
        <p className="eyebrow">Account</p>
        <h1 className="page-title">Your profile</h1>
        <p className="page-description">Manage your account details and keep your access secure.</p>
      </div>
      <div className="profile-grid">
        {!team && <Card className="profile-team-notice"><CardContent><strong>You are not in a team yet</strong><p>Join a team before the event begins.</p><Link className="ui-button ui-button-primary" to="/team/onboarding">Create or join a team</Link></CardContent></Card>}
        <Card>
          <CardHeader><CardTitle>Identity</CardTitle><CardDescription>Your event account.</CardDescription></CardHeader>
          <CardContent className="profile-identity">
            <div><span className="profile-label">Username</span><strong>{user?.username}</strong></div>
            <div><span className="profile-label">Email</span><strong>{user?.email}</strong></div>
            <div><span className="profile-label">Role</span><strong>{user?.role}</strong></div>
          </CardContent>
        </Card>
        {team && <Card><CardHeader><CardTitle>Your team</CardTitle><CardDescription>Your current roster.</CardDescription></CardHeader><CardContent className="profile-identity"><div><span className="profile-label">Team</span><strong>{team.name}</strong></div><div><span className="profile-label">Members</span><strong>{team.member_count} of 4</strong></div><div><span className="profile-label">Your role</span><strong>{team.captain_id === user?.id ? 'Captain' : 'Member'}</strong></div><Link className="ui-button ui-button-secondary" to="/team">Manage team</Link></CardContent></Card>}
        <Card>
          <CardHeader><CardTitle>Change password</CardTitle><CardDescription>Changing it signs out every active session.</CardDescription></CardHeader>
          <CardContent>
            <form className="auth-form" onSubmit={handleSubmit} noValidate>
              {error && <FieldError id="profile-password-error">{error}</FieldError>}
              <div className="form-field"><Label htmlFor="current-password">Current password</Label><Input id="current-password" type="password" autoComplete="current-password" value={values.current} onChange={(event) => setValues({ ...values, current: event.target.value })} /></div>
              <div className="form-field"><Label htmlFor="new-password">New password</Label><Input id="new-password" type="password" autoComplete="new-password" value={values.next} onChange={(event) => setValues({ ...values, next: event.target.value })} /></div>
              <div className="form-field"><Label htmlFor="confirm-new-password">Confirm new password</Label><Input id="confirm-new-password" type="password" autoComplete="new-password" value={values.confirm} onChange={(event) => setValues({ ...values, confirm: event.target.value })} /></div>
              <Button type="submit" variant="primary" loading={loading}>Change password</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
