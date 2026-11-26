import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getChallengeHealth, listAdminChallenges } from '../api/challenges'
import { Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Skeleton, useToast } from '../components/ui'
import { ApiError } from '../api/client'

const groups = [{ key: 'no_active_flag', label: 'Visible challenges without flags' }, { key: 'missing_files', label: 'Missing files' }, { key: 'file_sha256_mismatch', label: 'Mismatched file checksums' }, { key: 'invalid_scoring_bounds', label: 'Invalid scoring bounds' }, { key: 'prerequisite_cycles', label: 'Prerequisite cycles' }, { key: 'visible_zero_points', label: 'Visible challenges with zero points' }] as const
export function AdminChallengeHealthPage() {
  const { showToast } = useToast(); const health = useQuery({ queryKey: ['admin', 'challenge-health'], queryFn: getChallengeHealth }); const challenges = useQuery({ queryKey: ['admin', 'challenges'], queryFn: listAdminChallenges });
  if (health.isPending || challenges.isPending) return <section className="admin-challenges-page"><Skeleton className="admin-page-skeleton" /></section>
  if (health.isError) return <section className="admin-challenges-page"><EmptyState title="Health report unavailable" description={health.error instanceof ApiError ? health.error.message : 'Try again.'} /></section>
  const challengeMap = new Map((challenges.data ?? []).map((challenge) => [challenge.id, challenge]))
  const total = groups.reduce((count, group) => count + health.data[group.key].length, 0)
  return <section className="admin-challenges-page"><div className="admin-page-heading"><div><p className="eyebrow">Administration / challenges</p><h1 className="page-title">Challenge health</h1><p className="page-description">A pre-event check for flags, files, scoring bounds, and prerequisites.</p></div><Button variant="secondary" onClick={() => { void health.refetch().then((result) => { if (result.isError) showToast({ title: 'Refresh failed', variant: 'danger' }) }) }}>Refresh</Button></div>{total === 0 ? <Card><CardContent><EmptyState title="All clear" description="No challenge health issues were found." /></CardContent></Card> : <div className="health-report-grid">{groups.map((group) => <Card key={group.key}><CardHeader><CardTitle>{group.label}</CardTitle></CardHeader><CardContent>{health.data[group.key].length === 0 ? <p className="help-copy">None found.</p> : <ul className="health-issue-list">{health.data[group.key].map((id) => { const challenge = challengeMap.get(id); return <li key={id}><Link to={`/admin/challenges/${challenge?.id ?? id}/edit`}>{challenge?.title ?? id}</Link></li> })}</ul>}</CardContent></Card>)}</div>}</section>
}
