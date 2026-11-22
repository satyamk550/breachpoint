import { ApiError, apiGet, apiPost } from './client'

export type User = {
  id: string
  username: string
  email: string
  role: 'player' | 'admin'
  created_at: string
  last_login_at: string | null
}

export type LoginInput = { username: string; password: string }
export type RegisterInput = LoginInput & { email: string }

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await apiGet<User>('/auth/me', { redirectOnUnauthorized: false })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function login(input: LoginInput) {
  return apiPost<User>('/auth/login', input)
}

export function register(input: RegisterInput) {
  return apiPost<User>('/auth/register', input)
}

export function logout() {
  return apiPost<void>('/auth/logout')
}

export function changePassword(input: { current_password: string; new_password: string }) {
  return apiPost<void>('/auth/change-password', input)
}
