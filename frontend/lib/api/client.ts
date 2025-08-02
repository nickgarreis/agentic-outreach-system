// lib/api/client.ts
// Base API client for communicating with FastAPI backend
// Handles authentication, token refresh, and error handling
// RELEVANT FILES: auth.ts, campaigns.ts, leads.ts

interface ApiConfig {
  baseUrl: string
  getAccessToken?: () => string | null
  onTokenRefresh?: (tokens: { access_token: string; refresh_token: string }) => void
}

class ApiClient {
  private baseUrl: string
  private getAccessToken?: () => string | null
  private onTokenRefresh?: (tokens: { access_token: string; refresh_token: string }) => void

  constructor(config: ApiConfig) {
    this.baseUrl = config.baseUrl
    this.getAccessToken = config.getAccessToken
    this.onTokenRefresh = config.onTokenRefresh
  }

  private async refreshAccessToken(): Promise<string | null> {
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) return null

      const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!response.ok) {
        throw new Error('Token refresh failed')
      }

      const data = await response.json()
      
      // Store new tokens
      if (this.onTokenRefresh) {
        this.onTokenRefresh(data)
      } else {
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
      }

      return data.access_token
    } catch (error) {
      console.error('Token refresh error:', error)
      // Clear tokens on refresh failure
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
      return null
    }
  }

  async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const accessToken = this.getAccessToken
      ? this.getAccessToken()
      : localStorage.getItem('access_token')

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }

    let response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    })

    // If unauthorized, try to refresh token and retry
    if (response.status === 401 && accessToken) {
      const newToken = await this.refreshAccessToken()
      if (newToken) {
        headers['Authorization'] = `Bearer ${newToken}`
        response = await fetch(`${this.baseUrl}${endpoint}`, {
          ...options,
          headers,
        })
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Request failed: ${response.statusText}`)
    }

    // Handle empty responses
    const text = await response.text()
    return text ? JSON.parse(text) : null as T
  }

  // Convenience methods
  get<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' })
  }

  post<T = any>(endpoint: string, data?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  put<T = any>(endpoint: string, data?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  delete<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' })
  }
}

// Create singleton instance
export const apiClient = new ApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
})

export default apiClient