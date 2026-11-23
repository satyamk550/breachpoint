import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createTeam, getMyTeam, joinTeam, kickMember, leaveTeam, listTeams, renameTeam, rotateSecret, transferCaptain } from '../api/teams'

export const myTeamKey = ['teams', 'me'] as const
export const teamsKey = ['teams'] as const
export function useMyTeam(enabled = true) { return useQuery({ queryKey: myTeamKey, queryFn: getMyTeam, enabled, retry: false }) }
export function useTeams() { return useQuery({ queryKey: teamsKey, queryFn: listTeams, retry: false }) }

export function useTeamMutation<T extends unknown[], R>(mutationFn: (...args: T) => Promise<R>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (args: T) => mutationFn(...args),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: myTeamKey })
      void client.invalidateQueries({ queryKey: teamsKey })
    },
  })
}
export const teamActions = { createTeam, joinTeam, leaveTeam, kickMember, rotateSecret, renameTeam, transferCaptain }
