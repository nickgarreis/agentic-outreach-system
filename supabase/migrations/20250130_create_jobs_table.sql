-- Create jobs table for background worker queue
-- This table stores jobs to be processed by the AutopilotAgent
-- Supports job scheduling, retries, and status tracking

-- Create jobs table
CREATE TABLE IF NOT EXISTS public.jobs (
    id uuid primary key default gen_random_uuid(),
    job_type text not null, -- Type of job (campaign_execution, lead_enrichment, etc.)
    data jsonb not null default '{}'::jsonb, -- Job-specific data
    priority text not null default 'normal' check (priority in ('low', 'normal', 'high')),
    status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    
    -- Timing fields
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    scheduled_for timestamptz, -- Optional future execution time
    started_at timestamptz, -- When job processing started
    completed_at timestamptz, -- When job completed successfully
    failed_at timestamptz, -- When job failed
    cancelled_at timestamptz, -- When job was cancelled
    
    -- Retry fields
    retry_count int not null default 0,
    retry_at timestamptz, -- When to retry the job
    
    -- Worker tracking
    worker_id text, -- ID of the worker processing this job
    
    -- Result storage
    result jsonb, -- Job execution result
    
    -- Indexes for efficient querying
    CONSTRAINT valid_status CHECK (
        (status = 'pending' AND started_at IS NULL) OR
        (status = 'processing' AND started_at IS NOT NULL) OR
        (status = 'completed' AND completed_at IS NOT NULL) OR
        (status = 'failed' AND failed_at IS NOT NULL) OR
        (status = 'cancelled' AND cancelled_at IS NOT NULL)
    )
);

-- Create indexes for efficient job polling
CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON public.jobs(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled ON public.jobs(scheduled_for) WHERE scheduled_for IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_retry ON public.jobs(retry_at) WHERE retry_at IS NOT NULL AND status = 'pending';
CREATE INDEX IF NOT EXISTS idx_jobs_type ON public.jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON public.jobs(created_at);

-- Enable RLS on jobs table
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policies for jobs table
-- Note: Jobs are system-level, so we'll use service role key for backend operations
-- No user-level access is needed for the jobs table

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_jobs_updated_at ON public.jobs;
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON public.jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add helpful comments
COMMENT ON TABLE public.jobs IS 'Background job queue for AutopilotAgent tasks';
COMMENT ON COLUMN public.jobs.job_type IS 'Type of job to execute (e.g., campaign_execution, lead_enrichment)';
COMMENT ON COLUMN public.jobs.data IS 'Job-specific data passed to the AutopilotAgent';
COMMENT ON COLUMN public.jobs.priority IS 'Job priority: low, normal, or high';
COMMENT ON COLUMN public.jobs.status IS 'Current job status: pending, processing, completed, failed, or cancelled';
COMMENT ON COLUMN public.jobs.result IS 'Result data from job execution';
COMMENT ON COLUMN public.jobs.worker_id IS 'Identifier of the worker processing this job';