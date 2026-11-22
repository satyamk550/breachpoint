import { forwardRef, type HTMLAttributes } from 'react'

type CardPartProps = HTMLAttributes<HTMLDivElement>

export const Card = forwardRef<HTMLDivElement, CardPartProps>(
  ({ className = '', ...props }, ref) => (
    <div ref={ref} className={`ui-card ${className}`.trim()} {...props} />
  ),
)

Card.displayName = 'Card'

export function CardHeader({ className = '', ...props }: CardPartProps) {
  return <div className={`ui-card-header ${className}`.trim()} {...props} />
}

export function CardTitle({ className = '', ...props }: CardPartProps) {
  return <h2 className={`ui-card-title ${className}`.trim()} {...props} />
}

export function CardDescription({ className = '', ...props }: CardPartProps) {
  return <p className={`ui-card-description ${className}`.trim()} {...props} />
}

export function CardContent({ className = '', ...props }: CardPartProps) {
  return <div className={`ui-card-content ${className}`.trim()} {...props} />
}

export function CardFooter({ className = '', ...props }: CardPartProps) {
  return <div className={`ui-card-footer ${className}`.trim()} {...props} />
}
