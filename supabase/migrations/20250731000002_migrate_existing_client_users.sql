-- supabase/migrations/20250731000002_migrate_existing_client_users.sql
-- Migrates existing clients.user_id relationships to client_members table as owners
-- Ensures backwards compatibility during transition to many-to-many relationships
-- RELEVANT FILES: 20250731000001_create_client_members_table.sql, 20250728065254_add_user_id_to_clients.sql

-- Insert existing client-user relationships as 'owner' roles in client_members table
-- Only migrate clients that have a valid user_id (not null)
INSERT INTO public.client_members (client_id, user_id, role, created_at, accepted_at)
SELECT 
    c.id as client_id,
    c.user_id,
    'owner' as role,
    c.created_at,
    c.created_at as accepted_at -- Auto-accept since these are existing relationships
FROM public.clients c
WHERE c.user_id IS NOT NULL
-- Use ON CONFLICT to handle any potential duplicates gracefully
ON CONFLICT (client_id, user_id) DO NOTHING;

-- Verify the migration worked correctly
-- This should match the count of clients with non-null user_id
DO $$
DECLARE
    clients_with_users INTEGER;
    migrated_members INTEGER;
BEGIN
    -- Count clients with user_id
    SELECT COUNT(*) INTO clients_with_users 
    FROM public.clients 
    WHERE user_id IS NOT NULL;
    
    -- Count migrated members with owner role
    SELECT COUNT(*) INTO migrated_members 
    FROM public.client_members 
    WHERE role = 'owner' AND accepted_at IS NOT NULL;
    
    -- Log the results
    RAISE NOTICE 'Migration completed: % clients with users, % owner members created', 
        clients_with_users, migrated_members;
    
    -- Ensure counts match (allowing for potential pre-existing data)
    IF migrated_members < clients_with_users THEN
        RAISE EXCEPTION 'Migration incomplete: expected at least % owner members, got %', 
            clients_with_users, migrated_members;
    END IF;
END $$;