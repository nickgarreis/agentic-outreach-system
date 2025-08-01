-- /supabase/migrations/20250801_add_campaign_outreach_config.sql
-- Add outreach configuration columns to campaigns table
-- This migration adds boolean flags for outreach channels, email footer config, and daily sending limits
-- RELEVANT FILES: supabase/migrations/20250728063428_simplify_campaigns_table.sql, src/database/models.py, src/api/campaigns.py

-- Add linkedin_outreach boolean column with default false
ALTER TABLE campaigns 
ADD COLUMN linkedin_outreach boolean NOT NULL DEFAULT false;

-- Add email_outreach boolean column with default false  
ALTER TABLE campaigns 
ADD COLUMN email_outreach boolean NOT NULL DEFAULT false;

-- Add email_footer jsonb column for flexible footer configuration
ALTER TABLE campaigns 
ADD COLUMN email_footer jsonb;

-- Add daily sending limit for email outreach
ALTER TABLE campaigns 
ADD COLUMN daily_sending_limit_email int4;

-- Add daily sending limit for LinkedIn outreach
ALTER TABLE campaigns 
ADD COLUMN daily_sending_limit_linkedin int4;

-- Add comments for clarity
COMMENT ON COLUMN campaigns.linkedin_outreach IS 'Enable/disable LinkedIn outreach for this campaign';
COMMENT ON COLUMN campaigns.email_outreach IS 'Enable/disable email outreach for this campaign';
COMMENT ON COLUMN campaigns.email_footer IS 'JSON configuration for email footer content (HTML, text, variables, etc.)';
COMMENT ON COLUMN campaigns.daily_sending_limit_email IS 'Maximum number of emails to send per day for this campaign';
COMMENT ON COLUMN campaigns.daily_sending_limit_linkedin IS 'Maximum number of LinkedIn messages to send per day for this campaign';