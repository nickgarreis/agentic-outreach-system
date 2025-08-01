-- Create trigger to automatically research leads when campaigns need more messages
-- This ensures campaigns can reach their daily sending limits by researching enriched leads

-- Function to check if we should create lead research jobs
CREATE OR REPLACE FUNCTION should_create_lead_research_jobs(campaign_uuid UUID)
RETURNS TABLE(
  needs_research BOOLEAN,
  message_gap INTEGER,
  enriched_leads_count INTEGER
) AS $$
DECLARE
  campaign_rec RECORD;
  scheduled_today_count INT;
  enriched_without_research_count INT;
  daily_limit INT;
  messages_needed INT;
  last_job_time TIMESTAMP;
BEGIN
  -- Get campaign details
  SELECT 
    status,
    daily_sending_limit_email,
    daily_sending_limit_linkedin,
    email_outreach,
    linkedin_outreach
  INTO campaign_rec
  FROM campaigns 
  WHERE id = campaign_uuid;
  
  -- Check if campaign is active
  IF campaign_rec.status != 'active' THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 0::INTEGER, 0::INTEGER;
    RETURN;
  END IF;
  
  -- Calculate total daily limit
  daily_limit := 0;
  IF campaign_rec.email_outreach AND campaign_rec.daily_sending_limit_email IS NOT NULL THEN
    daily_limit := daily_limit + campaign_rec.daily_sending_limit_email;
  END IF;
  IF campaign_rec.linkedin_outreach AND campaign_rec.daily_sending_limit_linkedin IS NOT NULL THEN
    daily_limit := daily_limit + campaign_rec.daily_sending_limit_linkedin;
  END IF;
  
  -- If no daily limits set, nothing to do
  IF daily_limit = 0 THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 0::INTEGER, 0::INTEGER;
    RETURN;
  END IF;
  
  -- Count messages scheduled for today
  SELECT COUNT(*) INTO scheduled_today_count
  FROM messages 
  WHERE campaign_id = campaign_uuid 
    AND status = 'scheduled'
    AND DATE(send_at) = CURRENT_DATE;
  
  -- Calculate how many more messages we need
  messages_needed := daily_limit - scheduled_today_count;
  
  -- If we have enough messages scheduled, no need for research
  IF messages_needed <= 0 THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 0::INTEGER, 0::INTEGER;
    RETURN;
  END IF;
  
  -- Count enriched leads that haven't been researched yet
  SELECT COUNT(*) INTO enriched_without_research_count
  FROM leads 
  WHERE campaign_id = campaign_uuid 
    AND status = 'enriched';  -- Not yet researched
  
  -- Check for recent research jobs to implement cooldown (1 hour)
  SELECT MAX(created_at) INTO last_job_time
  FROM jobs 
  WHERE job_type = 'lead_research'
    AND data->>'campaign_id' = campaign_uuid::text
    AND created_at > NOW() - INTERVAL '1 hour';
  
  -- If we have a recent job, respect the cooldown
  IF last_job_time IS NOT NULL THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, messages_needed::INTEGER, enriched_without_research_count::INTEGER;
    RETURN;
  END IF;
  
  -- Return true if we have enriched leads to research and need more messages
  RETURN QUERY SELECT 
    (enriched_without_research_count > 0 AND messages_needed > 0)::BOOLEAN,
    messages_needed::INTEGER,
    enriched_without_research_count::INTEGER;
END;
$$ LANGUAGE plpgsql;

-- Function to handle lead research trigger
CREATE OR REPLACE FUNCTION handle_lead_research_trigger()
RETURNS TRIGGER AS $$
DECLARE
  campaign_cursor CURSOR FOR 
    SELECT DISTINCT c.id, c.name
    FROM campaigns c
    WHERE c.status = 'active'
      AND (c.daily_sending_limit_email > 0 OR c.daily_sending_limit_linkedin > 0);
  
  campaign_rec RECORD;
  research_check RECORD;
  leads_to_research RECORD;
  jobs_created INT := 0;
  max_jobs_per_trigger INT := 10;  -- Limit jobs per trigger execution
BEGIN
  -- Loop through all active campaigns with daily limits
  FOR campaign_rec IN campaign_cursor LOOP
    -- Check if this campaign needs research
    SELECT * INTO research_check
    FROM should_create_lead_research_jobs(campaign_rec.id);
    
    IF research_check.needs_research THEN
      -- Get enriched leads that need research (limit by message gap)
      FOR leads_to_research IN
        SELECT id, first_name, last_name, company
        FROM leads
        WHERE campaign_id = campaign_rec.id
          AND status = 'enriched'
        ORDER BY created_at DESC  -- Prioritize newer leads
        LIMIT LEAST(research_check.message_gap, max_jobs_per_trigger - jobs_created)
      LOOP
        -- Create a job for each lead
        INSERT INTO public.jobs (
          job_type,
          data,
          priority,
          status,
          created_at,
          updated_at
        ) VALUES (
          'lead_research',
          jsonb_build_object(
            'lead_id', leads_to_research.id,
            'campaign_id', campaign_rec.id,
            'campaign_name', campaign_rec.name,
            'lead_name', CONCAT(leads_to_research.first_name, ' ', leads_to_research.last_name),
            'company', leads_to_research.company,
            'triggered_by', 'lead_research_trigger'
          ),
          'normal',
          'pending',
          NOW(),
          NOW()
        );
        
        jobs_created := jobs_created + 1;
        
        -- Stop if we've created enough jobs
        IF jobs_created >= max_jobs_per_trigger THEN
          EXIT;
        END IF;
      END LOOP;
      
      IF jobs_created > 0 THEN
        RAISE NOTICE 'Created % lead_research jobs for campaign %', jobs_created, campaign_rec.name;
      END IF;
      
      -- Stop processing other campaigns if we've hit the limit
      IF jobs_created >= max_jobs_per_trigger THEN
        EXIT;
      END IF;
    END IF;
  END LOOP;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger that fires periodically to check for research needs
-- We'll trigger on messages table changes since that affects the daily count
CREATE TRIGGER lead_research_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.messages
FOR EACH STATEMENT
EXECUTE FUNCTION handle_lead_research_trigger();

-- Also trigger when leads status changes
CREATE TRIGGER lead_research_on_lead_change_trigger
AFTER UPDATE OF status ON public.leads
FOR EACH STATEMENT
EXECUTE FUNCTION handle_lead_research_trigger();

-- Add helpful comments
COMMENT ON FUNCTION should_create_lead_research_jobs IS 'Checks if a campaign needs lead research based on daily sending limits and scheduled messages';
COMMENT ON FUNCTION handle_lead_research_trigger IS 'Creates lead_research jobs when campaigns need more messages to reach daily limits';
COMMENT ON TRIGGER lead_research_trigger ON public.messages IS 'Monitors message changes and triggers lead research when daily limits aren\'t met';
COMMENT ON TRIGGER lead_research_on_lead_change_trigger ON public.leads IS 'Monitors lead status changes and triggers research for newly enriched leads';