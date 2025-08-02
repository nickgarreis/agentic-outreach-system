# src/routers/chat.py
# FastAPI router for real-time chat with AutopilotAgent
# Provides synchronous chat endpoint that integrates with Supabase realtime
# RELEVANT FILES: ../agent/autopilot_agent.py, ../database.py, ../deps.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import logging

from ..deps import get_current_user, UserClaims
from ..database import get_supabase
from ..agent import AutopilotAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Request model for sending a chat message"""
    conversation_id: Optional[str] = None
    message: str
    campaign_id: Optional[str] = None  # Optional campaign context


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    conversation_id: str
    response: str


@router.post("/send", response_model=ChatResponse)
async def send_message(
    chat_msg: ChatMessage,
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Send message to AutopilotAgent and get response.
    Creates a new conversation if conversation_id is not provided.
    """
    logger.info(f"Chat request from user {current_user.id}")
    
    supabase = await get_supabase()
    
    # Create or validate conversation
    if not chat_msg.conversation_id:
        # Create new conversation
        logger.info("Creating new conversation")
        conversation_data = {
            "user_id": str(current_user.id)
        }
        
        # Add campaign context if provided
        if chat_msg.campaign_id:
            conversation_data["campaign_id"] = chat_msg.campaign_id
            
        result = await supabase.table("conversations").insert(
            conversation_data
        ).execute()
        
        if not result.data:
            raise HTTPException(500, "Failed to create conversation")
            
        conversation_id = result.data[0]["id"]
        logger.info(f"Created new conversation: {conversation_id}")
    else:
        conversation_id = chat_msg.conversation_id
        
        # Verify user owns this conversation
        conv_result = await supabase.table("conversations")\
            .select("user_id")\
            .eq("id", conversation_id)\
            .single()\
            .execute()
            
        if not conv_result.data:
            raise HTTPException(404, "Conversation not found")
            
        if conv_result.data["user_id"] != str(current_user.id):
            raise HTTPException(403, "Not your conversation")
    
    # Store user message
    await supabase.table("chat_messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": chat_msg.message
    }).execute()
    
    logger.info(f"Stored user message for conversation {conversation_id}")
    
    # Get agent response
    # Create a unique job ID for tracking
    job_id = str(uuid.uuid4())
    agent = AutopilotAgent("chat", job_id)
    
    try:
        response = await agent.chat(conversation_id, chat_msg.message)
    except Exception as e:
        logger.error(f"Error getting agent response: {e}")
        raise HTTPException(500, f"Agent error: {str(e)}")
    
    # Store agent response
    await supabase.table("chat_messages").insert({
        "conversation_id": conversation_id,
        "role": "agent",
        "content": response
    }).execute()
    
    logger.info(f"Stored agent response for conversation {conversation_id}")
    
    return ChatResponse(
        conversation_id=conversation_id,
        response=response
    )


@router.get("/conversations")
async def list_conversations(
    current_user: UserClaims = Depends(get_current_user)
):
    """
    List all conversations for the current user.
    """
    supabase = await get_supabase()
    
    result = await supabase.table("conversations")\
        .select("id, campaign_id, created_at")\
        .eq("user_id", str(current_user.id))\
        .order("created_at", desc=True)\
        .execute()
    
    return {
        "conversations": result.data
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = 50,
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Get messages for a specific conversation.
    """
    supabase = await get_supabase()
    
    # Verify user owns this conversation
    conv_result = await supabase.table("conversations")\
        .select("user_id")\
        .eq("id", conversation_id)\
        .single()\
        .execute()
        
    if not conv_result.data:
        raise HTTPException(404, "Conversation not found")
        
    if conv_result.data["user_id"] != str(current_user.id):
        raise HTTPException(403, "Not your conversation")
    
    # Get messages
    messages_result = await supabase.table("chat_messages")\
        .select("id, role, content, created_at")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", desc=False)\
        .limit(limit)\
        .execute()
    
    return {
        "conversation_id": conversation_id,
        "messages": messages_result.data
    }