import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ToastContext, type ToastInput, type ToastMessage } from './toast-context'

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastMessage
  onDismiss: (id: number) => void
}) {
  useEffect(() => {
    const timerId = window.setTimeout(() => onDismiss(toast.id), 5000)
    return () => window.clearTimeout(timerId)
  }, [onDismiss, toast.id])

  const role = toast.variant === 'danger' ? 'alert' : 'status'
  return (
    <div className={`ui-toast ui-toast-${toast.variant ?? 'info'}`} role={role}>
      <div>
        <strong>{toast.title}</strong>
        {toast.description && <p>{toast.description}</p>}
      </div>
      <button
        className="ui-toast-dismiss"
        type="button"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(toast.id)}
      >
        ×
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((toast: ToastInput) => {
    nextId.current += 1
    setToasts((current) => [...current, { ...toast, id: nextId.current }])
  }, [])

  useEffect(() => {
    const onRateLimit = (event: Event) => {
      const detail = (event as CustomEvent<{ message?: string }>).detail
      showToast({
        title: 'Slow down',
        description: detail.message ?? 'Too many requests. Try again shortly.',
        variant: 'warning',
      })
    }
    window.addEventListener('api:rate-limit', onRateLimit)
    return () => window.removeEventListener('api:rate-limit', onRateLimit)
  }, [showToast])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="ui-toast-region" role="region" aria-label="Notifications">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
