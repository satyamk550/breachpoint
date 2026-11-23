import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { fetchEventAudit, runEventAction, updateEventTimes, type EventAuditEntry, type EventState } from '../api/event'
import { useEventStatus } from '../hooks/useEventStatus'
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Dialog, FieldError, Input, Label, Skeleton, Table, useToast } from '../components/ui'

type Action = 'start' | 'pause' | 'resume' | 'end' | 'reset'

const actionCopy: Record<Action, { label: string; title: string; description: string; variant: 'primary' | 'secondary' | 'danger' }> = {
  start: { label: 'Start now', title: 'Start the event now?', description: 'This starts the event immediately and locks all team rosters.', variant: 'primary' },
  pause: { label: 'Pause', title: 'Pause the event?', description: 'Submissions and hint unlocks will stop until an administrator resumes the event.', variant: 'secondary' },
  resume: { label: 'Resume', title: 'Resume the event?', description: 'The event will become live again. Its scheduled end time will not be enforced after resume.', variant: 'primary' },
  end: { label: 'End', title: 'End the event?', description: 'This permanently ends the event. Players will no longer be able to submit.', variant: 'danger' },
  reset: { label: 'Reset to upcoming', title: 'Reset the event to upcoming?', description: 'This clears the lifecycle override and schedule, returning the event to draft upcoming. Teams, users, and other data will not be deleted.', variant: 'danger' },
}

const lifecycleActions: Action[] = ['start', 'pause', 'resume', 'end']

function localInputValue(timestamp: string | null) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function utcValue(value: string) {
  return value ? new Date(value).toISOString() : null
}

function stateLabel(state: EventState) {
  return state === 'draft_upcoming' ? 'Upcoming' : state[0].toUpperCase() + state.slice(1)
}

function AuditTable({ entries }: { entries: EventAuditEntry[] }) {
  return (
    <Table
      caption="Recent event changes"
      columns={[
        { id: 'action', header: 'Action', cell: (entry) => <span className="admin-audit-action">{entry.action.replace(/_/g, ' ')}</span> },
        { id: 'time', header: 'Time', cell: (entry) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(entry.created_at)) },
      ]}
      rows={entries}
      rowKey={(entry) => entry.id}
    />
  )
}

