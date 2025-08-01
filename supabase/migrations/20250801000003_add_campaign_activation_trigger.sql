-- Create function to handle campaign activation and job creation
CREATE OR REPLACE FUNCTION handle_campaign_activation()
RETURNS TRIGGER AS $$
DECLARE
  platform_urls JSONB := '{}'::jsonb;
  platform_key TEXT;
  platform_data JSONB;
BEGIN
  -- Trigger when status changes to 'active'
  IF NEW.status = 'active' AND OLD.status != 'active' THEN
    
    -- Extract all platforms and their data from search_url
    FOR platform_key IN SELECT * FROM jsonb_object_keys(NEW.search_url) LOOP
      platform_data := NEW.search_url->platform_key;
      
      -- Build a simplified structure for the job
      platform_urls := platform_urls || jsonb_build_object(
        platform_key, jsonb_build_object(
          'search_url', platform_data->>'search_url',
          'page_number', (platform_data->>'page_number')::INT
        )
      );
    END LOOP;
    
    -- Create job with all platform URLs
    INSERT INTO public.jobs (
      job_type,
      data,
      priority,
      status,
      created_at,
      updated_at
    ) VALUES (
      'campaign_active',
      jsonb_build_object(
        'campaign_id', NEW.id,
        'campaign_name', NEW.name,
        'platform_urls', platform_urls
      ),
      'normal',
      'pending',
      NOW(),
      NOW()
    );
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER campaign_activation_trigger
AFTER UPDATE ON public.campaigns
FOR EACH ROW
EXECUTE FUNCTION handle_campaign_activation();

-- Add helpful comment
COMMENT ON FUNCTION handle_campaign_activation() IS 'Creates a campaign_active job when campaign status changes to active, extracting all configured search URLs';