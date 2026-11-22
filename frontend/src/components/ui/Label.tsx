import { forwardRef, type LabelHTMLAttributes } from 'react'

export type LabelProps = LabelHTMLAttributes<HTMLLabelElement>

export const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ className = '', ...props }, ref) => (
    <label ref={ref} className={`ui-label ${className}`.trim()} {...props} />
  ),
)

Label.displayName = 'Label'
