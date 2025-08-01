-- supabase/migrations/20250801000015_add_email_receiving_support.sql
-- Adds email receiving support for handling inbound emails from leads
-- Enables email threading and conversation tracking
-- RELEVANT FILES: 20250801000012_add_sender_configuration.sql, 20250801000011_add_email_sending_infrastructure.sql

-- Add thread tracking to messages table
ALTER TABLE public.messages 
ADD COLUMN IF NOT EXISTS thread_id uuid,
ADD COLUMN IF NOT EXISTS email_message_id text,
ADD COLUMN IF NOT EXISTS in_reply_to text;

-- Add comments for documentation
COMMENT ON COLUMN public.messages.thread_id IS 'UUID to group messages in the same email conversation thread';
COMMENT ON COLUMN public.messages.email_message_id IS 'RFC 2822 Message-ID header value for email threading';
COMMENT ON COLUMN public.messages.in_reply_to IS 'RFC 2822 In-Reply-To header value for linking to parent message';

-- Add reply domain configuration to campaigns
ALTER TABLE public.campaigns
ADD COLUMN IF NOT EXISTS reply_to_domain text;

COMMENT ON COLUMN public.campaigns.reply_to_domain IS 'Domain for receiving replies (e.g., reply.yourdomain.com). Must be configured with SendGrid Inbound Parse';

-- Create index for efficient email threading lookups
CREATE INDEX IF NOT EXISTS idx_messages_thread_id 
ON public.messages(thread_id) 
WHERE thread_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_messages_email_message_id 
ON public.messages(email_message_id) 
WHERE email_message_id IS NOT NULL;

-- Create function to generate email message IDs
CREATE OR REPLACE FUNCTION generate_email_message_id(
    p_message_id uuid,
    p_domain text DEFAULT 'example.com'
) RETURNS text AS $$
BEGIN
    -- Generate RFC 2822 compliant Message-ID
    -- Format: <message_uuid@domain>
    RETURN format('<%s@%s>', p_message_id::text, p_domain);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create function to handle inbound email processing
CREATE OR REPLACE FUNCTION process_inbound_email(
    p_from_email text,
    p_to_email text,
    p_subject text,
    p_content text,
    p_message_id text,
    p_in_reply_to text DEFAULT NULL,
    p_sendgrid_data jsonb DEFAULT '{}'::jsonb
) RETURNS uuid AS $$
DECLARE
    v_lead_id uuid;
    v_campaign_id uuid;
    v_thread_id uuid;
    v_parent_message_id uuid;
    v_new_message_id uuid;
BEGIN
    -- Find the lead by email
    SELECT id INTO v_lead_id
    FROM public.leads
    WHERE LOWER(email) = LOWER(p_from_email)
    LIMIT 1;
    
    -- If no lead found, return null (reject the email)
    IF v_lead_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Extract campaign ID from to_email if it follows pattern: reply+{message_id}@domain
    -- This allows us to link the reply to the original message
    IF p_to_email ~ '^reply\+[0-9a-f\-]+@' THEN
        -- Extract the UUID from the email
        v_parent_message_id := substring(p_to_email from 'reply\+([0-9a-f\-]+)@')::uuid;
        
        -- Get campaign_id and thread_id from parent message
        SELECT campaign_id, COALESCE(thread_id, id) 
        INTO v_campaign_id, v_thread_id
        FROM public.messages
        WHERE id = v_parent_message_id;
    END IF;
    
    -- If we couldn't determine campaign from reply address, 
    -- try to find it from the lead's most recent message
    IF v_campaign_id IS NULL THEN
        SELECT campaign_id INTO v_campaign_id
        FROM public.messages
        WHERE lead_id = v_lead_id
        ORDER BY created_at DESC
        LIMIT 1;
    END IF;
    
    -- If still no campaign, we can't process this email
    IF v_campaign_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- If no thread_id was found, check if this is a reply to an existing message
    IF v_thread_id IS NULL AND p_in_reply_to IS NOT NULL THEN
        SELECT COALESCE(thread_id, id) INTO v_thread_id
        FROM public.messages
        WHERE email_message_id = p_in_reply_to
        LIMIT 1;
    END IF;
    
    -- Insert the inbound message
    INSERT INTO public.messages (
        lead_id,
        campaign_id,
        channel,
        direction,
        content,
        subject,
        status,
        thread_id,
        email_message_id,
        in_reply_to,
        metadata
    ) VALUES (
        v_lead_id,
        v_campaign_id,
        'email',
        'inbound',
        p_content,
        p_subject,
        'delivered',
        v_thread_id,
        p_message_id,
        p_in_reply_to,
        jsonb_build_object(
            'source', 'inbound_parse',
            'received_at', now(),
            'sendgrid_data', p_sendgrid_data
        )
    ) RETURNING id INTO v_new_message_id;
    
    -- If this created a new thread, update the message to reference itself
    IF v_thread_id IS NULL THEN
        UPDATE public.messages 
        SET thread_id = v_new_message_id
        WHERE id = v_new_message_id;
    END IF;
    
    RETURN v_new_message_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION generate_email_message_id TO authenticated;
GRANT EXECUTE ON FUNCTION process_inbound_email TO authenticated;

-- Add trigger to auto-generate message IDs for outbound emails
CREATE OR REPLACE FUNCTION auto_generate_message_id()
RETURNS TRIGGER AS $$
BEGIN
    -- Only generate for outbound emails without existing message_id
    IF NEW.direction = 'outbound' AND 
       NEW.channel = 'email' AND 
       NEW.email_message_id IS NULL THEN
        
        -- Get reply domain from campaign
        SELECT COALESCE(c.reply_to_domain, 'example.com')
        INTO NEW.email_message_id
        FROM public.campaigns c
        WHERE c.id = NEW.campaign_id;
        
        -- Generate the message ID
        NEW.email_message_id := generate_email_message_id(NEW.id, NEW.email_message_id);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_email_message_id
BEFORE INSERT ON public.messages
FOR EACH ROW
EXECUTE FUNCTION auto_generate_message_id();