// types/index.ts
// Shared TypeScript types for the frontend application
// Matches the backend Pydantic schemas
// RELEVANT FILES: ../lib/api/*.ts

// Re-export API types
export type { Campaign, CreateCampaignRequest, UpdateCampaignRequest } from '@/lib/api/campaigns'
export type { UserProfile, LoginRequest, LoginResponse } from '@/lib/api/auth'

// Common types
export interface BaseResponse {
  success: boolean
  message?: string
  data?: any
}

export interface TimestampMixin {
  created_at: string
  updated_at?: string
}

// Enums
export enum CampaignStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  ARCHIVED = 'archived',
}

export enum ClientStatus {
  PROSPECT = 'prospect',
  CONTACTED = 'contacted',
  ENGAGED = 'engaged',
  CONVERTED = 'converted',
  LOST = 'lost',
}

export enum ClientRole {
  OWNER = 'owner',
  ADMIN = 'admin',
  USER = 'user',
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum MessageStatus {
  DRAFT = 'draft',
  SCHEDULED = 'scheduled',
  SENT = 'sent',
  DELIVERED = 'delivered',
  FAILED = 'failed',
  RETRY_PENDING = 'retry_pending',
  BOUNCED = 'bounced',
  UNSUBSCRIBED = 'unsubscribed',
}

// Client types
export interface Client extends TimestampMixin {
  id: string
  name: string
}

export interface ClientMember extends TimestampMixin {
  id: string
  client_id: string
  user_id: string
  role: ClientRole
  invited_by?: string
  invited_at?: string
  accepted_at?: string
  user_email?: string
  user_name?: string
  is_pending: boolean
  is_current_user: boolean
}

// Lead types
export interface Lead extends TimestampMixin {
  id: string
  campaign_id: string
  client_id?: string
  email?: string
  first_name?: string
  last_name?: string
  company?: string
  title?: string
  phone?: string
  status: 'enriched' | 'enrichment_failed'
  full_context?: any
}

// Message types
export interface Message extends TimestampMixin {
  id: string
  lead_id: string
  campaign_id: string
  channel: string
  direction: string
  content?: string
  subject?: string
  status: MessageStatus
  send_at?: string
  sent_at?: string
  metadata?: any
  message_type?: string
  thread_id?: string
  sendgrid_message_id?: string
}

// Job types
export interface Job extends TimestampMixin {
  id: string
  type: string
  status: JobStatus
  campaign_id: string
  client_id?: string
  payload: any
  result?: any
  error?: string
  started_at?: string
  completed_at?: string
}

// Chat types
export interface Conversation {
  id: string
  user_id?: string
  campaign_id?: string
  created_at: string
}

export interface ChatMessage {
  id: string
  conversation_id?: string
  role: 'user' | 'agent'
  content: string
  created_at?: string
}