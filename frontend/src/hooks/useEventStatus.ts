import { useQuery } from '@tanstack/react-query'
import { fetchEventStatus } from '../api/event'

const POLL_INTERVAL_MS = 15_000

export const eventStatusQueryKey = ['event-status'] as const

export function useEventStatus() {
  return useQuery({
    queryKey: eventStatusQueryKey,
    queryFn: ({ signal }) => fetchEventStatus(signal),
    refetchInterval: () => document.visibilityState === 'hidden' ? false : POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  })
}
