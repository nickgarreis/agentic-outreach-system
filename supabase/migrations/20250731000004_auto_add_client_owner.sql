-- supabase/migrations/20250731000004_auto_add_client_owner.sql
-- Creates trigger to automatically add client creator as owner in client_members table
-- Ensures every new client has at least one owner without requiring separate API calls
-- RELEVANT FILES: 20250731000001_create_client_members_table.sql, 20250731000003_update_rls_policies_for_client_members.sql

-- Create function to automatically add client creator as owner
CREATE OR REPLACE FUNCTION public.add_client_owner()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Add the client creator as an owner with accepted status
    INSERT INTO public.client_members (client_id, user_id, role, created_at, accepted_at)
    VALUES (NEW.id, auth.uid(), 'owner', now(), now())
    ON CONFLICT (client_id, user_id) DO NOTHING;
    
    RETURN NEW;
END;
$$;

-- Create trigger to fire after client insertion
CREATE TRIGGER trigger_add_client_owner
    AFTER INSERT ON public.clients
    FOR EACH ROW
    EXECUTE FUNCTION public.add_client_owner();

-- Add helpful comment
COMMENT ON FUNCTION public.add_client_owner() IS 'Automatically adds the client creator as an owner in client_members table';
COMMENT ON TRIGGER trigger_add_client_owner ON public.clients IS 'Ensures every new client has its creator as an owner';