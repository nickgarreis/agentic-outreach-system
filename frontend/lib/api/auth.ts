// lib/api/auth.ts
// Authentication API functions
// Handles login, logout, token refresh, and user profile
// RELEVANT FILES: client.ts, ../../app/(auth)/login/page.tsx

import apiClient from './client'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: {
    id: string
    email: string
    created_at: string
    last_sign_in_at?: string
    metadata?: Record<string, any>
  }
}

export interface UserProfile {
  id: string
  email: string
  created_at: string
  last_sign_in_at?: string
  metadata?: Record<string, any>
}

export const authApi = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    return apiClient.post<LoginResponse>('/api/auth/login', credentials)
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/auth/logout')
    } finally {
      // Clear tokens regardless of API response
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  },

  async refreshToken(refreshToken: string): Promise<{
    access_token: string
    refresh_token: string
  }> {
    return apiClient.post('/api/auth/refresh', { refresh_token: refreshToken })
  },

  async getCurrentUser(): Promise<UserProfile> {
    return apiClient.get<UserProfile>('/api/auth/me')
  },

  async verifyToken(): Promise<{
    valid: boolean
    user_id: string
    email: string
    role: string
    expires_at: number
  }> {
    return apiClient.post('/api/auth/verify')
  },
}

export default authApi