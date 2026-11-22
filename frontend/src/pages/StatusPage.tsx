import { Button, Card, Badge, EmptyState, Skeleton, Spinner } from '../components/ui'
import { useHealth } from '../hooks/useHealth'
import type { ServiceHealth } from '../api/health'

type ServiceCardProps = {
  name: string
  description: string
  index: string
  mark: string
  status: 'healthy' | 'unavailable' | 'unknown' | 'last-known-healthy' | 'last-known-unavailable'
}

function ServiceCard({ name, description, index, mark, status }: ServiceCardProps) {
  const isHealthy = status === 'healthy' || status === 'last-known-healthy'
  const isUnknown = status === 'unknown'
  const variant = isUnknown
    ? 'neutral'
    : isHealthy
      ? 'success'
      : 'danger'
  const label = isUnknown
    ? 'Checking'
    : status.startsWith('last-known')
      ? `Last known: ${isHealthy ? 'operational' : 'unavailable'}`
      : isHealthy
        ? 'Operational'
        : 'Unavailable'

  return (
    <Card className="health-card">
      <div className="health-card-top">
        <span className="service-index">{index}</span>
        <span className="service-mark" aria-hidden="true">{mark}</span>
      </div>
      <div className="health-card-bottom">
        <div>
          <h2 className="service-name">{name}</h2>
          <p className="service-description">{description}</p>
        </div>
        <Badge variant={variant} role="status" aria-label={label}>{label}</Badge>
      </div>
    </Card>
  )
}

function serviceState(
  service: ServiceHealth | undefined,
  isLoading: boolean,
  isError: boolean,
): ServiceCardProps['status'] {
  if (isLoading) return 'unknown'
  if (!service) return 'unavailable'
  if (isError) return service.status === 'ok' ? 'last-known-healthy' : 'last-known-unavailable'
  return service.status === 'ok' ? 'healthy' : 'unavailable'
}

function LoadingServices() {
  return (
    <div className="health-grid" aria-label="Loading service status" role="status">
      {[0, 1, 2].map((item) => (
        <Card className="health-card" key={item}>
          <div className="health-card-top">
            <Skeleton style={{ width: '1.5rem', height: '0.75rem' }} />
            <Skeleton style={{ width: '2.125rem', height: '2.125rem' }} />
          </div>
          <div className="health-card-bottom">
            <div className="skeleton-copy">
              <Skeleton style={{ width: '7.5rem', height: '1rem' }} />
              <Skeleton style={{ width: '6.5rem', height: '0.75rem' }} />
            </div>
            <Skeleton style={{ width: '5.5rem', height: '1.5rem' }} />
          </div>
        </Card>
      ))}
    </div>
  )
}

function localTime(timestamp: number) {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(timestamp))
}

export function StatusPage() {
  const healthQuery = useHealth()
  const health = healthQuery.data
  const isLoading = healthQuery.isPending
  const isUnreachable = healthQuery.isError
  const isDegraded = Boolean(
    health && (health.status !== 'ok'
      || health.database.status !== 'ok'
      || health.redis.status !== 'ok'),
  )
  const apiStatus = isLoading
    ? 'unknown'
    : isUnreachable
      ? 'unavailable'
      : 'healthy'
  const databaseStatus = serviceState(health?.database, isLoading, isUnreachable)
  const redisStatus = serviceState(health?.redis, isLoading, isUnreachable)
  const healthyCount = Number(apiStatus === 'healthy')
    + Number(health?.database.status === 'ok')
    + Number(health?.redis.status === 'ok')
  const lastCheckedAt = isUnreachable
    ? healthQuery.errorUpdatedAt
    : healthQuery.dataUpdatedAt
  const hasCompletedCheck = lastCheckedAt > 0

  const statusHeading = isLoading
    ? 'Checking services'
    : isUnreachable
      ? 'Health service unreachable'
      : isDegraded
        ? 'Service degradation detected'
        : 'All services operational'
  const statusDescription = isLoading
    ? 'Connecting to the health service.'
    : isUnreachable
      ? 'The API could not be reached. Check the connection and try again.'
      : isDegraded
        ? 'The API is reachable, but one or more dependencies need attention.'
        : 'The API and its data services are responding normally.'
  return (
    <div className="status-page">
      <section className="status-intro" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">System overview</p>
          <h1 className="page-title" id="page-title">
            Platform <span>status</span>
          </h1>
          <p className="page-description">
            Current health of the services supporting this event.
          </p>
        </div>
        <Card className="overall-card" aria-live="polite">
          <span className="overall-mark" aria-hidden="true">
            {isLoading ? <Spinner size="sm" /> : isUnreachable || isDegraded ? '!' : '✓'}
          </span>
          <div className="overall-copy">
            <span className="overall-label">Platform status</span>
            <h2 className="overall-heading">{statusHeading}</h2>
            <p>{statusDescription}</p>
          </div>
        </Card>
      </section>

      <section className="status-section" aria-labelledby="services-title">
        <div className="section-header">
          <div>
            <p className="eyebrow">Infrastructure</p>
            <h2 className="section-title" id="services-title">Core services</h2>
          </div>
          <div className="section-tools">
            <span className="health-count" aria-live="polite">
              {isLoading ? 'Checking services' : `${healthyCount} / 3 healthy`}
            </span>
            <Button
              variant="secondary"
              loading={healthQuery.isFetching}
              disabled={healthQuery.isFetching}
              onClick={() => void healthQuery.refetch()}
              aria-label="Refresh health status"
            >
              Refresh
            </Button>
          </div>
        </div>

        {isLoading ? (
          <LoadingServices />
        ) : (
          <div className="health-grid" aria-label="Service health">
            <ServiceCard
              name="Backend API"
              description="Health endpoint"
              index="01"
              mark="API"
              status={apiStatus}
            />
            <ServiceCard
              name="PostgreSQL"
              description="Primary data store"
              index="02"
              mark="DB"
              status={databaseStatus}
            />
            <ServiceCard
              name="Redis"
              description="Cache service"
              index="03"
              mark="R"
              status={redisStatus}
            />
          </div>
        )}

        {isUnreachable && !health && (
          <div className="status-page-state">
            <EmptyState
              title="No health data available"
              description="The status endpoint did not respond. Retry when the backend is available."
              action={
                <Button
                  variant="primary"
                  loading={healthQuery.isFetching}
                  onClick={() => void healthQuery.refetch()}
                >
                  Try again
                </Button>
              }
            />
          </div>
        )}

        {health && hasCompletedCheck && (
          <p className="last-checked" aria-live="polite">
            Last checked at {localTime(lastCheckedAt)}
            {isUnreachable && ' · Showing last known dependency status'}
          </p>
        )}
        {isUnreachable && health && (
          <p className="status-message" role="status">
            The backend could not be reached on the latest check. Dependency statuses are last known.
          </p>
        )}
      </section>
    </div>
  )
}
