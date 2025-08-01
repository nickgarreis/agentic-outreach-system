-- supabase/migrations/20250801000017_add_lead_enrichment_trigger.sql
-- Creates trigger to automatically enrich leads with placeholder emails
-- Separates discovery and enrichment into distinct job phases
-- RELEVANT FILES: 20250801000007_add_lead_research_trigger.sql, 20250801000003_add_campaign_activation_trigger.sql

-- Function to handle lead enrichment job creation
CREATE OR REPLACE FUNCTION handle_lead_enrichment_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create enrichment job for newly inserted leads with placeholder emails
    -- Check for common placeholder patterns
    IF (NEW.email LIKE '%placeholder%' OR 
        NEW.email = 'email_not_unlocked@domain.com' OR
        NEW.email LIKE '%example.com' OR
        NEW.email IS NULL) THEN
        
        -- Create enrichment job with normal priority
        INSERT INTO public.jobs (
            job_type,
            data,
            priority,
            status,
            created_at,
            updated_at
        ) VALUES (
            'lead_enrichment',
            jsonb_build_object(
                'lead_id', NEW.id,
                'campaign_id', NEW.campaign_id,
                'client_id', NEW.client_id,
                'lead_name', CONCAT(NEW.first_name, ' ', NEW.last_name),
                'company', NEW.company,
                'attempt_number', 1
            ),
            'normal',
            'pending',
            NOW(),
            NOW()
        );
        
        -- Log the job creation
        RAISE NOTICE 'Created lead_enrichment job for lead % with placeholder email %', NEW.id, NEW.email;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger that fires after lead insertion
CREATE TRIGGER lead_enrichment_on_insert
AFTER INSERT ON public.leads
FOR EACH ROW
EXECUTE FUNCTION handle_lead_enrichment_trigger();

-- Add helpful comments
COMMENT ON FUNCTION handle_lead_enrichment_trigger IS 'Creates lead_enrichment jobs for newly discovered leads with placeholder emails';
COMMENT ON TRIGGER lead_enrichment_on_insert ON public.leads IS 'Automatically triggers enrichment for leads that need real email addresses';