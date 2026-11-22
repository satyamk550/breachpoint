import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/health'

const POLL_INTERVAL_MS = 15_000
const MAX_BACKOFF_MS = 120_000

export const healthQueryKey = ['health'] as const

export function useHealth() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: (query) => {
      if (document.visibilityState === 'hidden') return false
      if (query.state.status === 'error') {
        const failures = Math.max(1, query.state.fetchFailureCount)
        return Math.min(POLL_INTERVAL_MS * 2 ** failures, MAX_BACKOFF_MS)
      }
      return POLL_INTERVAL_MS
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  })
}
