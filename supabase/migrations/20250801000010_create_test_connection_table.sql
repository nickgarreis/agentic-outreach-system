-- Create a minimal table for health check testing
-- This table is used by the API health endpoint to verify database connectivity
CREATE TABLE IF NOT EXISTS public._test_connection (
    id INTEGER PRIMARY KEY DEFAULT 1,
    status TEXT DEFAULT 'ok',
    CHECK (id = 1)  -- Ensure only one row can exist
);

-- Insert the single test row
INSERT INTO public._test_connection (id, status) 
VALUES (1, 'ok') 
ON CONFLICT (id) DO NOTHING;

-- Add table comment for documentation
COMMENT ON TABLE public._test_connection IS 'Health check test table - do not delete. Used by API /health endpoint to verify database connectivity.';

-- Enable RLS for consistency (though this table is read-only)
ALTER TABLE public._test_connection ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows all authenticated users to read
CREATE POLICY "Anyone can read test connection" ON public._test_connection
    FOR SELECT
    USING (true);