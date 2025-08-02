-- supabase/migrations/20250801000018_remove_sendgrid_validation_trigger.sql
-- Removes SendGrid API key validation trigger to allow more flexible key formats
-- Validation can be handled at application layer if needed
-- RELEVANT FILES: 20250801000011_add_email_sending_infrastructure.sql

-- Drop the trigger first
DROP TRIGGER IF EXISTS validate_sendgrid_key_on_update ON public.campaigns;

-- Drop the function
DROP FUNCTION IF EXISTS public.validate_sendgrid_api_key();

-- Add comment explaining the removal
COMMENT ON COLUMN public.campaigns.sendgrid_api_key IS 'SendGrid API key for sending emails - format validation handled by application';