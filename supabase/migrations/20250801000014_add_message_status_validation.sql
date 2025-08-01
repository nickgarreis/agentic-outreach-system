-- supabase/migrations/20250801000014_add_message_status_validation.sql
-- Adds validation constraint for message status values using enum type
-- Complete reset approach to handle all edge cases and partial states
-- RELEVANT FILES: 20250801000000_add_messages_table.sql, 20250801000011_add_email_sending_infrastructure.sql

-- Step 1: Clean up any partial migration state
DO $$
BEGIN
    -- Drop all dependent objects that might exist
    DROP VIEW IF EXISTS message_tracking_status CASCADE;
    DROP VIEW IF EXISTS message_status_stats CASCADE;
    DROP TRIGGER IF EXISTS validate_message_status_transition_trigger ON public.messages;
    DROP FUNCTION IF EXISTS validate_message_status_transition() CASCADE;
    
    -- Check if column is already using enum type
    IF EXISTS (
        SELECT 1 
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_type t ON a.atttypid = t.oid
        WHERE c.relname = 'messages'
        AND a.attname = 'status'
        AND t.typname = 'message_status'
    ) THEN
        -- Convert back to text to start fresh
        ALTER TABLE public.messages ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE public.messages ALTER COLUMN status TYPE text USING status::text;
        RAISE NOTICE 'Converted status column back to text for clean migration';
    END IF;
    
    -- Drop enum type and any casts if they exist
    DROP CAST IF EXISTS (varchar AS message_status);
    DROP CAST IF EXISTS (text AS message_status);
    DROP TYPE IF EXISTS message_status CASCADE;
    
    RAISE NOTICE 'Cleaned up any existing enum type and dependencies';
END$$;

-- Step 2: Update invalid values BEFORE creating enum (while column is still text)
UPDATE public.messages 
SET status = 'failed' 
WHERE status IS NOT NULL 
  AND status NOT IN ('draft', 'scheduled', 'sent', 'delivered', 'failed', 'retry_pending', 'bounced', 'unsubscribed');

-- Log what we're about to do
DO $$
DECLARE
    v_distinct_values text;
BEGIN
    SELECT string_agg(DISTINCT status, ', ' ORDER BY status) 
    INTO v_distinct_values
    FROM public.messages 
    WHERE status IS NOT NULL;
    
    RAISE NOTICE 'Current distinct status values: %', COALESCE(v_distinct_values, '(none)');
END$$;

-- Step 3: Create the enum type
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

COMMENT ON TYPE message_status IS 'Valid status values for messages with their lifecycle meanings';

-- Step 4: Convert the column to enum type
ALTER TABLE public.messages 
    ALTER COLUMN status DROP DEFAULT,
    ALTER COLUMN status TYPE message_status USING status::message_status,
    ALTER COLUMN status SET DEFAULT 'draft'::message_status;

COMMENT ON COLUMN public.messages.status IS 'Current status of the message in its lifecycle';

-- Step 5: Create index for performance
CREATE INDEX IF NOT EXISTS idx_messages_status 
ON public.messages(status) 
WHERE status IS NOT NULL;

-- Step 6: Create status transition validation function
CREATE OR REPLACE FUNCTION validate_message_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow any transition if old status is NULL or new status is NULL
    IF OLD.status IS NULL OR NEW.status IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Define valid transitions
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

COMMENT ON FUNCTION validate_message_status_transition IS 'Ensures message status transitions follow valid lifecycle paths';

-- Step 7: Create trigger for validation
CREATE TRIGGER validate_message_status_transition_trigger
BEFORE UPDATE OF status ON public.messages
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION validate_message_status_transition();

-- Step 8: Recreate the message tracking status view
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

GRANT SELECT ON message_tracking_status TO authenticated;

COMMENT ON VIEW message_tracking_status IS 'Email message tracking status with derived status from timestamps';

-- Step 9: Create status statistics view
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

GRANT SELECT ON message_status_stats TO authenticated;

COMMENT ON VIEW message_status_stats IS 'Aggregated statistics of message statuses by campaign';

-- Final success message
DO $$
BEGIN
    RAISE NOTICE 'Message status enum migration completed successfully';
    RAISE NOTICE 'Status column is now using enum type with validation';
END$$;