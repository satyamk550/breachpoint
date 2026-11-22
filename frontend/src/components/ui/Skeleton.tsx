import type { HTMLAttributes } from 'react'

export type SkeletonProps = HTMLAttributes<HTMLSpanElement>

export function Skeleton({ className = '', ...props }: SkeletonProps) {
  return <span className={`ui-skeleton ${className}`.trim()} aria-hidden="true" {...props} />
}
