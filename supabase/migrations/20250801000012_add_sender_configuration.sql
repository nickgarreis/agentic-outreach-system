-- supabase/migrations/20250801000012_add_sender_configuration.sql
-- Adds configurable sender settings to campaigns table
-- Allows each campaign to have its own from_email and from_name
-- RELEVANT FILES: 20250801000011_add_email_sending_infrastructure.sql, 20250801000000_add_campaign_outreach_config.sql

-- Add sender configuration columns to campaigns table
ALTER TABLE public.campaigns 
ADD COLUMN IF NOT EXISTS from_email text,
ADD COLUMN IF NOT EXISTS from_name text;

-- Add comments for documentation
COMMENT ON COLUMN public.campaigns.from_email IS 'Sender email address for this campaign (must be verified in SendGrid)';
COMMENT ON COLUMN public.campaigns.from_name IS 'Sender display name for this campaign';

-- Add validation function for email format
CREATE OR REPLACE FUNCTION validate_sender_email()
RETURNS TRIGGER AS $$
BEGIN
  -- Validate email format if provided
  IF NEW.from_email IS NOT NULL AND NEW.from_email !~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN
    RAISE EXCEPTION 'Invalid sender email format: %', NEW.from_email;
  END IF;
  
  -- If email outreach is enabled, require sender email
  IF NEW.email_outreach = true AND NEW.from_email IS NULL THEN
    RAISE EXCEPTION 'Sender email (from_email) is required when email outreach is enabled';
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to validate sender email
CREATE TRIGGER validate_sender_email_on_update
BEFORE INSERT OR UPDATE OF from_email, email_outreach ON public.campaigns
FOR EACH ROW
EXECUTE FUNCTION validate_sender_email();

-- Add index for sender email lookups (useful for domain validation)
CREATE INDEX IF NOT EXISTS idx_campaigns_from_email 
ON public.campaigns(from_email) 
WHERE from_email IS NOT NULL;

-- Helper function to get campaign sender info with defaults
CREATE OR REPLACE FUNCTION get_campaign_sender_info(p_campaign_id uuid)
RETURNS TABLE (
  from_email text,
  from_name text,
  sendgrid_api_key text
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COALESCE(c.from_email, 'noreply@example.com') as from_email,
    COALESCE(c.from_name, cl.name) as from_name,
    c.sendgrid_api_key
  FROM public.campaigns c
  JOIN public.clients cl ON c.client_id = cl.id
  WHERE c.id = p_campaign_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_campaign_sender_info TO authenticated;

-- Add helpful comment
COMMENT ON FUNCTION get_campaign_sender_info IS 'Get campaign sender information with defaults (uses client name if from_name not set)';