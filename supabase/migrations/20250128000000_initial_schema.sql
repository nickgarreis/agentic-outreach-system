-- Initial schema migration for Agentic Outreach System
-- This migration creates the complete database structure

-- Create clients table
create table if not exists public.clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz not null default now(),
    user_id uuid references auth.users(id) -- Owner of the client organization
);

-- Enable RLS on clients
alter table public.clients enable row level security;

-- RLS Policies for clients
create policy "Users can view own clients" on public.clients
    for select using (auth.uid() = user_id);

create policy "Users can insert own clients" on public.clients
    for insert with check (auth.uid() = user_id);

create policy "Users can update own clients" on public.clients
    for update using (auth.uid() = user_id);

create policy "Users can delete own clients" on public.clients
    for delete using (auth.uid() = user_id);

-- Create campaigns table
create table if not exists public.campaigns (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references public.clients(id),
    name text not null,
    status text not null default 'draft',
    created_at timestamptz not null default now()
);

-- Enable RLS on campaigns
alter table public.campaigns enable row level security;

-- RLS Policies for campaigns
create policy "Users can view campaigns for their clients" on public.campaigns
    for select using (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

create policy "Users can insert campaigns for their clients" on public.campaigns
    for insert with check (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

create policy "Users can update campaigns for their clients" on public.campaigns
    for update using (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

create policy "Users can delete campaigns for their clients" on public.campaigns
    for delete using (
        client_id in (
            select id from public.clients where user_id = auth.uid()
        )
    );

-- Create leads table
create table if not exists public.leads (
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

-- Enable RLS on leads
alter table public.leads enable row level security;

-- RLS Policies for leads
create policy "Users can view leads for their campaigns" on public.leads
    for select using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can insert leads for their campaigns" on public.leads
    for insert with check (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can update leads for their campaigns" on public.leads
    for update using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can delete leads for their campaigns" on public.leads
    for delete using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

-- Create messages table
create table if not exists public.messages (
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

-- Enable RLS on messages
alter table public.messages enable row level security;

-- RLS Policies for messages
create policy "Users can view messages for their campaigns" on public.messages
    for select using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can insert messages for their campaigns" on public.messages
    for insert with check (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can update messages for their campaigns" on public.messages
    for update using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );

create policy "Users can delete messages for their campaigns" on public.messages
    for delete using (
        campaign_id in (
            select c.id 
            from public.campaigns c
            join public.clients cl on c.client_id = cl.id
            where cl.user_id = auth.uid()
        )
    );