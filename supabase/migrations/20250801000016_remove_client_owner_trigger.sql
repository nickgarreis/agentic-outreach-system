-- supabase/migrations/20250801000016_remove_client_owner_trigger.sql
-- Removes the automatic client owner trigger to allow more flexible client creation
-- This trigger was causing issues with direct SQL inserts without auth context
-- RELEVANT FILES: 20250731000004_auto_add_client_owner.sql

-- Drop the trigger first
DROP TRIGGER IF EXISTS trigger_add_client_owner ON public.clients;

-- Drop the trigger function (also handles the old naming convention)
DROP FUNCTION IF EXISTS public.add_client_owner();
DROP TRIGGER IF EXISTS add_client_owner_trigger ON public.clients;

-- Add comment explaining the removal
COMMENT ON TABLE public.clients IS 'Client entities - owner relationships must be manually managed through client_members table';