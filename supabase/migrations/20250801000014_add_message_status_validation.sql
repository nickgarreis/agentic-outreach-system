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

-- Create enum type if it doesn't exist (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
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
    END IF;
END$$;

-- Create implicit cast from varchar to message_status for safer operations
-- This helps with compatibility when converting from text columns
DO $$
BEGIN
    -- Check if cast already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_cast 
        WHERE castsource = 'varchar'::regtype 
        AND casttarget = 'message_status'::regtype
    ) THEN
        CREATE CAST (varchar AS message_status) WITH INOUT AS IMPLICIT;
    END IF;
END$$;

-- Only proceed with column type change if status is still text type
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'messages' 
        AND column_name = 'status' 
        AND data_type = 'text'
    ) THEN
        -- Drop dependent views first
        DROP VIEW IF EXISTS message_tracking_status;
        
        -- Drop existing default
        EXECUTE 'ALTER TABLE public.messages ALTER COLUMN status DROP DEFAULT';
        
        -- Update any invalid values before conversion
        UPDATE public.messages 
        SET status = 'failed' 
        WHERE status IS NOT NULL 
          AND status NOT IN ('draft', 'scheduled', 'sent', 'delivered', 'failed', 'retry_pending', 'bounced', 'unsubscribed');
        
        -- Alter column with proper double casting (text -> text -> enum)
        EXECUTE 'ALTER TABLE public.messages ALTER COLUMN status TYPE message_status USING status::text::message_status';
        
        -- Set new default
        EXECUTE 'ALTER TABLE public.messages ALTER COLUMN status SET DEFAULT ''draft''::message_status';
        
        -- Update column comment
        COMMENT ON COLUMN public.messages.status IS 'Current status of the message in its lifecycle';
        
        -- Recreate the message_tracking_status view
        CREATE OR REPLACE VIEW message_tracking_status AS
        SELECT 
          m.id,
          m.campaign_id,
          m.lead_id,
          m.channel,
          m.status,
          m.send_at,
          m.sent_at,
          m.delivered_at,
          m.opened_at,
          m.clicked_at,
          m.bounced_at,
          m.unsubscribed_at,
          CASE 
            WHEN m.bounced_at IS NOT NULL THEN 'bounced'
            WHEN m.unsubscribed_at IS NOT NULL THEN 'unsubscribed'
            WHEN m.clicked_at IS NOT NULL THEN 'clicked'
            WHEN m.opened_at IS NOT NULL THEN 'opened'
            WHEN m.delivered_at IS NOT NULL THEN 'delivered'
            WHEN m.sent_at IS NOT NULL THEN 'sent'
            ELSE m.status::text
          END as tracking_status,
          jsonb_array_length(m.tracking_events) as event_count,
          m.tracking_events
        FROM public.messages m
        WHERE m.channel = 'email';
        
        -- Grant permissions
        GRANT SELECT ON message_tracking_status TO authenticated;
        
        RAISE NOTICE 'Successfully converted status column to enum type';
    ELSE
        RAISE NOTICE 'Status column is already using enum type or does not exist, skipping conversion';
    END IF;
END$$;

-- Create an index on status for performance (idempotent)
CREATE INDEX IF NOT EXISTS idx_messages_status 
ON public.messages(status) 
WHERE status IS NOT NULL;

-- Create a function to validate status transitions (idempotent)
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
    -- delivered -> bounced (late bounce), unsubscribed
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

-- Add trigger for status transition validation (idempotent)
DROP TRIGGER IF EXISTS validate_message_status_transition_trigger ON public.messages;
CREATE TRIGGER validate_message_status_transition_trigger
BEFORE UPDATE OF status ON public.messages
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION validate_message_status_transition();

-- Add helpful comments
COMMENT ON FUNCTION validate_message_status_transition IS 'Ensures message status transitions follow valid lifecycle paths';

-- Create a view for message status statistics (idempotent)
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

-- Final success message
DO $$
BEGIN
    RAISE NOTICE 'Message status validation migration completed successfully';
END$$;