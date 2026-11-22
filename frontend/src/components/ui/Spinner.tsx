import type { HTMLAttributes } from 'react'

export type SpinnerProps = HTMLAttributes<HTMLSpanElement> & {
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

export function Spinner({ label, size = 'md', className = '', ...props }: SpinnerProps) {
  return (
    <span
      className={`ui-spinner ui-spinner-${size} ${className}`.trim()}
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      {...props}
    />
  )
}
