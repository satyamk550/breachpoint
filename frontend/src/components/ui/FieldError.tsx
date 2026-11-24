import type { HTMLAttributes } from 'react'

export type FieldErrorProps = HTMLAttributes<HTMLParagraphElement> & {
  id?: string
}

export function FieldError({ id, className = '', ...props }: FieldErrorProps) {
  return <p id={id} className={`ui-field-error ${className}`.trim()} role="alert" {...props} />
}
