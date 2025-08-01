# src/routers/webhooks.py
# Webhook endpoints for external service integrations
# Processes SendGrid email events and updates tracking data
# RELEVANT FILES: ../database.py, ../schemas.py, ../agent/tools/email_sender.py

import logging
import hmac
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response

from ..database import get_supabase
from ..config import get_settings
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"]
)


def verify_sendgrid_signature(
    request_body: bytes,
    signature: str,
    timestamp: str,
    webhook_key: str
) -> bool:
    """
    Verify SendGrid webhook signature for security.
    
    Args:
        request_body: Raw request body
        signature: SendGrid signature from header
        timestamp: SendGrid timestamp from header
        webhook_key: Webhook verification key from SendGrid
        
    Returns:
        bool: True if signature is valid
    """
    # Decode the signature
    decoded_signature = signature.encode('utf-8')
    
    # Create the payload to verify
    payload = timestamp.encode('utf-8') + request_body
    
    # Compute expected signature
    expected_signature = hmac.new(
        webhook_key.encode('utf-8'),
        payload,
        hashlib.sha256
    ).digest()
    
    # Compare signatures
    return hmac.compare_digest(expected_signature, decoded_signature)


@router.post("/sendgrid")
async def handle_sendgrid_webhook(
    request: Request,
    events: List[Dict[str, Any]]
):
    """
    Handle SendGrid webhook events for email tracking.
    
    SendGrid Event Types:
    - processed: Message has been received by SendGrid
    - delivered: Message was successfully delivered
    - open: Recipient opened the email
    - click: Recipient clicked a link
    - bounce: Message bounced
    - unsubscribe: Recipient unsubscribed
    - spam_report: Recipient marked as spam
    """
    try:
        # Log webhook receipt
        logger.info(f"Received SendGrid webhook with {len(events)} events")
        
        # Get Supabase client
        supabase = await get_supabase()
        
        # Process each event
        processed_count = 0
        error_count = 0
        
        for event in events:
            try:
                await process_sendgrid_event(supabase, event)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process SendGrid event: {e}, Event: {event}")
                error_count += 1
        
        logger.info(f"Processed {processed_count} events successfully, {error_count} errors")
        
        # SendGrid expects 200 OK response
        return Response(status_code=200)
        
    except Exception as e:
        logger.error(f"SendGrid webhook handler error: {e}")
        # Return 200 to prevent SendGrid from retrying
        return Response(status_code=200)


