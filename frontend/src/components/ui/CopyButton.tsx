import { useEffect, useState } from 'react'
import { Button, type ButtonProps } from './Button'
import { Tooltip } from './Tooltip'
import { useToast } from './useToast'

export type CopyButtonProps = Omit<ButtonProps, 'children' | 'onClick'> & {
  value: string
  label?: string
}

export function CopyButton({
  value,
  label = 'Copy to clipboard',
  ...buttonProps
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const { showToast } = useToast()

  useEffect(() => {
    if (!copied) return
    const timerId = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(timerId)
  }, [copied])

  async function copyValue() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      showToast({ title: 'Copied to clipboard', variant: 'success' })
    } catch {
      showToast({
        title: 'Copy failed',
        description: 'Clipboard access is unavailable in this browser.',
        variant: 'danger',
      })
    }
  }

  return (
    <Tooltip content={copied ? 'Copied' : label}>
      <Button
        {...buttonProps}
        variant={buttonProps.variant ?? 'ghost'}
        type="button"
        aria-label={copied ? 'Copied to clipboard' : label}
        onClick={() => void copyValue()}
      >
        <span aria-hidden="true">{copied ? '✓' : '⧉'}</span>
      </Button>
    </Tooltip>
  )
}
