-- supabase/migrations/20250731000001_create_client_members_table.sql
-- Creates client_members junction table for many-to-many user-client relationships with roles
-- Enables role-based access control (owner, admin, user) for multi-user client management
-- RELEVANT FILES: 20250728065254_add_user_id_to_clients.sql, 20250728065329_enable_rls_on_tables.sql

-- Create client_members junction table for many-to-many relationships
CREATE TABLE IF NOT EXISTS public.client_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'user')),
    created_at timestamptz NOT NULL DEFAULT now(),
    invited_by uuid REFERENCES auth.users(id),
    invited_at timestamptz DEFAULT now(),
    accepted_at timestamptz,
    
    -- Ensure unique user-client pairs
    UNIQUE(client_id, user_id)
);

-- Add indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_client_members_client_id ON public.client_members(client_id);
CREATE INDEX IF NOT EXISTS idx_client_members_user_id ON public.client_members(user_id);
CREATE INDEX IF NOT EXISTS idx_client_members_role ON public.client_members(role);
CREATE INDEX IF NOT EXISTS idx_client_members_pending ON public.client_members(client_id, user_id) WHERE accepted_at IS NULL;

-- Add helpful comment
COMMENT ON TABLE public.client_members IS 'Junction table managing many-to-many relationships between users and clients with role-based access control';
COMMENT ON COLUMN public.client_members.role IS 'User role within the client: owner (full access), admin (manage members), user (read-only)';
COMMENT ON COLUMN public.client_members.invited_by IS 'User who sent the invitation (null for initial owners)';
COMMENT ON COLUMN public.client_members.accepted_at IS 'When invitation was accepted (null for pending invitations)';

-- Enable RLS on the new table
ALTER TABLE public.client_members ENABLE ROW LEVEL SECURITY;

-- Create RLS policy: users can view memberships they're part of
CREATE POLICY "Users can view their own memberships" ON public.client_members
    FOR SELECT USING (auth.uid() = user_id);

-- Create RLS policy: owners and admins can view all client memberships
CREATE POLICY "Owners and admins can view client memberships" ON public.client_members
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = client_members.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- Create RLS policy: owners and admins can invite new members
CREATE POLICY "Owners and admins can invite members" ON public.client_members
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = client_members.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- Create RLS policy: users can accept their own invitations
CREATE POLICY "Users can accept their invitations" ON public.client_members
    FOR UPDATE USING (
        auth.uid() = user_id
        AND accepted_at IS NULL
    ) WITH CHECK (
        auth.uid() = user_id
        AND accepted_at IS NOT NULL
    );

-- Create RLS policy: owners and admins can update member roles
CREATE POLICY "Owners and admins can update member roles" ON public.client_members
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = client_members.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
        -- Prevent role changes that would leave no owners
        AND NOT (
            role = 'owner' 
            AND NEW.role != 'owner'
            AND (
                SELECT COUNT(*) FROM public.client_members cm2
                WHERE cm2.client_id = client_members.client_id
                AND cm2.role = 'owner'
                AND cm2.accepted_at IS NOT NULL
            ) = 1
        )
    );

-- Create RLS policy: owners and admins can remove members (except sole owners)
CREATE POLICY "Owners and admins can remove members" ON public.client_members
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = client_members.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
        -- Prevent deletion of sole owners
        AND NOT (
            role = 'owner'
            AND (
                SELECT COUNT(*) FROM public.client_members cm2
                WHERE cm2.client_id = client_members.client_id
                AND cm2.role = 'owner'
                AND cm2.accepted_at IS NOT NULL
            ) = 1
        )
    );

-- Create RLS policy: users can remove themselves from clients
CREATE POLICY "Users can remove themselves from clients" ON public.client_members
    FOR DELETE USING (
        auth.uid() = user_id
        -- Prevent sole owners from removing themselves
        AND NOT (
            role = 'owner'
            AND (
                SELECT COUNT(*) FROM public.client_members cm
                WHERE cm.client_id = client_members.client_id
                AND cm.role = 'owner'
                AND cm.accepted_at IS NOT NULL
            ) = 1
        )
    );