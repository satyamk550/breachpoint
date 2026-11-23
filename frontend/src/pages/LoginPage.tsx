import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { login } from '../api/auth'
import { getMyTeam } from '../api/teams'
import { Button, FieldError, Input, Label } from '../components/ui'
import { useToast } from '../components/ui'
import { useQueryClient } from '@tanstack/react-query'
import { AuthPageFrame, AuthLink } from './AuthPageFrame'

function safeReturnTo(value: string | null) {
  return value?.startsWith('/') && !value.startsWith('//') ? value : '/'
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ username?: string; password?: string; form?: string }>({})
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors: typeof errors = {}
    if (!username.trim()) nextErrors.username = 'Enter your username.'
    if (!password) nextErrors.password = 'Enter your password.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setLoading(true)
    try {
      const user = await login({ username: username.trim(), password })
      queryClient.setQueryData(['auth', 'me'], user)
      const team = user.role === 'player' ? await getMyTeam() : null
      if (user.role === 'player') queryClient.setQueryData(['teams', 'me'], team)
      showToast({ title: 'Signed in', description: `Welcome back, ${user.username}.`, variant: 'success' })
      navigate(user.role === 'player' ? (team ? '/team' : '/team/onboarding') : safeReturnTo(new URLSearchParams(location.search).get('returnTo')), { replace: true })
    } catch (error) {
      setErrors({ form: error instanceof ApiError ? error.message : 'Unable to sign in. Try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageFrame
      title="Return to the arena"
      description="Sign in to see your team workspace and event activity."
      footer={<span>New here? <AuthLink to="/register">Create an account</AuthLink></span>}
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {errors.form && <FieldError id="login-form-error">{errors.form}</FieldError>}
        <div className="form-field">
          <Label htmlFor="login-username">Username</Label>
          <Input id="login-username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} invalid={Boolean(errors.username)} aria-describedby={errors.username ? 'login-username-error' : undefined} />
          {errors.username && <FieldError id="login-username-error">{errors.username}</FieldError>}
        </div>
        <div className="form-field">
          <Label htmlFor="login-password">Password</Label>
          <Input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} invalid={Boolean(errors.password)} aria-describedby={errors.password ? 'login-password-error' : undefined} />
          {errors.password && <FieldError id="login-password-error">{errors.password}</FieldError>}
        </div>
        <Button type="submit" variant="primary" loading={loading} className="auth-submit">Sign in</Button>
        <p className="auth-help">Passwords are handled by the event server and never stored in this browser.</p>
      </form>
    </AuthPageFrame>
  )
}

export function LoginLink() {
  return <Link to="/login">Sign in</Link>
}