async def process_sendgrid_event(supabase, event: Dict[str, Any]):
    """
    Process a single SendGrid event and update tracking data.
    
    Args:
        supabase: Supabase client
        event: SendGrid event data
    """
    # Extract event data
    event_type = event.get('event')
    
    # SendGrid puts custom args in 'custom_args' or at root level depending on version
    # Try both locations for backwards compatibility
    custom_args = event.get('custom_args', {})
    message_id = event.get('message_id') or custom_args.get('message_id')
    campaign_id = event.get('campaign_id') or custom_args.get('campaign_id')
    lead_id = event.get('lead_id') or custom_args.get('lead_id')
    timestamp = event.get('timestamp', 0)
    
    # Convert timestamp to datetime
    event_time = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    
    # Skip if no message_id (can't track without it)
    if not message_id:
        logger.warning(f"SendGrid event missing message_id: {event}")
        return
    
    # Prepare tracking event data
    tracking_event = {
        "event": event_type,
        "timestamp": event_time,
        "ip": event.get('ip'),
        "user_agent": event.get('useragent'),
        "url": event.get('url'),  # For click events
        "reason": event.get('reason'),  # For bounce events
        "response": event.get('response'),  # For bounce events
        "sg_event_id": event.get('sg_event_id'),
        "sg_message_id": event.get('sg_message_id')
    }
    
    # Get current message data
    message_response = await supabase.table("messages").select(
        "id, tracking_events, send_attempts"
    ).eq("id", message_id).single().execute()
    
    if not message_response.data:
        logger.warning(f"Message not found for ID: {message_id}")
        return
    
    message_data = message_response.data
    current_events = message_data.get('tracking_events', [])
    
    # Append new event
    current_events.append(tracking_event)
    
    # Prepare update data
    update_data = {
        "tracking_events": current_events,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Update specific timestamp fields based on event type
    if event_type == 'delivered':
        update_data['delivered_at'] = event_time
        update_data['status'] = 'delivered'
    elif event_type == 'open':
        update_data['opened_at'] = event_time
    elif event_type == 'click':
        update_data['clicked_at'] = event_time
    elif event_type == 'bounce':
        update_data['bounced_at'] = event_time
        update_data['status'] = 'bounced'
        update_data['send_error'] = tracking_event.get('reason', 'Email bounced')
    elif event_type == 'unsubscribe':
        update_data['unsubscribed_at'] = event_time
        update_data['status'] = 'unsubscribed'
    
    # Update message record
    await supabase.table("messages").update(update_data).eq(
        "id", message_id
    ).execute()
    
    # Update campaign metrics if campaign_id provided
    if campaign_id:
        await update_campaign_metrics(supabase, campaign_id, event_type)
    
    logger.info(f"Processed {event_type} event for message {message_id}")


async def update_campaign_metrics(
    supabase,
    campaign_id: str,
    event_type: str
):
    """
    Update campaign-level email metrics atomically.
    
    Args:
        supabase: Supabase client
        campaign_id: Campaign UUID
        event_type: Type of email event
    """
    try:
        # Get current metrics
        campaign_response = await supabase.table("campaigns").select(
            "email_metrics"
        ).eq("id", campaign_id).single().execute()
        
        if not campaign_response.data:
            logger.warning(f"Campaign not found for metrics update: {campaign_id}")
            return
        
        # Get current metrics or use defaults
        current_metrics = campaign_response.data.get('email_metrics', {
            "sent": 0,
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "bounced": 0,
            "unsubscribed": 0,
            "open_rate": 0,
            "click_rate": 0
        })
        
        # Increment the appropriate metric
        metric_map = {
            'processed': 'sent',
            'delivered': 'delivered',
            'open': 'opened',
            'click': 'clicked',
            'bounce': 'bounced',
            'unsubscribe': 'unsubscribed'
        }
        
        metric_key = metric_map.get(event_type)
        if metric_key:
            current_metrics[metric_key] = current_metrics.get(metric_key, 0) + 1
            
            # Recalculate rates
            if current_metrics['delivered'] > 0:
                current_metrics['open_rate'] = round(
                    (current_metrics['opened'] / current_metrics['delivered']) * 100, 2
                )
                current_metrics['click_rate'] = round(
                    (current_metrics['clicked'] / current_metrics['delivered']) * 100, 2
                )
        
        # Update campaign with new metrics
        await supabase.table("campaigns").update({
            "email_metrics": current_metrics,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", campaign_id).execute()
        
    except Exception as e:
        logger.error(f"Failed to update campaign metrics: {e}")


@router.post("/sendgrid-inbound")
async def handle_sendgrid_inbound_webhook(request: Request):
    """
    Handle SendGrid Inbound Parse webhook for receiving emails from leads.
    
    This endpoint processes emails sent to our reply domain and creates
    inbound message records linked to the appropriate lead and campaign.
    
    SendGrid sends multipart/form-data with parsed email content.
    """
    try:
        # Parse form data from SendGrid
        form_data = await request.form()
        
        # Extract email fields
        from_email = form_data.get('from', '')
        to_email = form_data.get('to', '')
        subject = form_data.get('subject', '')
        text_content = form_data.get('text', '')
        html_content = form_data.get('html', '')
        headers = form_data.get('headers', '')
        
        # Parse sender email address (handle format: "Name <email@domain.com>")
        import re
        email_match = re.search(r'<(.+?)>', from_email)
        if email_match:
            sender_email = email_match.group(1)
        else:
            # Assume the whole string is the email
            sender_email = from_email.strip()
        
        # Extract Message-ID and In-Reply-To from headers
        message_id = None
        in_reply_to = None
        if headers:
            # Parse Message-ID
            message_id_match = re.search(r'Message-ID:\s*<(.+?)>', headers, re.IGNORECASE)
            if message_id_match:
                message_id = f"<{message_id_match.group(1)}>"
            
            # Parse In-Reply-To
            reply_to_match = re.search(r'In-Reply-To:\s*<(.+?)>', headers, re.IGNORECASE)
            if reply_to_match:
                in_reply_to = f"<{reply_to_match.group(1)}>"
        
        # Prepare content (prefer HTML if available)
        content = html_content if html_content else text_content
        
        # Log the incoming email
        logger.info(f"Received inbound email from {sender_email} to {to_email}")
        
        # Get Supabase client
        supabase = await get_supabase()
        
        # Build SendGrid data for storage
        sendgrid_data = {
            "to": to_email,
            "from": from_email,
            "subject": subject,
            "headers": headers[:1000] if headers else None,  # Truncate headers for storage
            "spam_score": form_data.get('spam_score'),
            "spam_report": form_data.get('spam_report'),
            "attachments": form_data.get('attachments', '0')
        }
        
        # Call the database function to process the email
        result = await supabase.rpc('process_inbound_email', {
            'p_from_email': sender_email,
            'p_to_email': to_email,
            'p_subject': subject,
            'p_content': content,
            'p_message_id': message_id,
            'p_in_reply_to': in_reply_to,
            'p_sendgrid_data': sendgrid_data
        }).execute()
        
        # Check if email was processed
        if result.data:
            message_id = result.data
            logger.info(f"Inbound email processed successfully. Message ID: {message_id}")
            
            # TODO: Optionally trigger a job to have AI respond to the email
            # This could be done by creating a job record for the AutopilotAgent
            
            return Response(status_code=200)
        else:
            # Email was rejected (not from a known lead or other validation failure)
            logger.warning(f"Inbound email rejected from {sender_email}")
            return Response(status_code=200)  # Still return 200 to prevent SendGrid retries
    
    except Exception as e:
        logger.error(f"SendGrid inbound webhook error: {e}")
        # Return 200 to prevent SendGrid from retrying
        return Response(status_code=200)