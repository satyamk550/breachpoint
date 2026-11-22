import { createContext } from 'react'

export type ToastVariant = 'success' | 'warning' | 'danger' | 'info'

export type ToastInput = {
  title: string
  description?: string
  variant?: ToastVariant
}

export type ToastMessage = ToastInput & { id: number }
export type ToastContextValue = { showToast: (toast: ToastInput) => void }

export const ToastContext = createContext<ToastContextValue | null>(null)
