-- supabase/migrations/20250801000011_add_email_sending_infrastructure.sql
-- Adds SendGrid integration and email tracking infrastructure
-- Enables campaigns to send emails via SendGrid with proper tracking
-- RELEVANT FILES: 20250801000009_add_message_metadata.sql, 20250728063502_simplify_messages_table.sql

-- Add SendGrid API key to campaigns table
ALTER TABLE public.campaigns 
ADD COLUMN IF NOT EXISTS sendgrid_api_key text;

COMMENT ON COLUMN public.campaigns.sendgrid_api_key IS 'SendGrid API key for sending emails from this campaign';

-- Add email tracking columns to messages table
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS send_attempts integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_send_attempt_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS send_error text,
ADD COLUMN IF NOT EXISTS sendgrid_message_id text,
ADD COLUMN IF NOT EXISTS job_id uuid;

-- Add comments for documentation
COMMENT ON COLUMN public.messages.send_attempts IS 'Number of times email send was attempted';
COMMENT ON COLUMN public.messages.last_send_attempt_at IS 'Timestamp of the last send attempt';
COMMENT ON COLUMN public.messages.send_error IS 'Error message from last failed send attempt';
COMMENT ON COLUMN public.messages.sendgrid_message_id IS 'SendGrid message ID for tracking';
COMMENT ON COLUMN public.messages.job_id IS 'Reference to the job that will send this message';

-- Create index for efficient querying of messages by send time and status
CREATE INDEX IF NOT EXISTS idx_messages_send_at_status_channel 
ON public.messages(send_at, status, channel) 
WHERE status = 'scheduled' AND channel = 'email';

-- Create index for job_id lookups
CREATE INDEX IF NOT EXISTS idx_messages_job_id 
ON public.messages(job_id) 
WHERE job_id IS NOT NULL;

-- Add RLS policy for campaigns.sendgrid_api_key
-- Only users who are members of the client can see the API key
CREATE POLICY "Users can view sendgrid_api_key for their campaigns"
ON public.campaigns
FOR SELECT
USING (
  client_id IN (
    SELECT cm.client_id 
    FROM public.client_members cm 
    WHERE cm.user_id = auth.uid() 
    AND cm.accepted_at IS NOT NULL
  )
);

-- Function to validate SendGrid API key format (optional)
CREATE OR REPLACE FUNCTION validate_sendgrid_api_key()
RETURNS TRIGGER AS $$
BEGIN
  -- SendGrid API keys start with 'SG.'
  IF NEW.sendgrid_api_key IS NOT NULL AND NOT NEW.sendgrid_api_key LIKE 'SG.%' THEN
    RAISE EXCEPTION 'Invalid SendGrid API key format. Keys must start with SG.';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to validate SendGrid API key format
CREATE TRIGGER validate_sendgrid_key_on_update
BEFORE INSERT OR UPDATE OF sendgrid_api_key ON public.campaigns
FOR EACH ROW
EXECUTE FUNCTION validate_sendgrid_api_key();

-- Helper function to get messages ready for sending
-- This is useful for debugging and monitoring
CREATE OR REPLACE FUNCTION get_due_email_messages(
  p_campaign_id uuid DEFAULT NULL,
  p_limit integer DEFAULT 100
)
RETURNS TABLE (
  id uuid,
  campaign_id uuid,
  lead_id uuid,
  subject text,
  content text,
  send_at timestamp with time zone,
  send_attempts integer,
  job_id uuid
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    m.id,
    m.campaign_id,
    m.lead_id,
    m.subject,
    m.content,
    m.send_at,
    m.send_attempts,
    m.job_id
  FROM public.messages m
  WHERE m.channel = 'email'
    AND m.status = 'scheduled'
    AND m.send_at <= NOW()
    AND (p_campaign_id IS NULL OR m.campaign_id = p_campaign_id)
  ORDER BY m.send_at ASC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_due_email_messages TO authenticated;

-- Add helpful comment
COMMENT ON FUNCTION get_due_email_messages IS 'Helper function to retrieve email messages that are due to be sent';