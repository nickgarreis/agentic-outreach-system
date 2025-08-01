-- Create trigger to automatically create jobs when enriched leads fall below threshold
-- This ensures campaigns always have sufficient enriched leads for outreach

-- Function to check if we should create an enrichment job
CREATE OR REPLACE FUNCTION should_create_enrichment_job(campaign_uuid UUID)
RETURNS BOOLEAN AS $$
DECLARE
  campaign_status TEXT;
  enriched_count INT;
  recent_job_exists BOOLEAN;
BEGIN
  -- First check if campaign is active
  SELECT status INTO campaign_status
  FROM campaigns 
  WHERE id = campaign_uuid;
  
  IF campaign_status != 'active' THEN
    RETURN FALSE;
  END IF;
  
  -- Count enriched leads
  SELECT COUNT(*) INTO enriched_count
  FROM leads 
  WHERE campaign_id = campaign_uuid 
    AND status = 'enriched';
  
  -- Check for recent jobs to prevent spam
  SELECT EXISTS(
    SELECT 1 FROM jobs 
    WHERE job_type = 'campaign_active'
      AND data->>'campaign_id' = campaign_uuid::text
      AND status IN ('pending', 'processing')
      AND created_at > NOW() - INTERVAL '5 minutes'
  ) INTO recent_job_exists;
  
  -- Return true if enriched count is low and no recent job exists
  RETURN enriched_count < 5 AND NOT recent_job_exists;
END;
$$ LANGUAGE plpgsql;

-- Function to handle low enriched leads (nearly identical to campaign activation)
CREATE OR REPLACE FUNCTION handle_low_enriched_leads()
RETURNS TRIGGER AS $$
DECLARE
  affected_campaign_id UUID;
  campaign_record RECORD;
  platform_urls JSONB := '{}'::jsonb;
  platform_key TEXT;
  platform_data JSONB;
BEGIN
  -- Determine which campaign was affected
  IF TG_OP = 'DELETE' THEN
    affected_campaign_id := OLD.campaign_id;
  ELSE
    affected_campaign_id := NEW.campaign_id;
  END IF;
  
  -- Check if we should create a job
  IF NOT should_create_enrichment_job(affected_campaign_id) THEN
    RETURN NEW;
  END IF;
  
  -- Get campaign details
  SELECT id, name, search_url 
  INTO campaign_record
  FROM campaigns 
  WHERE id = affected_campaign_id;
  
  -- Extract all platforms and their data from search_url (same as activation trigger)
  FOR platform_key IN SELECT * FROM jsonb_object_keys(campaign_record.search_url) LOOP
    platform_data := campaign_record.search_url->platform_key;
    
    -- Build a simplified structure for the job
    platform_urls := platform_urls || jsonb_build_object(
      platform_key, jsonb_build_object(
        'search_url', platform_data->>'search_url',
        'page_number', (platform_data->>'page_number')::INT
      )
    );
  END LOOP;
  
  -- Create job with all platform URLs (identical to activation trigger)
  INSERT INTO public.jobs (
    job_type,
    data,
    priority,
    status,
    created_at,
    updated_at
  ) VALUES (
    'campaign_active',  -- Same job type as activation
    jsonb_build_object(
      'campaign_id', campaign_record.id,
      'campaign_name', campaign_record.name,
      'platform_urls', platform_urls,
      'triggered_by', 'low_enriched_leads'  -- Add context for debugging
    ),
    'normal',
    'pending',
    NOW(),
    NOW()
  );
  
  -- Log the automatic job creation
  RAISE NOTICE 'Created campaign_active job for campaign % due to low enriched leads', campaign_record.name;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on leads table
CREATE TRIGGER low_enriched_leads_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.leads
FOR EACH ROW
EXECUTE FUNCTION handle_low_enriched_leads();

-- Add helpful comments
COMMENT ON FUNCTION should_create_enrichment_job IS 'Checks if a campaign needs more enriched leads and if a job should be created';
COMMENT ON FUNCTION handle_low_enriched_leads IS 'Creates a campaign_active job when enriched leads fall below 5 for active campaigns';
COMMENT ON TRIGGER low_enriched_leads_trigger ON public.leads IS 'Monitors lead changes and triggers job creation when enriched leads are low';