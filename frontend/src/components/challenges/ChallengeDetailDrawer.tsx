import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getPlayerChallenge, type Challenge } from '../../api/challenges'
import { Badge, Button, CopyButton, Skeleton } from '../ui'
import { MarkdownPreview } from '../MarkdownPreview'

export function ChallengeDetailDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [loading, setLoading] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  useEffect(() => {
    if (!id) return
    setLoading(true); setUnavailable(false); setChallenge(null)
    void getPlayerChallenge(id).then(setChallenge).catch((error: unknown) => { if (error instanceof ApiError && error.status === 404) setUnavailable(true) }).finally(() => setLoading(false))
  }, [id])
  useEffect(() => { if (!id) return; const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }; document.addEventListener('keydown', handler); return () => document.removeEventListener('keydown', handler) }, [id, onClose])
  if (!id) return null
  return <div className="challenge-drawer-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <aside className="challenge-drawer" role="dialog" aria-modal="true" aria-labelledby="challenge-drawer-title">
      <button className="challenge-drawer-close" type="button" onClick={onClose} aria-label="Close challenge details">×</button>
      {loading && <div className="challenge-drawer-loading"><Skeleton /><Skeleton /><Skeleton /></div>}
      {unavailable && <div className="challenge-unavailable"><p className="eyebrow">404</p><h2 id="challenge-drawer-title">Challenge not available</h2><p>This challenge is hidden, locked, or no longer available to your team.</p></div>}
      {challenge && <>
        <p className="eyebrow">Challenge detail</p><h2 id="challenge-drawer-title">{challenge.title}</h2>
        <div className="challenge-detail-meta"><Badge variant="info">{challenge.points} points</Badge><span>{challenge.solve_count} solves</span>{challenge.solved_by_my_team && <Badge variant="success">Solved</Badge>}</div>
        <MarkdownPreview markdown={challenge.description_md} />
        {challenge.tags.length > 0 && <div className="challenge-tags">{challenge.tags.map((tag) => <Badge key={tag} variant="neutral">{tag}</Badge>)}</div>}
        {challenge.connection_info && <div className="challenge-connection"><div><p className="profile-label">Connection info</p><code>{challenge.connection_info}</code></div><CopyButton value={challenge.connection_info} /> </div>}
        <div className="challenge-submit-disabled"><strong>Submit flag</strong><span>Flag submission opens in the next update</span><Button disabled>Submit flag</Button></div>
      </>}
    </aside>
  </div>
}
