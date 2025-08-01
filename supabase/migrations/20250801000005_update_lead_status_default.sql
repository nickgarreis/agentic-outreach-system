-- Update the default value for lead status column
-- Change from 'new' to 'enrichment_failed' to better reflect the actual state

ALTER TABLE public.leads 
ALTER COLUMN status SET DEFAULT 'enrichment_failed';

-- Add helpful comment
COMMENT ON COLUMN public.leads.status IS 'Lead enrichment status: "enriched" = successfully enriched, "enrichment_failed" = enrichment failed or not attempted';