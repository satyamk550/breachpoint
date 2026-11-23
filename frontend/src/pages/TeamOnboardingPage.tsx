import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { createTeam, joinTeam } from '../api/teams'
import { useMyTeam } from '../hooks/useTeams'
import { useEventStatus } from '../hooks'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, CopyButton, FieldError, Input, Label, Tabs, useToast } from '../components/ui'
import { useNavigate } from 'react-router-dom'

function message(error: unknown) {
  if (!(error instanceof ApiError)) return 'Something went wrong. Try again.'
  if (error.status === 429) return error.message
  if (error.status === 401) return 'The team name or join secret is incorrect.'
  if (error.status === 403) return 'Rosters are locked while the event is live.'
  if (error.status === 409) return error.message
  return error.message
}

export function TeamOnboardingPage() {
  const navigate = useNavigate(); const { showToast } = useToast(); const myTeam = useMyTeam(); const { data: event } = useEventStatus(); const locked = event?.capabilities.can_change_roster === false
  const [name, setName] = useState(''); const [secret, setSecret] = useState(''); const [error, setError] = useState(''); const [joinMode, setJoinMode] = useState('create'); const [joinSecret, setJoinSecret] = useState<string | null>(null); const [loading, setLoading] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); if (!name.trim() || (joinMode === 'join' && !secret)) { setError('Complete all fields.'); return } setLoading(true)
    try { if (joinMode === 'create') { const result = await createTeam(name.trim()); setJoinSecret(result.join_secret); await myTeam.refetch() } else { const result = await joinTeam(name.trim(), secret); await myTeam.refetch(); navigate(`/teams/${result.id}`) } showToast({ title: joinMode === 'create' ? 'Team created' : 'You joined the team', variant: 'success' }) } catch (caught) { setError(message(caught)) } finally { setLoading(false) }
  }
  if (joinSecret) return <section className="team-page"><Card><CardHeader><CardTitle>Your join secret</CardTitle><CardDescription>Save this now. It will not be shown again.</CardDescription></CardHeader><CardContent><div className="secret-reveal"><code>{joinSecret}</code><CopyButton value={joinSecret} label="Copy join secret" /></div><p className="warning-copy">Anyone with this secret can join your team. Keep it private.</p><Button variant="primary" onClick={() => navigate('/team')}>Continue to team</Button></CardContent></Card></section>
  return <section className="team-page"><div className="team-heading"><p className="eyebrow">Team access</p><h1 className="page-title">Create or join a team</h1><p className="page-description">Your team is your unit for the competition. Choose a name or use an invitation secret.</p></div>{locked && <div className="roster-lock-banner" role="status">Rosters are locked while the event is live. Team creation and joining are disabled.</div>}<Card><CardContent><Tabs label="Team access" value={joinMode} onValueChange={(v) => { setJoinMode(v); setError('') }} items={[{ value: 'create', label: 'Create', content: null }, { value: 'join', label: 'Join', content: null }]} /><form className="auth-form team-form" onSubmit={submit}>{error && <FieldError id="team-error">{error}</FieldError>}<div className="form-field"><Label htmlFor="team-name">Team name</Label><Input id="team-name" disabled={locked} value={name} onChange={(e) => setName(e.target.value)} /></div>{joinMode === 'join' && <div className="form-field"><Label htmlFor="join-secret">Join secret</Label><Input id="join-secret" disabled={locked} value={secret} onChange={(e) => setSecret(e.target.value)} /></div>}<Button type="submit" variant="primary" disabled={locked} loading={loading}>{joinMode === 'create' ? 'Create team' : 'Join team'}</Button></form></CardContent></Card></section>
}
