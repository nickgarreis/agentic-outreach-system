-- supabase/migrations/20250801000020_disable_automatic_triggers.sql
-- Disables all automatic triggers to allow manual control via chat interface
-- User can now explicitly tell the AutopilotAgent what to do
-- RELEVANT FILES: src/routers/chat.py, src/agent/autopilot_agent.py

-- Disable campaign activation trigger
ALTER TABLE campaigns DISABLE TRIGGER campaign_activation_trigger;

-- Disable lead enrichment trigger
ALTER TABLE leads DISABLE TRIGGER lead_enrichment_on_insert;

-- Disable lead outreach triggers
ALTER TABLE leads DISABLE TRIGGER lead_outreach_trigger;
ALTER TABLE leads DISABLE TRIGGER lead_outreach_on_insert_trigger;

-- Disable lead research trigger
ALTER TABLE leads DISABLE TRIGGER lead_research_on_lead_change_trigger;

-- Disable low enriched leads trigger  
ALTER TABLE leads DISABLE TRIGGER low_enriched_leads_trigger;

-- Disable message-based lead research trigger
ALTER TABLE messages DISABLE TRIGGER lead_research_trigger;

-- Add comment explaining the change
COMMENT ON TABLE public.jobs IS 'Background job queue for AutopilotAgent tasks - now primarily created through manual chat commands rather than automatic triggers';