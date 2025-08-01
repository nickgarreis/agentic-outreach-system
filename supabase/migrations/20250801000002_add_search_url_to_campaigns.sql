-- Add search_url column to campaigns table for storing platform search configurations
ALTER TABLE public.campaigns 
ADD COLUMN search_url JSONB DEFAULT '{}'::jsonb;

-- Add helpful comment
COMMENT ON COLUMN public.campaigns.search_url IS 
'Search URLs and pagination state for lead discovery platforms. Structure: {"apollo": {"search_url": "...", "page_number": 1}, "linkedin": {"search_url": "...", "page_number": 1}}';