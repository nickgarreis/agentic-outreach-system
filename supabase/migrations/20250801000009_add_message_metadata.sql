-- supabase/migrations/20250801000009_add_message_metadata.sql
-- Adds metadata column to messages table for storing additional context
-- Used by OutreachAgent to track sequence numbers and scheduling information
-- RELEVANT FILES: 20250728063502_simplify_messages_table.sql, 20250801000008_add_lead_outreach_trigger.sql

-- Add metadata column to messages table
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb;

-- Add comment explaining usage
COMMENT ON COLUMN public.messages.metadata IS 'Flexible JSON storage for message-specific data like sequence numbers, scheduling info, and agent metadata';

-- Add subject column for email messages if not exists
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS subject text;

-- Add comment for subject
COMMENT ON COLUMN public.messages.subject IS 'Email subject line (null for non-email channels)';

-- Add message_type column for LinkedIn messages
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS message_type text;

-- Add comment for message_type
COMMENT ON COLUMN public.messages.message_type IS 'Type of message for channel-specific handling (e.g., connection_request, message for LinkedIn)';

-- Create index on metadata for common queries
CREATE INDEX IF NOT EXISTS idx_messages_metadata_sequence 
ON public.messages ((metadata->>'sequence_number')) 
WHERE metadata->>'sequence_number' IS NOT NULL;

-- Create index for scheduled messages by send_at
CREATE INDEX IF NOT EXISTS idx_messages_scheduled_send_at
ON public.messages (campaign_id, channel, send_at)
WHERE status = 'scheduled';