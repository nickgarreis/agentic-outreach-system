-- supabase/migrations/20250801000019_add_agent_chat_tables.sql
-- Adds tables for real-time chat between users and AutopilotAgent
-- Enables manual agent communication with conversation history and optional RAG memory
-- RELEVANT FILES: src/routers/chat.py, src/agent/autopilot_agent.py

-- 1. Simple conversations table
CREATE TABLE public.conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  campaign_id uuid REFERENCES public.campaigns(id), -- optional campaign context
  created_at timestamptz DEFAULT now()
);

-- 2. Chat messages table
CREATE TYPE public.message_role AS ENUM ('user', 'agent');

CREATE TABLE public.chat_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid REFERENCES public.conversations(id) ON DELETE CASCADE,
  role public.message_role NOT NULL,
  content text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- 3. Optional vector memory (costs nothing to add now)
CREATE TABLE public.agent_memory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid REFERENCES public.conversations(id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536), -- for OpenAI embeddings
  metadata jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX idx_chat_messages_conversation ON public.chat_messages(conversation_id, created_at);
CREATE INDEX idx_agent_memory_conversation ON public.agent_memory(conversation_id);
CREATE INDEX idx_agent_memory_embedding ON public.agent_memory USING ivfflat (embedding vector_cosine_ops);

-- 4. Helper function for memory search
CREATE OR REPLACE FUNCTION match_memories(
  query_embedding vector(1536),
  conversation_uuid uuid,
  match_count int DEFAULT 5
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    am.id,
    am.content,
    am.metadata,
    1 - (am.embedding <=> query_embedding) as similarity
  FROM agent_memory am
  WHERE am.conversation_id = conversation_uuid
  ORDER BY am.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Enable RLS
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory ENABLE ROW LEVEL SECURITY;

-- Users can only see their own conversations
CREATE POLICY "Users can manage their conversations" 
ON public.conversations
FOR ALL 
USING (auth.uid() = user_id);

-- Users can view messages in their conversations
CREATE POLICY "Users can view their messages" 
ON public.chat_messages
FOR SELECT 
USING (
  EXISTS (
    SELECT 1 FROM public.conversations 
    WHERE id = chat_messages.conversation_id 
    AND user_id = auth.uid()
  )
);

-- Users can view memory for their conversations
CREATE POLICY "Users can view their memory" 
ON public.agent_memory
FOR SELECT 
USING (
  EXISTS (
    SELECT 1 FROM public.conversations 
    WHERE id = agent_memory.conversation_id 
    AND user_id = auth.uid()
  )
);

-- Add helpful comments
COMMENT ON TABLE public.conversations IS 'Chat sessions between users and AutopilotAgent';
COMMENT ON TABLE public.chat_messages IS 'Individual messages in a conversation';
COMMENT ON TABLE public.agent_memory IS 'Vector embeddings for RAG-based contextual memory';
COMMENT ON FUNCTION match_memories IS 'Find similar memories using vector similarity search';