export function AdminEventPage() {
  const statusQuery = useEventStatus()
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [timeError, setTimeError] = useState<string | null>(null)
  const [activeAction, setActiveAction] = useState<Action | null>(null)
  const [saving, setSaving] = useState(false)
  const { showToast } = useToast()
  const auditQuery = useMemo(() => fetchEventAudit(), [])
  const [audit, setAudit] = useState<EventAuditEntry[]>([])

  useEffect(() => {
    if (statusQuery.data) {
      setStart(localInputValue(statusQuery.data.start))
      setEnd(localInputValue(statusQuery.data.end))
    }
  }, [statusQuery.data])

  useEffect(() => { void auditQuery.then(setAudit).catch(() => undefined) }, [auditQuery])

  async function refreshAudit() {
    try { setAudit(await fetchEventAudit()) } catch { /* status action toast is enough */ }
  }

  async function saveTimes() {
    setTimeError(null)
    if (start && end && new Date(start) >= new Date(end)) {
      setTimeError('Event end must be after event start.')
      return
    }
    setSaving(true)
    try {
      await updateEventTimes(utcValue(start), utcValue(end))
      await statusQuery.refetch()
      await refreshAudit()
      showToast({ title: 'Schedule saved', description: 'Event times were updated.', variant: 'success' })
    } catch (error) {
      setTimeError(error instanceof ApiError ? error.message : 'Unable to save event times.')
    } finally { setSaving(false) }
  }

  async function confirmAction() {
    if (!activeAction) return
    setSaving(true)
    try {
      await runEventAction(activeAction)
      await statusQuery.refetch()
      await refreshAudit()
      showToast({ title: `${actionCopy[activeAction].label} complete`, description: 'Event status has been refreshed.', variant: 'success' })
      setActiveAction(null)
    } catch (error) {
      showToast({ title: 'Action failed', description: error instanceof ApiError ? error.message : 'Try again in a moment.', variant: 'danger' })
    } finally { setSaving(false) }
  }

  if (statusQuery.isPending) return <section className="admin-event-page" aria-label="Loading event controls"><Skeleton className="admin-event-skeleton" /></section>
  if (statusQuery.isError || !statusQuery.data) return <section className="admin-event-page"><p className="page-description">Event status is unavailable. Try refreshing the page.</p></section>

  const { state, capabilities } = statusQuery.data
  const canAction: Record<Action, boolean> = { start: state === 'draft_upcoming', pause: state === 'live', resume: state === 'paused', end: state === 'live' || state === 'paused', reset: state === 'paused' || state === 'ended' }

  return (
    <div className="admin-event-page">
      <section className="admin-event-heading" aria-labelledby="admin-event-title">
        <div><p className="eyebrow">Event operations</p><h1 className="page-title" id="admin-event-title">Control room</h1><p className="page-description">Manage the event lifecycle and its operating window.</p></div>
        <Card className="admin-state-card"><span className="admin-state-label">Current state</span><Badge variant={state === 'live' ? 'success' : state === 'paused' ? 'warning' : state === 'ended' ? 'neutral' : 'info'} role="status">{stateLabel(state)}</Badge><span className="admin-state-time">Server time {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(statusQuery.data.server_time))}</span></Card>
      </section>
      <section className="admin-event-grid">
        <Card><CardHeader><CardTitle>Schedule</CardTitle><CardDescription>Times are shown in your browser’s local time and sent to the server as UTC.</CardDescription></CardHeader><CardContent><div className="admin-time-grid"><div className="form-field"><Label htmlFor="event-start">Start time</Label><Input id="event-start" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} aria-describedby={timeError ? 'event-time-error' : undefined} invalid={Boolean(timeError)} /></div><div className="form-field"><Label htmlFor="event-end">End time</Label><Input id="event-end" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} aria-describedby={timeError ? 'event-time-error' : undefined} invalid={Boolean(timeError)} /></div></div>{timeError && <FieldError id="event-time-error">{timeError}</FieldError>}<Button className="admin-save-button" loading={saving} disabled={saving} onClick={() => void saveTimes()}>Save schedule</Button></CardContent></Card>
        <Card><CardHeader><CardTitle>Lifecycle actions</CardTitle><CardDescription>Each action changes what players can do immediately.</CardDescription></CardHeader><CardContent><div className="admin-action-list">{lifecycleActions.map((action) => <Button key={action} variant={actionCopy[action].variant} disabled={!canAction[action] || saving} onClick={() => setActiveAction(action)}>{actionCopy[action].label}</Button>)}{canAction.reset && <Button variant={actionCopy.reset.variant} disabled={saving} onClick={() => setActiveAction('reset')}>{actionCopy.reset.label}</Button>}</div><p className="warning-copy">After Resume, the scheduled end time is not enforced. Press End manually when the event is over.</p><dl className="admin-capabilities">{Object.entries(capabilities).map(([name, enabled]) => <div key={name}><dt>{name.replace(/_/g, ' ')}</dt><dd>{enabled ? 'Enabled' : 'Disabled'}</dd></div>)}</dl></CardContent></Card>
      </section>
      <section className="admin-audit-section" aria-labelledby="audit-title"><div className="section-header"><div><p className="eyebrow">Accountability</p><h2 className="section-title" id="audit-title">Recent changes</h2></div><span className="health-count">Last 10 event entries</span></div><Card className="admin-audit-card">{audit.length ? <AuditTable entries={audit} /> : <p className="admin-empty">No event changes recorded yet.</p>}</Card></section>
      {activeAction && <Dialog open onOpenChange={(open) => { if (!open && !saving) setActiveAction(null) }} title={actionCopy[activeAction].title} description={actionCopy[activeAction].description}><div className="admin-dialog-actions"><Button variant="ghost" disabled={saving} onClick={() => setActiveAction(null)}>Cancel</Button><Button variant={actionCopy[activeAction].variant} loading={saving} onClick={() => void confirmAction()}>Confirm {actionCopy[activeAction].label}</Button></div></Dialog>}
    </div>
  )
}
