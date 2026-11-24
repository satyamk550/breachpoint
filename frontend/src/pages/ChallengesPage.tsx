import { useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { useEventStatus } from '../hooks/useEventStatus'
import { useMyTeam } from '../hooks/useTeams'
import { listPlayerChallenges, type ChallengeGroup } from '../api/challenges'
import { Badge, EmptyState, Input, Skeleton, Tabs } from '../components/ui'
import { ChallengeDetailDrawer } from '../components/challenges/ChallengeDetailDrawer'
import { useQuery } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'

function stateMessage(state: string) { return state === 'paused' ? 'The event is paused' : state === 'ended' ? 'The event has ended' : 'The event has not started' }
export function ChallengesPage() {
  const team = useMyTeam(); const status = useEventStatus(); const [search, setSearch] = useState(''); const [category, setCategory] = useState('all'); const [selected, setSelected] = useState<string | null>(null)
  const query = useQuery({ queryKey: ['challenges', 'player'], queryFn: listPlayerChallenges, enabled: Boolean(team.data && status.data?.capabilities.can_view_challenges), retry: false })
  const groups = useMemo(() => (query.data ?? []).filter((group) => category === 'all' || group.category_id === category).map((group) => ({ ...group, challenges: group.challenges.filter((challenge) => challenge.title.toLowerCase().includes(search.toLowerCase())) })).filter((group) => group.challenges.length), [query.data, category, search])
  if (team.isFetched && !team.data) return <Navigate replace to="/team/onboarding" />
  if (status.data && !status.data.capabilities.can_view_challenges) return <section className="challenge-page"><p className="eyebrow">Challenges</p><EmptyState title={stateMessage(status.data.state)} description="Challenge access will become available when the event state changes." /></section>
  if (query.isPending || team.isPending || status.isPending) return <section className="challenge-page" aria-label="Loading challenges"><Skeleton className="challenge-heading-skeleton" /><div className="challenge-grid">{[1, 2, 3].map((item) => <Skeleton key={item} className="challenge-card-skeleton" />)}</div></section>
  if (query.isError) return <section className="challenge-page"><EmptyState title={query.error instanceof ApiError && query.error.status === 403 ? 'Challenge access denied' : 'Challenges unavailable'} description={query.error instanceof Error ? query.error.message : 'Try again later.'} /></section>
  const categories = query.data ?? []
  return <section className="challenge-page"><div className="challenge-heading"><div><p className="eyebrow">Player board</p><h1 className="page-title">Challenges</h1><p className="page-description">Choose your next target. Locked and hidden challenges stay out of sight.</p></div><label className="challenge-search"><span className="sr-only">Search challenges</span><Input placeholder="Search challenges" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
    <Tabs label="Challenge categories" value={category} onValueChange={setCategory} items={[{ value: 'all', label: 'All', content: null }, ...categories.map((group) => ({ value: group.category_id, label: group.category_name, content: null }))]} />
    {groups.length === 0 ? <EmptyState title="No challenges yet" description={search ? 'No challenge matches that search.' : 'The board is waiting for its first challenge.'} /> : <div className="challenge-groups">{groups.map((group: ChallengeGroup) => <section key={group.category_id} className="challenge-group" aria-labelledby={`category-${group.category_id}`}><div className="section-header"><h2 className="section-title" id={`category-${group.category_id}`}>{group.category_name}</h2><span className="health-count">{group.challenges.length} challenges</span></div><div className="challenge-grid">{group.challenges.map((challenge) => <button className="challenge-card" key={challenge.id} type="button" onClick={() => setSelected(challenge.id)}><span className="challenge-card-kicker">{challenge.solved_by_my_team ? 'Solved' : 'Open'}</span><strong>{challenge.title}</strong><span className="challenge-card-bottom"><span>{challenge.points} pts</span><span>{challenge.solve_count} solves</span>{challenge.solved_by_my_team && <Badge variant="success">Solved</Badge>}</span></button>)}</div></section>)}</div>}
    <ChallengeDetailDrawer id={selected} onClose={() => setSelected(null)} />
  </section>
}
