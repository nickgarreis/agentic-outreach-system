-- supabase/migrations/20250731000005_cleanup_old_user_id_column.sql
-- Removes the deprecated user_id column from clients table after migration to client_members
-- Completes the transition to many-to-many relationships with role-based access
-- RELEVANT FILES: 20250731000001_create_client_members_table.sql, 20250731000002_migrate_existing_client_users.sql

-- Verify that all existing client relationships have been migrated
DO $$
DECLARE
    unmigrated_count INTEGER;
BEGIN
    -- Count clients with user_id that don't have corresponding client_members entry
    SELECT COUNT(*) INTO unmigrated_count
    FROM public.clients c
    WHERE c.user_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM public.client_members cm
        WHERE cm.client_id = c.id
        AND cm.user_id = c.user_id
        AND cm.role = 'owner'
        AND cm.accepted_at IS NOT NULL
    );
    
    -- Raise error if any unmigrated relationships found
    IF unmigrated_count > 0 THEN
        RAISE EXCEPTION 'Cannot proceed with cleanup: % clients have unmigrated user relationships', unmigrated_count;
    END IF;
    
    RAISE NOTICE 'Migration verification passed: all client relationships migrated successfully';
END $$;

-- Drop the foreign key constraint first
ALTER TABLE public.clients DROP CONSTRAINT IF EXISTS clients_user_id_fkey;

-- Remove the user_id column from clients table
ALTER TABLE public.clients DROP COLUMN IF EXISTS user_id;

-- Add helpful comment to document the change
COMMENT ON TABLE public.clients IS 'Client entities with many-to-many user relationships managed via client_members table';

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Cleanup completed: removed deprecated user_id column from clients table';
END $$;