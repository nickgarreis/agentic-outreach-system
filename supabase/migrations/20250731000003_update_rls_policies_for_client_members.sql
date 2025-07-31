-- supabase/migrations/20250731000003_update_rls_policies_for_client_members.sql
-- Updates RLS policies to use client_members table for role-based access control
-- Replaces direct user_id checks with membership-based authorization
-- RELEVANT FILES: 20250731000001_create_client_members_table.sql, 20250728065329_enable_rls_on_tables.sql

-- =============================================================================
-- CLIENTS TABLE RLS POLICIES
-- =============================================================================

-- Drop old policies that used direct user_id relationship
DROP POLICY IF EXISTS "Users can view own clients" ON public.clients;
DROP POLICY IF EXISTS "Users can insert own clients" ON public.clients;
DROP POLICY IF EXISTS "Users can update own clients" ON public.clients;
DROP POLICY IF EXISTS "Users can delete own clients" ON public.clients;

-- Create new policies based on client_members table

-- SELECT: Users can view clients they are members of
CREATE POLICY "Users can view clients they are members of" ON public.clients
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = clients.id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- INSERT: Any authenticated user can create clients (they become owner automatically)
CREATE POLICY "Authenticated users can create clients" ON public.clients
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- UPDATE: Only owners and admins can update client details
CREATE POLICY "Owners and admins can update clients" ON public.clients
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = clients.id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- DELETE: Only owners can delete clients
CREATE POLICY "Only owners can delete clients" ON public.clients
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = clients.id
            AND cm.user_id = auth.uid()
            AND cm.role = 'owner'
            AND cm.accepted_at IS NOT NULL
        )
    );

-- =============================================================================
-- CAMPAIGNS TABLE RLS POLICIES
-- =============================================================================

-- Drop old policies
DROP POLICY IF EXISTS "Users can view campaigns for their clients" ON public.campaigns;
DROP POLICY IF EXISTS "Users can insert campaigns for their clients" ON public.campaigns;
DROP POLICY IF EXISTS "Users can update campaigns for their clients" ON public.campaigns;
DROP POLICY IF EXISTS "Users can delete campaigns for their clients" ON public.campaigns;

-- SELECT: Users can view campaigns for clients they are members of
CREATE POLICY "Users can view campaigns for their clients" ON public.campaigns
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = campaigns.client_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- INSERT: Users with any role can create campaigns for their clients
CREATE POLICY "Members can create campaigns for their clients" ON public.campaigns
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = campaigns.client_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- UPDATE: Owners and admins can update campaigns
CREATE POLICY "Owners and admins can update campaigns" ON public.campaigns
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = campaigns.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- DELETE: Owners and admins can delete campaigns
CREATE POLICY "Owners and admins can delete campaigns" ON public.campaigns
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.client_members cm
            WHERE cm.client_id = campaigns.client_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- =============================================================================
-- LEADS TABLE RLS POLICIES
-- =============================================================================

-- Drop old policies
DROP POLICY IF EXISTS "Users can view leads for their campaigns" ON public.leads;
DROP POLICY IF EXISTS "Users can insert leads for their campaigns" ON public.leads;
DROP POLICY IF EXISTS "Users can update leads for their campaigns" ON public.leads;
DROP POLICY IF EXISTS "Users can delete leads for their campaigns" ON public.leads;

-- SELECT: Users can view leads for campaigns of clients they are members of
CREATE POLICY "Users can view leads for their client campaigns" ON public.leads
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = leads.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- INSERT: Members can create leads for their client campaigns
CREATE POLICY "Members can create leads for their client campaigns" ON public.leads
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = leads.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- UPDATE: Owners and admins can update leads
CREATE POLICY "Owners and admins can update leads" ON public.leads
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = leads.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- DELETE: Owners and admins can delete leads
CREATE POLICY "Owners and admins can delete leads" ON public.leads
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = leads.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- =============================================================================
-- MESSAGES TABLE RLS POLICIES
-- =============================================================================

-- Drop old policies
DROP POLICY IF EXISTS "Users can view messages for their campaigns" ON public.messages;
DROP POLICY IF EXISTS "Users can insert messages for their campaigns" ON public.messages;
DROP POLICY IF EXISTS "Users can update messages for their campaigns" ON public.messages;
DROP POLICY IF EXISTS "Users can delete messages for their campaigns" ON public.messages;

-- SELECT: Users can view messages for campaigns of clients they are members of
CREATE POLICY "Users can view messages for their client campaigns" ON public.messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = messages.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- INSERT: Members can create messages for their client campaigns
CREATE POLICY "Members can create messages for their client campaigns" ON public.messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = messages.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.accepted_at IS NOT NULL
        )
    );

-- UPDATE: Owners and admins can update messages
CREATE POLICY "Owners and admins can update messages" ON public.messages
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = messages.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- DELETE: Owners and admins can delete messages
CREATE POLICY "Owners and admins can delete messages" ON public.messages
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.campaigns c
            JOIN public.client_members cm ON c.client_id = cm.client_id
            WHERE c.id = messages.campaign_id
            AND cm.user_id = auth.uid()
            AND cm.role IN ('owner', 'admin')
            AND cm.accepted_at IS NOT NULL
        )
    );

-- =============================================================================
-- HELPER FUNCTIONS FOR ROLE CHECKING
-- =============================================================================

-- Create helper function to check user role for a client (useful for API layer)
CREATE OR REPLACE FUNCTION public.get_user_client_role(client_uuid uuid, user_uuid uuid DEFAULT auth.uid())
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    user_role text;
BEGIN
    SELECT role INTO user_role
    FROM public.client_members
    WHERE client_id = client_uuid
    AND user_id = user_uuid
    AND accepted_at IS NOT NULL;
    
    RETURN COALESCE(user_role, 'none');
END;
$$;

-- Create helper function to check if user has minimum role for a client
CREATE OR REPLACE FUNCTION public.user_has_client_role(client_uuid uuid, required_role text, user_uuid uuid DEFAULT auth.uid())
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    user_role text;
    role_hierarchy integer;
BEGIN
    -- Get user's actual role
    user_role := public.get_user_client_role(client_uuid, user_uuid);
    
    -- Define role hierarchy (higher number = more permissions)
    role_hierarchy := CASE user_role
        WHEN 'owner' THEN 3
        WHEN 'admin' THEN 2
        WHEN 'user' THEN 1
        ELSE 0
    END;
    
    -- Check if user meets minimum role requirement
    RETURN role_hierarchy >= CASE required_role
        WHEN 'owner' THEN 3
        WHEN 'admin' THEN 2
        WHEN 'user' THEN 1
        ELSE 0
    END;
END;
$$;

-- Add comments for documentation
COMMENT ON FUNCTION public.get_user_client_role(uuid, uuid) IS 'Returns the role of a user for a specific client, or ''none'' if not a member';
COMMENT ON FUNCTION public.user_has_client_role(uuid, text, uuid) IS 'Checks if a user has at least the specified role for a client';