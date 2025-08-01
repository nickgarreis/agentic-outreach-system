-- supabase/migrations/20250801000014_add_message_status_validation.sql
-- Adds validation constraint for message status values
-- Ensures only valid status values can be set
-- RELEVANT FILES: 20250801000000_add_messages_table.sql, 20250801000011_add_email_sending_infrastructure.sql

-- First, let's check current status values in use
-- This is a safe operation that won't fail if there are invalid values
DO $$
BEGIN
    -- Log current distinct status values for audit
    RAISE NOTICE 'Current message status values in use: %', 
        (SELECT string_agg(DISTINCT status, ', ') FROM public.messages WHERE status IS NOT NULL);
END $$;

-- Define valid status values
-- These are all the statuses used throughout the codebase
CREATE TYPE message_status AS ENUM (
    'draft',          -- Message created but not scheduled
    'scheduled',      -- Scheduled for future sending
    'sent',          -- Successfully sent
    'delivered',     -- Confirmed delivered by provider
    'failed',        -- Send attempt failed
    'retry_pending', -- Failed but will be retried
    'bounced',       -- Email bounced
    'unsubscribed'   -- Recipient unsubscribed
);

-- Add comment explaining the statuses
COMMENT ON TYPE message_status IS 'Valid status values for messages with their lifecycle meanings';

-- Update the messages table to use the enum type
-- First, we need to handle any existing invalid values
UPDATE public.messages 
SET status = 'failed' 
WHERE status IS NOT NULL 
  AND status NOT IN ('draft', 'scheduled', 'sent', 'delivered', 'failed', 'retry_pending', 'bounced', 'unsubscribed');

-- Drop the existing default first (required for type conversion)
ALTER TABLE public.messages 
ALTER COLUMN status DROP DEFAULT;

-- Now alter the column to use the enum
-- This requires casting the existing text values
ALTER TABLE public.messages 
ALTER COLUMN status TYPE message_status 
USING status::message_status;

-- Add a default value for new messages
ALTER TABLE public.messages 
ALTER COLUMN status SET DEFAULT 'draft'::message_status;

-- Update column comment
COMMENT ON COLUMN public.messages.status IS 'Current status of the message in its lifecycle';

-- Create an index on status for performance
CREATE INDEX IF NOT EXISTS idx_messages_status 
ON public.messages(status) 
WHERE status IS NOT NULL;

-- Create a function to validate status transitions
-- This ensures status changes follow logical progression
CREATE OR REPLACE FUNCTION validate_message_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow any transition if old status is NULL or new status is NULL
    IF OLD.status IS NULL OR NEW.status IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Define valid transitions
    -- draft -> scheduled, sent (direct send)
    -- scheduled -> sent, failed, retry_pending
    -- sent -> delivered, bounced, failed
    -- delivered -> bounced (late bounce)
    -- failed -> retry_pending, failed (permanent)
    -- retry_pending -> sent, failed
    -- bounced -> (terminal state)
    -- unsubscribed -> (terminal state)
    
    -- Check if transition is valid
    CASE OLD.status
        WHEN 'draft' THEN
            IF NEW.status NOT IN ('scheduled', 'sent', 'failed') THEN
                RAISE EXCEPTION 'Invalid status transition from draft to %', NEW.status;
            END IF;
        WHEN 'scheduled' THEN
            IF NEW.status NOT IN ('sent', 'failed', 'retry_pending') THEN
                RAISE EXCEPTION 'Invalid status transition from scheduled to %', NEW.status;
            END IF;
        WHEN 'sent' THEN
            IF NEW.status NOT IN ('delivered', 'bounced', 'failed') THEN
                RAISE EXCEPTION 'Invalid status transition from sent to %', NEW.status;
            END IF;
        WHEN 'delivered' THEN
            IF NEW.status NOT IN ('bounced', 'unsubscribed') THEN
                RAISE EXCEPTION 'Invalid status transition from delivered to %', NEW.status;
            END IF;
        WHEN 'failed' THEN
            IF NEW.status NOT IN ('retry_pending', 'failed') THEN
                RAISE EXCEPTION 'Invalid status transition from failed to %', NEW.status;
            END IF;
        WHEN 'retry_pending' THEN
            IF NEW.status NOT IN ('sent', 'failed') THEN
                RAISE EXCEPTION 'Invalid status transition from retry_pending to %', NEW.status;
            END IF;
        WHEN 'bounced', 'unsubscribed' THEN
            -- Terminal states - no transitions allowed
            RAISE EXCEPTION 'Cannot transition from terminal status %', OLD.status;
    END CASE;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for status transition validation
CREATE TRIGGER validate_message_status_transition_trigger
BEFORE UPDATE OF status ON public.messages
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION validate_message_status_transition();

-- Add helpful comment
COMMENT ON FUNCTION validate_message_status_transition IS 'Ensures message status transitions follow valid lifecycle paths';

-- Create a view for message status statistics
CREATE OR REPLACE VIEW message_status_stats AS
SELECT 
    campaign_id,
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_seconds
FROM public.messages
GROUP BY campaign_id, status
ORDER BY campaign_id, status;

-- Grant permissions
GRANT SELECT ON message_status_stats TO authenticated;

-- Add helpful comment
COMMENT ON VIEW message_status_stats IS 'Aggregated statistics of message statuses by campaign';