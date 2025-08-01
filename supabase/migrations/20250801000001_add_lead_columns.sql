-- /supabase/migrations/20250801000001_add_lead_columns.sql
-- Add new columns to the leads table: title, phone, and full_context
-- These columns will store additional lead information and enrichment data
-- RELEVANT FILES: supabase/migrations/20250728063444_simplify_leads_table.sql, src/models/leads.py

-- Add title column to store job title/position of the lead
ALTER TABLE public.leads 
ADD COLUMN title TEXT;

COMMENT ON COLUMN public.leads.title IS 'Job title or position of the lead';

-- Add phone column to store phone number in flexible text format
ALTER TABLE public.leads 
ADD COLUMN phone TEXT;

COMMENT ON COLUMN public.leads.phone IS 'Phone number of the lead (supports international formats and extensions)';

-- Add full_context column to store additional enrichment data as JSONB
ALTER TABLE public.leads 
ADD COLUMN full_context JSONB DEFAULT '{}';

COMMENT ON COLUMN public.leads.full_context IS 'Additional enrichment data about the lead stored as JSON (company info, social profiles, etc.)';