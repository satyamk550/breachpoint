import * as DialogPrimitive from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'

export type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  trigger?: ReactNode
  children: ReactNode
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  children,
}: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ui-dialog-overlay" />
        <DialogPrimitive.Content className="ui-dialog-content">
          <DialogPrimitive.Title className="ui-dialog-title">{title}</DialogPrimitive.Title>
          {description && (
            <DialogPrimitive.Description className="ui-dialog-description">
              {description}
            </DialogPrimitive.Description>
          )}
          <div className="ui-dialog-body">{children}</div>
          <DialogPrimitive.Close className="ui-dialog-close" aria-label="Close dialog">
            <span aria-hidden="true">×</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
