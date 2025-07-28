-- Initial schema migration for Agentic Outreach System
-- This migration creates the complete database structure
-- Made idempotent to work on both dev and main branches

-- Create clients table
create table if not exists public.clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz not null default now(),
    user_id uuid references auth.users(id) -- Owner of the client organization
);

-- Enable RLS on clients if not already enabled
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'clients' 
        AND rowsecurity = true
    ) THEN
        ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- RLS Policies for clients (drop if exists, then create)
DROP POLICY IF EXISTS "Users can view own clients" ON public.clients;
CREATE POLICY "Users can view own clients" ON public.clients
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own clients" ON public.clients;
CREATE POLICY "Users can insert own clients" ON public.clients
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own clients" ON public.clients;
CREATE POLICY "Users can update own clients" ON public.clients
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own clients" ON public.clients;
CREATE POLICY "Users can delete own clients" ON public.clients
    FOR DELETE USING (auth.uid() = user_id);

-- Create campaigns table
CREATE TABLE IF NOT EXISTS public.campaigns (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id),
    name text not null,
    status text not null default 'draft',
    created_at timestamptz not null default now()
);

-- Enable RLS on campaigns if not already enabled
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'campaigns' 
        AND rowsecurity = true
    ) THEN
        ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- RLS Policies for campaigns (drop if exists, then create)
DROP POLICY IF EXISTS "Users can view campaigns for their clients" ON public.campaigns;
CREATE POLICY "Users can view campaigns for their clients" ON public.campaigns
    FOR SELECT USING (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert campaigns for their clients" ON public.campaigns;
CREATE POLICY "Users can insert campaigns for their clients" ON public.campaigns
    FOR INSERT WITH CHECK (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update campaigns for their clients" ON public.campaigns;
CREATE POLICY "Users can update campaigns for their clients" ON public.campaigns
    FOR UPDATE USING (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can delete campaigns for their clients" ON public.campaigns;
CREATE POLICY "Users can delete campaigns for their clients" ON public.campaigns
    FOR DELETE USING (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

-- Create leads table
CREATE TABLE IF NOT EXISTS public.leads (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id),
    email text,
    first_name text,
    last_name text,
    company text,
    status text not null default 'new',
    created_at timestamptz not null default now(),
    client_id uuid references public.clients(id)
);

-- Enable RLS on leads if not already enabled
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'leads' 
        AND rowsecurity = true
    ) THEN
        ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- RLS Policies for leads (drop if exists, then create)
DROP POLICY IF EXISTS "Users can view leads for their campaigns" ON public.leads;
CREATE POLICY "Users can view leads for their campaigns" ON public.leads
    FOR SELECT USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert leads for their campaigns" ON public.leads;
CREATE POLICY "Users can insert leads for their campaigns" ON public.leads
    FOR INSERT WITH CHECK (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update leads for their campaigns" ON public.leads;
CREATE POLICY "Users can update leads for their campaigns" ON public.leads
    FOR UPDATE USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can delete leads for their campaigns" ON public.leads;
CREATE POLICY "Users can delete leads for their campaigns" ON public.leads
    FOR DELETE USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

-- Create messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id uuid primary key default gen_random_uuid(),
    lead_id uuid not null references public.leads(id),
    campaign_id uuid not null references public.campaigns(id),
    channel text not null,
    direction text not null,
    content text,
    send_at timestamptz,
    sent_at timestamptz,
    status text not null default 'scheduled',
    created_at timestamptz not null default now()
);

-- Enable RLS on messages if not already enabled
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'messages' 
        AND rowsecurity = true
    ) THEN
        ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- RLS Policies for messages (drop if exists, then create)
DROP POLICY IF EXISTS "Users can view messages for their campaigns" ON public.messages;
CREATE POLICY "Users can view messages for their campaigns" ON public.messages
    FOR SELECT USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert messages for their campaigns" ON public.messages;
CREATE POLICY "Users can insert messages for their campaigns" ON public.messages
    FOR INSERT WITH CHECK (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update messages for their campaigns" ON public.messages;
CREATE POLICY "Users can update messages for their campaigns" ON public.messages
    FOR UPDATE USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can delete messages for their campaigns" ON public.messages;
CREATE POLICY "Users can delete messages for their campaigns" ON public.messages
    FOR DELETE USING (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );