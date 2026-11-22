import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import { register } from '../api/auth'
import { Button, FieldError, Input, Label, useToast } from '../components/ui'
import { AuthLink, AuthPageFrame } from './AuthPageFrame'

function safeReturnTo(value: string | null) {
  return value?.startsWith('/') && !value.startsWith('//') ? value : '/'
}

export function RegisterPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [values, setValues] = useState({ username: '', email: '', password: '', confirmPassword: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  function update(name: keyof typeof values, value: string) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors: Record<string, string> = {}
    if (!/^[A-Za-z0-9_.-]{3,64}$/.test(values.username.trim())) nextErrors.username = 'Use 3 to 64 letters, numbers, dots, hyphens, or underscores.'
    if (!/^\S+@\S+\.\S+$/.test(values.email)) nextErrors.email = 'Enter a valid email address.'
    if (values.password.length < 10 || values.password.length > 128) nextErrors.password = 'Use 10 to 128 characters.'
    if (values.password !== values.confirmPassword) nextErrors.confirmPassword = 'Passwords do not match.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setLoading(true)
    try {
      const user = await register({ username: values.username.trim(), email: values.email.trim(), password: values.password })
      queryClient.setQueryData(['auth', 'me'], user)
      showToast({ title: 'Account created', description: `Welcome, ${user.username}.`, variant: 'success' })
      navigate(safeReturnTo(new URLSearchParams(location.search).get('returnTo')), { replace: true })
    } catch (error) {
      setErrors({ form: error instanceof ApiError ? error.message : 'Unable to create the account. Try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageFrame
      title="Join the event"
      description="Create a player account and get ready to solve with your team."
      footer={<span>Already registered? <AuthLink to="/login">Sign in</AuthLink></span>}
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {errors.form && <FieldError id="register-form-error">{errors.form}</FieldError>}
        {(['username', 'email', 'password', 'confirmPassword'] as const).map((field) => {
          const labels = { username: 'Username', email: 'Email', password: 'Password', confirmPassword: 'Confirm password' }
          const ids = { username: 'register-username', email: 'register-email', password: 'register-password', confirmPassword: 'register-confirm-password' }
          const errorId = `${ids[field]}-error`
          return (
            <div className="form-field" key={field}>
              <Label htmlFor={ids[field]}>{labels[field]}</Label>
              <Input id={ids[field]} type={field.toLowerCase().includes('password') ? 'password' : field === 'email' ? 'email' : 'text'} autoComplete={field === 'confirmPassword' ? 'new-password' : field === 'password' ? 'new-password' : field} value={values[field]} onChange={(event) => update(field, event.target.value)} invalid={Boolean(errors[field])} aria-describedby={errors[field] ? errorId : undefined} />
              {errors[field] && <FieldError id={errorId}>{errors[field]}</FieldError>}
            </div>
          )
        })}
        <Button type="submit" variant="primary" loading={loading} className="auth-submit">Create account</Button>
        <p className="auth-help">Use a unique password with at least 10 characters.</p>
      </form>
    </AuthPageFrame>
  )
}
