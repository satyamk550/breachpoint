import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { getCurrentUser, logout as logoutRequest } from '../api/auth'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const userQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getCurrentUser,
    retry: false,
    staleTime: 30_000,
  })

  async function logout() {
    await logoutRequest()
    queryClient.setQueryData(['auth', 'me'], null)
  }

  const user = userQuery.data ?? null
  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading: userQuery.isPending,
        isAuthenticated: Boolean(user),
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
