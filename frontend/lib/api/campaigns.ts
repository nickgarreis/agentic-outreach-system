// lib/api/campaigns.ts
// Campaign API functions
// Handles CRUD operations for campaigns
// RELEVANT FILES: client.ts, leads.ts

import apiClient from './client'

export interface Campaign {
  id: string
  client_id: string
  name: string
  status: 'draft' | 'active' | 'paused' | 'completed' | 'archived'
  created_at: string
  linkedin_outreach: boolean
  email_outreach: boolean
  email_footer?: any
  daily_sending_limit_email?: number
  daily_sending_limit_linkedin?: number
  search_url?: any
  require_phone_number?: boolean
  total_leads_discovered?: number
  sendgrid_api_key?: string
  from_email?: string
  from_name?: string
  email_metrics?: any
  reply_to_domain?: string
}

export interface CreateCampaignRequest {
  name: string
  client_id: string
  status?: 'draft' | 'active' | 'paused' | 'completed' | 'archived'
  linkedin_outreach?: boolean
  email_outreach?: boolean
  daily_sending_limit_email?: number
  daily_sending_limit_linkedin?: number
}

export interface UpdateCampaignRequest extends Partial<CreateCampaignRequest> {
  email_footer?: any
  search_url?: any
  require_phone_number?: boolean
  sendgrid_api_key?: string
  from_email?: string
  from_name?: string
  reply_to_domain?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export const campaignsApi = {
  async list(params?: {
    offset?: number
    limit?: number
    status?: string
    client_id?: string
  }): Promise<PaginatedResponse<Campaign>> {
    const queryParams = new URLSearchParams()
    if (params?.offset) queryParams.append('offset', params.offset.toString())
    if (params?.limit) queryParams.append('limit', params.limit.toString())
    if (params?.status) queryParams.append('status', params.status)
    if (params?.client_id) queryParams.append('client_id', params.client_id)
    
    return apiClient.get(`/api/campaigns?${queryParams}`)
  },

  async get(id: string): Promise<Campaign> {
    return apiClient.get(`/api/campaigns/${id}`)
  },

  async create(data: CreateCampaignRequest): Promise<Campaign> {
    return apiClient.post('/api/campaigns', data)
  },

  async update(id: string, data: UpdateCampaignRequest): Promise<Campaign> {
    return apiClient.put(`/api/campaigns/${id}`, data)
  },

  async delete(id: string): Promise<void> {
    return apiClient.delete(`/api/campaigns/${id}`)
  },

  async getMetrics(id: string): Promise<any> {
    return apiClient.get(`/api/campaigns/${id}/metrics`)
  },
}

export default campaignsApi