-- supabase/migrations/20250801000008_add_lead_outreach_trigger.sql
-- Creates trigger to automatically create outreach jobs when lead status changes to 'researched'
-- This enables the OutreachAgent to craft and schedule personalized messages
-- RELEVANT FILES: 20250801000007_add_lead_research_trigger.sql, 20250130_create_jobs_table.sql

-- Function to handle lead status change to 'researched'
CREATE OR REPLACE FUNCTION handle_lead_outreach_trigger()
RETURNS TRIGGER AS $$
DECLARE
  existing_job_count INT;
  campaign_rec RECORD;
BEGIN
  -- Only proceed if the status changed TO 'researched'
  -- Check both that new status is 'researched' and old status was different
  IF NEW.status = 'researched' AND 
     (OLD.status IS NULL OR OLD.status != 'researched') THEN
    
    -- Check if we already have a pending or processing outreach job for this lead
    -- This prevents duplicate job creation
    SELECT COUNT(*) INTO existing_job_count
    FROM jobs 
    WHERE job_type = 'lead_outreach'
      AND data->>'lead_id' = NEW.id::text
      AND status IN ('pending', 'processing');
    
    -- If job already exists, skip creation
    IF existing_job_count > 0 THEN
      RAISE NOTICE 'Outreach job already exists for lead %', NEW.id;
      RETURN NEW;
    END IF;
    
    -- Get campaign information for context
    SELECT 
      id,
      name,
      email_outreach,
      linkedin_outreach,
      daily_sending_limit_email,
      daily_sending_limit_linkedin
    INTO campaign_rec
    FROM campaigns 
    WHERE id = NEW.campaign_id;
    
    -- Only create job if campaign has at least one outreach channel enabled
    IF campaign_rec.email_outreach = true OR campaign_rec.linkedin_outreach = true THEN
      -- Create the outreach job
      INSERT INTO public.jobs (
        job_type,
        data,
        priority,
        status,
        created_at,
        updated_at
      ) VALUES (
        'lead_outreach',
        jsonb_build_object(
          'lead_id', NEW.id,
          'campaign_id', NEW.campaign_id,
          'campaign_name', campaign_rec.name,
          'lead_name', CONCAT(NEW.first_name, ' ', NEW.last_name),
          'company', NEW.company,
          'email', NEW.email,
          'enabled_channels', jsonb_build_object(
            'email', campaign_rec.email_outreach,
            'linkedin', campaign_rec.linkedin_outreach
          ),
          'daily_limits', jsonb_build_object(
            'email', campaign_rec.daily_sending_limit_email,
            'linkedin', campaign_rec.daily_sending_limit_linkedin
          ),
          'triggered_by', 'lead_outreach_trigger',
          'triggered_at', NOW()
        ),
        'high', -- High priority to ensure timely outreach
        'pending',
        NOW(),
        NOW()
      );
      
      RAISE NOTICE 'Created lead_outreach job for lead % in campaign %', 
        NEW.id, campaign_rec.name;
    ELSE
      RAISE NOTICE 'No outreach channels enabled for campaign %, skipping job creation', 
        campaign_rec.name;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger that fires when lead status changes
-- Using AFTER UPDATE to ensure the status change is committed
CREATE TRIGGER lead_outreach_trigger
AFTER UPDATE OF status ON public.leads
FOR EACH ROW
EXECUTE FUNCTION handle_lead_outreach_trigger();

-- Also create trigger for new leads that are created with 'researched' status
-- This handles edge cases where leads might be imported already researched
CREATE TRIGGER lead_outreach_on_insert_trigger
AFTER INSERT ON public.leads
FOR EACH ROW
EXECUTE FUNCTION handle_lead_outreach_trigger();

-- Add helpful comments
COMMENT ON FUNCTION handle_lead_outreach_trigger IS 'Creates lead_outreach jobs when leads reach researched status, enabling automated personalized outreach';
COMMENT ON TRIGGER lead_outreach_trigger ON public.leads IS 'Monitors lead status changes and triggers outreach job creation when status becomes researched';
COMMENT ON TRIGGER lead_outreach_on_insert_trigger ON public.leads IS 'Handles cases where leads are created with researched status';

-- Add index to improve job query performance
CREATE INDEX IF NOT EXISTS idx_jobs_lead_outreach 
ON public.jobs ((data->>'lead_id')) 
WHERE job_type = 'lead_outreach';