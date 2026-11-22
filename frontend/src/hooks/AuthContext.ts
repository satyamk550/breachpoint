import { createContext, useContext } from 'react'
import type { User } from '../api/auth'

export type AuthContextValue = {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
