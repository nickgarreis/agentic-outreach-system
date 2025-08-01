# src/agent/tools/email_sender.py
# SendGrid email sender tool for automated outreach campaigns
# Handles email sending, tracking, and error management
# RELEVANT FILES: base_tools.py, database_tools.py, message_scheduler.py

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import asyncio

# SendGrid imports
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Personalization
except ImportError:
    SendGridAPIClient = None
    Mail = None
    logger.warning("SendGrid library not installed. Email sending will fail.")

from ..agentops_config import track_tool
from .base_tools import BaseTools, ToolResult

logger = logging.getLogger(__name__)


class EmailError:
    """Email error categorization for better error handling"""
    
    # Error categories
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    INVALID_EMAIL = "invalid_email"
    CONTENT_ERROR = "content_error"
    NETWORK_ERROR = "network_error"
    TEMPORARY_ERROR = "temporary_error"
    PERMANENT_ERROR = "permanent_error"
    UNKNOWN = "unknown"
    
    # Error patterns for categorization
    ERROR_PATTERNS = {
        RATE_LIMIT: ["rate limit", "too many requests", "429"],
        AUTHENTICATION: ["unauthorized", "invalid api key", "401", "403"],
        INVALID_EMAIL: ["invalid email", "bad recipient", "invalid address", "550"],
        CONTENT_ERROR: ["content", "spam", "blocked", "rejected"],
        NETWORK_ERROR: ["connection", "timeout", "network", "dns"],
        TEMPORARY_ERROR: ["temporary", "try again", "503", "504"],
        PERMANENT_ERROR: ["permanent", "bounce", "551", "552", "553"]
    }
    
    @classmethod
    def categorize(cls, error_message: str) -> tuple[str, bool]:
        """
        Categorize an error message and determine if it's retryable.
        
        Args:
            error_message: The error message to categorize
            
        Returns:
            Tuple of (category, is_retryable)
        """
        error_lower = str(error_message).lower()
        
        # Check each category pattern
        for category, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern in error_lower:
                    # Determine if retryable based on category
                    is_retryable = category in [
                        cls.RATE_LIMIT, 
                        cls.NETWORK_ERROR, 
                        cls.TEMPORARY_ERROR
                    ]
                    return category, is_retryable
        
        # Default to unknown, not retryable
        return cls.UNKNOWN, False


