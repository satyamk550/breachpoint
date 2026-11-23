import { apiGet, apiPatch, apiPost } from './client'

export type TeamMember = { id: string; username: string; role: 'player' | 'admin' }
export type TeamSummary = { id: string; name: string; member_count: number }
export type Team = TeamSummary & {
  captain_id: string
  is_banned: boolean
  is_hidden: boolean
  created_at: string
  members: TeamMember[]
}
export type TeamSecretResponse = { team: Team; join_secret: string }

export function getMyTeam() { return apiGet<Team | null>('/teams/me') }
export function listTeams() { return apiGet<TeamSummary[]>('/teams') }
export function getTeam(id: string) { return apiGet<Team>(`/teams/${id}`) }
export function createTeam(name: string) { return apiPost<TeamSecretResponse>('/teams', { name }) }
export function joinTeam(name: string, secret: string) { return apiPost<Team>('/teams/join', { name, secret }) }
export function leaveTeam() { return apiPost<void>('/teams/leave') }
export function kickMember(teamId: string, userId: string) { return apiPost<void>(`/teams/${teamId}/kick`, { user_id: userId }) }
export function rotateSecret(teamId: string) { return apiPost<TeamSecretResponse>(`/teams/${teamId}/rotate-secret`) }
export function renameTeam(teamId: string, name: string) { return apiPatch<Team>(`/teams/${teamId}/rename`, { name }) }
export function transferCaptain(teamId: string, userId: string) { return apiPost<Team>(`/teams/${teamId}/transfer-captain`, { user_id: userId }) }
