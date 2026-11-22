export type ServerClockSnapshot = {
  browserEpochMs: number
  monotonicAtFetchMs: number
  offsetMs: number
}

export function createServerClockSnapshot(
  serverTime: string,
  browserEpochMs = Date.now(),
  monotonicAtFetchMs = performance.now(),
): ServerClockSnapshot {
  const serverEpoch = Date.parse(serverTime)
  return {
    browserEpochMs,
    monotonicAtFetchMs,
    offsetMs: serverEpoch - browserEpochMs,
  }
}

export function getServerNowMs(
  snapshot: ServerClockSnapshot,
  monotonicNowMs = performance.now(),
): number {
  return snapshot.browserEpochMs + snapshot.offsetMs
    + Math.max(0, monotonicNowMs - snapshot.monotonicAtFetchMs)
}
