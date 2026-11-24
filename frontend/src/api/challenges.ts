import { apiDelete, apiGet, apiPatch, apiPost } from './client'

export type Visibility = 'draft' | 'visible' | 'hidden'
export type ScoringMode = 'static' | 'dynamic'
export type FlagType = 'static' | 'regex'

export type Category = { id: string; name: string; sort_order: number }
export type Prerequisite = { challenge_id: string; requires_challenge_id: string }
export type Challenge = {
  id: string
  title: string
  description_md: string
  category_id: string
  points: number
  scoring_mode: ScoringMode
  initial: number | null
  minimum: number | null
  decay: number | null
  function: 'linear' | 'logarithmic' | null
  visibility: Visibility
  max_attempts: number | null
  connection_info: string | null
  author: string | null
  created_at: string
  tags: string[]
  prerequisites: Prerequisite[]
  solve_count: number
  solved_by_my_team: boolean
}
export type ChallengeGroup = { category_id: string; category_name: string; sort_order: number; challenges: Challenge[] }
export type Flag = { id: string; type: FlagType; content?: string; case_insensitive: boolean }
export type FlagWrite = { type: FlagType; content: string; case_insensitive: boolean }

export type ChallengeInput = {
  title: string
  description_md: string
  category_id: string
  points: number
  scoring_mode: ScoringMode
  initial?: number
  minimum?: number
  decay?: number
  function?: 'linear' | 'logarithmic'
  visibility?: Visibility
  max_attempts?: number | null
  connection_info?: string | null
  author?: string | null
  tags: string[]
  prerequisites: string[]
}

export function listPlayerChallenges() { return apiGet<ChallengeGroup[]>('/challenges') }
export function getPlayerChallenge(id: string) { return apiGet<Challenge>(`/challenges/${id}`) }
export function listCategories() { return apiGet<Category[]>('/admin/categories') }
export function createCategory(input: { name: string; sort_order: number }) { return apiPost<Category>('/admin/categories', input) }
export function updateCategory(id: string, input: { name?: string; sort_order?: number }) { return apiPatch<Category>(`/admin/categories/${id}`, input) }
export function deleteCategory(id: string) { return apiDelete<void>(`/admin/categories/${id}`) }
export function listAdminChallenges() { return apiGet<Challenge[]>('/admin/challenges') }
export function getAdminChallenge(id: string) { return apiGet<Challenge>(`/admin/challenges/${id}`) }
export function createChallenge(input: ChallengeInput) { return apiPost<Challenge>('/admin/challenges', input) }
export function updateChallenge(id: string, input: Partial<ChallengeInput>) { return apiPatch<Challenge>(`/admin/challenges/${id}`, input) }
export function deleteChallenge(id: string) { return apiDelete<void>(`/admin/challenges/${id}`) }
export function bulkVisibility(visibility: Visibility, challenge_ids: string[]) { return apiPost<void>('/admin/challenges/visibility', { visibility, challenge_ids }) }
export function cloneChallenge(id: string) { return apiPost<Challenge>(`/admin/challenges/${id}/clone`) }
export function listFlags(id: string) { return apiGet<Flag[]>(`/admin/challenges/${id}/flags`) }
export function createFlag(id: string, input: FlagWrite) { return apiPost<Flag>(`/admin/challenges/${id}/flags`, input) }
export function updateFlag(challengeId: string, flagId: string, input: Partial<FlagWrite>) { return apiPatch<Flag>(`/admin/challenges/${challengeId}/flags/${flagId}`, input) }
export function deleteFlag(challengeId: string, flagId: string) { return apiDelete<void>(`/admin/challenges/${challengeId}/flags/${flagId}`) }
