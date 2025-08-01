-- Add phone number requirement setting and lead discovery metrics to campaigns table
-- This migration adds support for conditional phone number enrichment and tracking total leads discovered

-- Add new columns to campaigns table
ALTER TABLE public.campaigns
ADD COLUMN require_phone_number BOOLEAN DEFAULT FALSE,
ADD COLUMN total_leads_discovered INTEGER DEFAULT 0;

-- Add helpful comments
COMMENT ON COLUMN public.campaigns.require_phone_number IS 'Whether to reveal phone numbers during lead enrichment (costs more credits)';
COMMENT ON COLUMN public.campaigns.total_leads_discovered IS 'Total number of leads discovered through all searches';

-- Function to increment lead counter atomically
CREATE OR REPLACE FUNCTION increment_campaign_leads(campaign_uuid UUID, increment_by INT)
RETURNS VOID AS $$
BEGIN
    UPDATE campaigns 
    SET total_leads_discovered = COALESCE(total_leads_discovered, 0) + increment_by
    WHERE id = campaign_uuid;
END;
$$ LANGUAGE plpgsql;

-- Add comment for the function
COMMENT ON FUNCTION increment_campaign_leads IS 'Atomically increment the total_leads_discovered counter for a campaign';