-- supabase/migrations/20250801000013_add_inline_tracking_data.sql
-- Adds inline tracking columns to messages and campaigns tables
-- Stores email event tracking data directly in the tables instead of separate table
-- RELEVANT FILES: 20250801000011_add_email_sending_infrastructure.sql, 20250801000012_add_sender_configuration.sql

-- Add tracking timestamp columns to messages table
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS delivered_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS opened_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS clicked_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS bounced_at timestamp with time zone,
ADD COLUMN IF NOT EXISTS unsubscribed_at timestamp with time zone;

-- Add tracking events JSONB column for detailed event history
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS tracking_events jsonb DEFAULT '[]'::jsonb;

-- Add comments for documentation
COMMENT ON COLUMN public.messages.delivered_at IS 'Timestamp when the email was delivered to recipient';
COMMENT ON COLUMN public.messages.opened_at IS 'Timestamp when the email was first opened';
COMMENT ON COLUMN public.messages.clicked_at IS 'Timestamp when a link in the email was first clicked';
COMMENT ON COLUMN public.messages.bounced_at IS 'Timestamp when the email bounced';
COMMENT ON COLUMN public.messages.unsubscribed_at IS 'Timestamp when recipient unsubscribed';
COMMENT ON COLUMN public.messages.tracking_events IS 'Array of all tracking events with details (event type, timestamp, metadata)';

-- Add email_metrics JSONB column to campaigns table for aggregated metrics
ALTER TABLE public.campaigns
ADD COLUMN IF NOT EXISTS email_metrics jsonb DEFAULT '{
  "sent": 0,
  "delivered": 0,
  "opened": 0,
  "clicked": 0,
  "bounced": 0,
  "unsubscribed": 0,
  "spam_reports": 0,
  "unique_opens": 0,
  "unique_clicks": 0,
  "open_rate": 0,
  "click_rate": 0,
  "bounce_rate": 0,
  "unsubscribe_rate": 0,
  "last_updated": null
}'::jsonb;

COMMENT ON COLUMN public.campaigns.email_metrics IS 'Aggregated email performance metrics for the campaign';

-- Create indexes for tracking timestamp queries
CREATE INDEX IF NOT EXISTS idx_messages_delivered_at ON public.messages(delivered_at) WHERE delivered_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_opened_at ON public.messages(opened_at) WHERE opened_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_clicked_at ON public.messages(clicked_at) WHERE clicked_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_bounced_at ON public.messages(bounced_at) WHERE bounced_at IS NOT NULL;

-- Create GIN index for JSONB tracking events queries
CREATE INDEX IF NOT EXISTS idx_messages_tracking_events ON public.messages USING GIN (tracking_events);
CREATE INDEX IF NOT EXISTS idx_campaigns_email_metrics ON public.campaigns USING GIN (email_metrics);

-- Helper function to append tracking event to a message
CREATE OR REPLACE FUNCTION append_tracking_event(
  p_message_id uuid,
  p_event jsonb
) RETURNS void AS $$
BEGIN
  UPDATE public.messages
  SET tracking_events = tracking_events || jsonb_build_array(p_event)
  WHERE id = p_message_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function to update campaign email metrics atomically
CREATE OR REPLACE FUNCTION update_campaign_email_metrics(
  p_campaign_id uuid,
  p_metric_name text,
  p_increment integer DEFAULT 1
) RETURNS void AS $$
DECLARE
  current_metrics jsonb;
  updated_metrics jsonb;
  sent_count integer;
  delivered_count integer;
BEGIN
  -- Get current metrics
  SELECT email_metrics INTO current_metrics
  FROM public.campaigns
  WHERE id = p_campaign_id;
  
  -- Update the specific metric
  updated_metrics := jsonb_set(
    current_metrics,
    array[p_metric_name],
    to_jsonb(COALESCE((current_metrics->p_metric_name)::integer, 0) + p_increment)
  );
  
  -- Update last_updated timestamp
  updated_metrics := jsonb_set(
    updated_metrics,
    array['last_updated'],
    to_jsonb(now())
  );
  
  -- Recalculate rates if needed
  IF p_metric_name IN ('delivered', 'opened', 'clicked', 'bounced', 'unsubscribed') THEN
    sent_count := COALESCE((updated_metrics->>'sent')::integer, 0);
    delivered_count := COALESCE((updated_metrics->>'delivered')::integer, 0);
    
    -- Calculate rates based on delivered emails (more accurate than sent)
    IF delivered_count > 0 THEN
      -- Open rate
      updated_metrics := jsonb_set(
        updated_metrics,
        array['open_rate'],
        to_jsonb(round((COALESCE((updated_metrics->>'opened')::integer, 0)::numeric / delivered_count::numeric) * 100, 2))
      );
      
      -- Click rate
      updated_metrics := jsonb_set(
        updated_metrics,
        array['click_rate'],
        to_jsonb(round((COALESCE((updated_metrics->>'clicked')::integer, 0)::numeric / delivered_count::numeric) * 100, 2))
      );
      
      -- Bounce rate (based on sent, not delivered)
      IF sent_count > 0 THEN
        updated_metrics := jsonb_set(
          updated_metrics,
          array['bounce_rate'],
          to_jsonb(round((COALESCE((updated_metrics->>'bounced')::integer, 0)::numeric / sent_count::numeric) * 100, 2))
        );
      END IF;
      
      -- Unsubscribe rate
      updated_metrics := jsonb_set(
        updated_metrics,
        array['unsubscribe_rate'],
        to_jsonb(round((COALESCE((updated_metrics->>'unsubscribed')::integer, 0)::numeric / delivered_count::numeric) * 100, 2))
      );
    END IF;
  END IF;
  
  -- Update the campaign
  UPDATE public.campaigns
  SET email_metrics = updated_metrics
  WHERE id = p_campaign_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION append_tracking_event TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION update_campaign_email_metrics TO authenticated, service_role;

-- Create view for easy access to message tracking status
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
    ELSE m.status
  END as tracking_status,
  jsonb_array_length(m.tracking_events) as event_count,
  m.tracking_events
FROM public.messages m
WHERE m.channel = 'email';

-- Grant access to the view
GRANT SELECT ON message_tracking_status TO authenticated;

-- Create RLS policies for the new columns
-- Messages tracking data should follow existing message RLS policies
-- (no additional policies needed as column access follows row access)

-- Add helpful comments
COMMENT ON FUNCTION append_tracking_event IS 'Append a tracking event to a message tracking_events array';
COMMENT ON FUNCTION update_campaign_email_metrics IS 'Atomically update campaign email metrics and recalculate rates';
COMMENT ON VIEW message_tracking_status IS 'Consolidated view of email message tracking status';