class EmailSender(BaseTools):
    """
    Email sender tool that integrates with SendGrid.
    Handles batch sending, tracking, and error management.
    """
    
    # SendGrid rate limits
    RATE_LIMIT_PER_SECOND = 100  # SendGrid allows 100 emails/second
    BATCH_SIZE = 100  # Maximum emails per batch
    MAX_RETRIES = 3  # Maximum retry attempts
    
    # Connection pool settings
    MAX_POOL_SIZE = 10  # Maximum number of SendGrid clients per API key
    POOL_TIMEOUT = 300  # Client expiration time in seconds (5 minutes)
    
    def __init__(self):
        """Initialize the email sender"""
        super().__init__()
        self.logger = logger
        self._api_clients = {}  # Cache SendGrid clients by API key
        self._client_timestamps = {}  # Track client creation times
        self._client_usage_count = {}  # Track usage for round-robin
        
    def _get_sendgrid_client(self, api_key: str) -> Optional[SendGridAPIClient]:
        """
        Get or create a SendGrid client from the connection pool.
        Implements round-robin load balancing and connection recycling.
        
        Args:
            api_key: SendGrid API key
            
        Returns:
            SendGridAPIClient instance or None if invalid
        """
        if not api_key:
            self.logger.error("No SendGrid API key provided")
            return None
        
        current_time = datetime.utcnow().timestamp()
        
        # Initialize pool for this API key if needed
        if api_key not in self._api_clients:
            self._api_clients[api_key] = []
            self._client_timestamps[api_key] = []
            self._client_usage_count[api_key] = 0
        
        # Clean up expired clients
        self._cleanup_expired_clients(api_key, current_time)
        
        # Get existing client or create new one
        client_pool = self._api_clients[api_key]
        
        if client_pool:
            # Round-robin selection
            index = self._client_usage_count[api_key] % len(client_pool)
            self._client_usage_count[api_key] += 1
            return client_pool[index]
        
        # Create new client if pool is empty or below max size
        if len(client_pool) < self.MAX_POOL_SIZE:
            try:
                client = SendGridAPIClient(api_key)
                self._api_clients[api_key].append(client)
                self._client_timestamps[api_key].append(current_time)
                self.logger.info(f"Created new SendGrid client (pool size: {len(client_pool) + 1})")
                return client
            except Exception as e:
                self.logger.error(f"Failed to create SendGrid client: {e}")
                return None
        
        # Pool is at max size, return least recently used
        return client_pool[0]
    
    def _cleanup_expired_clients(self, api_key: str, current_time: float):
        """
        Remove expired clients from the pool.
        
        Args:
            api_key: SendGrid API key
            current_time: Current timestamp
        """
        if api_key not in self._client_timestamps:
            return
        
        # Find indices of non-expired clients
        valid_indices = [
            i for i, timestamp in enumerate(self._client_timestamps[api_key])
            if current_time - timestamp < self.POOL_TIMEOUT
        ]
        
        # Keep only valid clients
        if len(valid_indices) < len(self._api_clients[api_key]):
            self._api_clients[api_key] = [
                self._api_clients[api_key][i] for i in valid_indices
            ]
            self._client_timestamps[api_key] = [
                self._client_timestamps[api_key][i] for i in valid_indices
            ]
            self.logger.info(
                f"Cleaned up {len(self._api_clients[api_key]) - len(valid_indices)} "
                f"expired clients for API key ending in ...{api_key[-4:]}"
            )
    
    @track_tool("send_email")
    async def send_email(
        self,
        message_data: Dict[str, Any],
        api_key: str,
        campaign_footer: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Send a single email via SendGrid.
        
        Args:
            message_data: Message record from database
            api_key: SendGrid API key
            campaign_footer: Optional campaign footer configuration
            
        Returns:
            ToolResult with send status and tracking info
        """
        try:
            sg_client = self._get_sendgrid_client(api_key)
            if not sg_client:
                return ToolResult(
                    success=False,
                    error="Invalid or missing SendGrid API key"
                )
            
            # Get lead data for personalization
            lead_data = await self._get_lead_data(message_data['lead_id'])
            if not lead_data:
                return ToolResult(
                    success=False,
                    error=f"Lead {message_data['lead_id']} not found"
                )
            
            # Format email content with personalization
            formatted_content = self._format_email_content(
                content=message_data['content'],
                lead_data=lead_data,
                campaign_footer=campaign_footer
            )
            
            # Create SendGrid message
            message = Mail(
                from_email=Email("noreply@example.com"),  # TODO: Make this configurable
                to_emails=To(lead_data['email']),
                subject=self._personalize_text(message_data['subject'], lead_data),
                html_content=Content("text/html", formatted_content)
            )
            
            # Send email
            response = sg_client.send(message)
            
            # Extract message ID from response headers
            sendgrid_message_id = None
            if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                sendgrid_message_id = response.headers['X-Message-Id']
            
            self.logger.info(
                f"Email sent successfully to {lead_data['email']} "
                f"(Message ID: {sendgrid_message_id})"
            )
            
            return ToolResult(
                success=True,
                data={
                    "message_id": message_data['id'],
                    "sendgrid_message_id": sendgrid_message_id,
                    "status_code": response.status_code,
                    "sent_to": lead_data['email'],
                    "sent_at": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            error_category, is_retryable = EmailError.categorize(error_msg)
            
            self.logger.error(
                f"Failed to send email: {e} "
                f"(Category: {error_category}, Retryable: {is_retryable})"
            )
            
            return ToolResult(
                success=False,
                error=error_msg,
                data={
                    "message_id": message_data['id'],
                    "error_type": type(e).__name__,
                    "error_category": error_category,
                    "is_retryable": is_retryable
                }
            )
    
    @track_tool("send_batch_emails")
    async def send_batch_emails(
        self,
        messages: List[Dict[str, Any]],
        api_key: str,
        campaign_footer: Optional[Dict[str, Any]] = None,
        from_email: str = "noreply@example.com",
        from_name: Optional[str] = None,
        retry_attempts: int = 0
    ) -> ToolResult:
        """
        Send multiple emails in batch via SendGrid using personalizations.
        
        Args:
            messages: List of message records from database
            api_key: SendGrid API key
            campaign_footer: Optional campaign footer configuration
            from_email: Sender email address
            from_name: Sender name
            
        Returns:
            ToolResult with batch send results
        """
        try:
            if not messages:
                return ToolResult(
                    success=True,
                    data={"sent": 0, "failed": 0, "results": []}
                )
            
            sg_client = self._get_sendgrid_client(api_key)
            if not sg_client:
                return ToolResult(
                    success=False,
                    error="Invalid or missing SendGrid API key"
                )
            
            # Process in chunks to respect rate limits
            results = []
            sent_count = 0
            failed_count = 0
            
            # Process messages in batches using SendGrid's batch API
            for i in range(0, len(messages), self.BATCH_SIZE):
                batch = messages[i:i + self.BATCH_SIZE]
                
                # Use asyncio.to_thread for true async with sync SDK
                batch_result = await asyncio.to_thread(
                    self._send_batch_with_personalizations,
                    batch, sg_client, campaign_footer, from_email, from_name
                )
                
                # Process results
                sent_count += batch_result['sent']
                failed_count += batch_result['failed']
                results.extend(batch_result['results'])
                
                # Rate limiting - ensure we don't exceed 100 emails/second
                if i + self.BATCH_SIZE < len(messages):
                    await asyncio.sleep(1)  # Wait 1 second between batches
            
            self.logger.info(
                f"Batch email send completed: {sent_count} sent, {failed_count} failed"
            )
            
            return ToolResult(
                success=True,
                data={
                    "sent": sent_count,
                    "failed": failed_count,
                    "total": len(messages),
                    "results": results
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            error_category, is_retryable = EmailError.categorize(error_msg)
            self.logger.error(
                f"Batch email send failed: {e} "
                f"(Category: {error_category}, Retryable: {is_retryable})"
            )
            return ToolResult(
                success=False,
                error=f"Batch send failed: {error_msg}",
                data={
                    "error_category": error_category,
                    "is_retryable": is_retryable
                }
            )
    
    def _send_batch_with_personalizations(
        self,
        messages: List[Dict[str, Any]],
        sg_client: SendGridAPIClient,
        campaign_footer: Optional[Dict[str, Any]],
        from_email: str,
        from_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Send a batch of emails using SendGrid's personalizations feature.
        This runs in a thread for async compatibility.
        Optimized version that groups messages with identical content.
        """
        from sendgrid.helpers.mail import Mail, From, Personalization, To, Content
        
        sent = 0
        failed = 0
        results = []
        
        # Group messages by content hash to optimize sending
        content_groups = {}
        
        # First, fetch all lead data and group by content
        for msg in messages:
            try:
                lead_data = self._get_lead_data_sync(msg['lead_id'])
                if not lead_data or not lead_data.get('email'):
                    results.append({
                        "message_id": msg['id'],
                        "error": "Lead data not found or missing email",
                        "error_category": "invalid_email",
                        "is_retryable": False
                    })
                    failed += 1
                    continue
                
                # Create content hash for grouping
                content_key = f"{msg.get('subject', '')}||{msg.get('content', '')}"
                
                if content_key not in content_groups:
                    content_groups[content_key] = {
                        'subject': msg.get('subject', ''),
                        'content': msg.get('content', ''),
                        'recipients': []
                    }
                
                content_groups[content_key]['recipients'].append({
                    'message': msg,
                    'lead': lead_data
                })
                
            except Exception as e:
                error_msg = str(e)
                error_category, is_retryable = EmailError.categorize(error_msg)
                self.logger.error(f"Failed to fetch lead data for message {msg['id']}: {e}")
                results.append({
                    "message_id": msg['id'],
                    "error": error_msg,
                    "error_category": error_category,
                    "is_retryable": is_retryable
                })
                failed += 1
        
        # Send each content group as a batch
        for content_key, group_data in content_groups.items():
            if not group_data['recipients']:
                continue
            
            # Create Mail object for this content group
            mail = Mail()
            mail.from_email = From(from_email, from_name)
            
            # Use the content as template with placeholders
            content_template = group_data['content']
            formatted_content = self._format_email_content(
                content_template,
                {},  # Leave placeholders for substitution
                campaign_footer
            )
            mail.add_content(Content("text/html", formatted_content))
            
            # Add personalizations for all recipients with same content
            for recipient_data in group_data['recipients']:
                msg = recipient_data['message']
                lead_data = recipient_data['lead']
                
                try:
                    # Create personalization
                    personalization = Personalization()
                    personalization.add_to(To(lead_data['email']))
                    
                    # Set personalized subject
                    personalization.subject = self._personalize_text(
                        group_data['subject'], lead_data
                    )
                    
                    # Add substitutions for dynamic content
                    substitutions = {
                        '{{first_name}}': lead_data.get('first_name', ''),
                        '{{last_name}}': lead_data.get('last_name', ''),
                        '{{full_name}}': f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
                        '{{company}}': lead_data.get('company', ''),
                        '{{title}}': lead_data.get('title', ''),
                        '{{email}}': lead_data.get('email', '')
                    }
                    
                    for key, value in substitutions.items():
                        personalization.add_substitution(key, value)
                    
                    # Add custom args for tracking
                    personalization.add_custom_arg('message_id', str(msg['id']))
                    personalization.add_custom_arg('campaign_id', str(msg.get('campaign_id', '')))
                    personalization.add_custom_arg('lead_id', str(msg.get('lead_id', '')))
                    
                    mail.add_personalization(personalization)
                    
                except Exception as e:
                    error_msg = str(e)
                    error_category, is_retryable = EmailError.categorize(error_msg)
                    self.logger.error(f"Failed to add personalization for message {msg['id']}: {e}")
                    results.append({
                        "message_id": msg['id'],
                        "error": error_msg,
                        "error_category": error_category,
                        "is_retryable": is_retryable
                    })
                    failed += 1
            
            # Send this batch if it has personalizations
            if mail.personalizations:
                try:
                    # Send the batch
                    response = sg_client.send(mail)
                    
                    # All personalizations sent successfully
                    sent += len(mail.personalizations)
                    
                    # Extract message ID if available
                    sendgrid_message_id = None
                    if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                        sendgrid_message_id = response.headers['X-Message-Id']
                    
                    # Add success results for each message
                    for personalization in mail.personalizations:
                        msg_id = personalization.custom_args.get('message_id')
                        results.append({
                            "message_id": msg_id,
                            "sendgrid_message_id": sendgrid_message_id,
                            "status_code": response.status_code
                        })
                    
                except Exception as e:
                    error_msg = str(e)
                    error_category, is_retryable = EmailError.categorize(error_msg)
                    self.logger.error(f"Batch send failed: {e}")
                    failed += len(mail.personalizations)
                    for personalization in mail.personalizations:
                        msg_id = personalization.custom_args.get('message_id')
                        results.append({
                            "message_id": msg_id,
                            "error": error_msg,
                            "error_category": error_category,
                            "is_retryable": is_retryable
                        })
        
        return {
            'sent': sent,
            'failed': failed,
            'results': results
        }
    
    def _get_lead_data_sync(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous version of lead data fetching for use in threads.
        Uses a synchronous Supabase client to avoid event loop issues.
        """
        try:
            # Import sync client only when needed
            from supabase import create_client
            from ...config import get_settings
            
            settings = get_settings()
            
            # Create sync Supabase client
            sync_client = create_client(
                settings.supabase_url,
                settings.supabase_publishable_key
            )
            
            # Fetch lead data synchronously
            response = sync_client.table("leads")\
                .select("*")\
                .eq("id", lead_id)\
                .single()\
                .execute()
            
            return response.data
        except Exception as e:
            self.logger.error(f"Failed to fetch lead data sync: {e}")
            return None
    
    async def _get_lead_data(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch lead data for personalization.
        
        Args:
            lead_id: Lead UUID
            
        Returns:
            Lead data dictionary or None
        """
        try:
            client = await self._get_client()
            response = await client.table("leads")\
                .select("*")\
                .eq("id", lead_id)\
                .single()\
                .execute()
            return response.data
        except Exception as e:
            self.logger.error(f"Failed to fetch lead data: {e}")
            return None
    
    def _format_email_content(
        self,
        content: str,
        lead_data: Dict[str, Any],
        campaign_footer: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format email content with personalization and footer.
        
        Args:
            content: Raw email content
            lead_data: Lead information for personalization
            campaign_footer: Campaign footer configuration
            
        Returns:
            Formatted HTML email content
        """
        # Personalize content
        personalized_content = self._personalize_text(content, lead_data)
        
        # Convert plain text to HTML if needed
        if not personalized_content.strip().startswith('<'):
            # Simple plain text to HTML conversion
            personalized_content = personalized_content.replace('\n', '<br>\n')
            personalized_content = f"<p>{personalized_content}</p>"
        
        # Add campaign footer if configured
        footer_html = ""
        if campaign_footer and campaign_footer.get('enabled'):
            footer_template = campaign_footer.get('template', '')
            footer_html = f"""
            <br><br>
            <hr style="border: 1px solid #eee;">
            <div style="margin-top: 20px; font-size: 12px; color: #666;">
                {self._personalize_text(footer_template, lead_data)}
            </div>
            """
        
        # Wrap in basic HTML template
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            {personalized_content}
            {footer_html}
        </body>
        </html>
        """
    
    def _personalize_text(self, text: str, lead_data: Dict[str, Any]) -> str:
        """
        Replace personalization variables in text.
        
        Args:
            text: Text with {{variable}} placeholders
            lead_data: Lead data for replacement
            
        Returns:
            Personalized text
        """
        # Common personalization variables
        replacements = {
            '{{first_name}}': lead_data.get('first_name', ''),
            '{{last_name}}': lead_data.get('last_name', ''),
            '{{full_name}}': f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            '{{company}}': lead_data.get('company', ''),
            '{{title}}': lead_data.get('title', ''),
            '{{email}}': lead_data.get('email', '')
        }
        
        # Replace all variables
        for var, value in replacements.items():
            text = text.replace(var, value or '')
        
        return text
    
    @track_tool("update_message_status")
    async def update_message_status(
        self,
        message_id: str,
        status: str,
        sendgrid_message_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> ToolResult:
        """
        Update message status after send attempt.
        
        Args:
            message_id: Message UUID
            status: New status (sent/failed)
            sendgrid_message_id: SendGrid tracking ID
            error: Error message if failed
            
        Returns:
            ToolResult with update status
        """
        try:
            client = await self._get_client()
            
            update_data = {
                "status": status,
                "last_send_attempt_at": datetime.utcnow().isoformat()
            }
            
            # Increment send attempts
            message_response = await client.table("messages")\
                .select("send_attempts")\
                .eq("id", message_id)\
                .single()\
                .execute()
            
            current_attempts = message_response.data.get("send_attempts", 0) if message_response.data else 0
            update_data["send_attempts"] = current_attempts + 1
            
            if status == "sent":
                update_data["sent_at"] = datetime.utcnow().isoformat()
                if sendgrid_message_id:
                    update_data["sendgrid_message_id"] = sendgrid_message_id
            elif status == "failed" and error:
                update_data["send_error"] = error
            
            # Update message
            await client.table("messages")\
                .update(update_data)\
                .eq("id", message_id)\
                .execute()
            
            return ToolResult(
                success=True,
                data={"message_id": message_id, "status": status}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update message status: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to update status: {str(e)}"
            )
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics for monitoring.
        
        Returns:
            Dictionary with pool statistics per API key
        """
        stats = {}
        for api_key in self._api_clients:
            # Mask API key for security
            masked_key = f"...{api_key[-8:]}" if len(api_key) > 8 else "***"
            stats[masked_key] = {
                "pool_size": len(self._api_clients.get(api_key, [])),
                "total_requests": self._client_usage_count.get(api_key, 0),
                "oldest_client_age": None
            }
            
            # Calculate oldest client age
            if api_key in self._client_timestamps and self._client_timestamps[api_key]:
                oldest_timestamp = min(self._client_timestamps[api_key])
                age_seconds = datetime.utcnow().timestamp() - oldest_timestamp
                stats[masked_key]["oldest_client_age"] = round(age_seconds, 2)
        
        return stats
    
    async def retry_failed_messages(
        self,
        failed_results: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        api_key: str,
        campaign_footer: Optional[Dict[str, Any]] = None,
        from_email: str = "noreply@example.com",
        from_name: Optional[str] = None
    ) -> ToolResult:
        """
        Retry sending messages that failed with retryable errors.
        
        Args:
            failed_results: List of failed message results with error categorization
            messages: Original message list
            api_key: SendGrid API key
            campaign_footer: Optional campaign footer
            from_email: Sender email
            from_name: Sender name
            
        Returns:
            ToolResult with retry results
        """
        # Filter retryable messages
        retryable_message_ids = {
            result['message_id'] 
            for result in failed_results 
            if result.get('is_retryable', False)
        }
        
        if not retryable_message_ids:
            return ToolResult(
                success=True,
                data={"retried": 0, "message": "No retryable messages"}
            )
        
        # Get retryable messages
        retryable_messages = [
            msg for msg in messages 
            if msg['id'] in retryable_message_ids
        ]
        
        self.logger.info(f"Retrying {len(retryable_messages)} failed messages")
        
        # Wait before retry (exponential backoff)
        await asyncio.sleep(2)
        
        # Retry with updated attempt counter
        return await self.send_batch_emails(
            messages=retryable_messages,
            api_key=api_key,
            campaign_footer=campaign_footer,
            from_email=from_email,
            from_name=from_name,
            retry_attempts=1
        )