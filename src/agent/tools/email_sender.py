# src/agent/tools/email_sender.py
# Simplified SendGrid email sender tool for automated outreach campaigns
# Handles email sending with per-campaign API keys for multi-client support
# RELEVANT FILES: base_tools.py, database_tools.py, autopilot_agent.py

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

# SendGrid imports
from ..agentops_config import track_tool
from .base_tools import BaseTools, ToolResult

logger = logging.getLogger(__name__)

# SendGrid imports
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Personalization, From, CustomArg, Header
except ImportError:
    SendGridAPIClient = None
    Mail = None
    logger.warning("SendGrid library not installed. Email sending will fail.")


class EmailError:
    """Simplified email error categorization"""
    
    # Error categories
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    INVALID_EMAIL = "invalid_email"
    TEMPORARY_ERROR = "temporary_error"
    PERMANENT_ERROR = "permanent_error"
    UNKNOWN = "unknown"
    
    # Retryable error categories
    RETRYABLE_CATEGORIES = {RATE_LIMIT, TEMPORARY_ERROR}
    
    @classmethod
    def categorize(cls, error_message: str) -> tuple[str, bool]:
        """
        Categorize an error and determine if it's retryable.
        Simplified to focus on key error types.
        """
        error_lower = str(error_message).lower()
        
        # Check for specific error patterns
        if any(code in error_lower for code in ["429", "rate limit", "too many"]):
            return cls.RATE_LIMIT, True
        elif any(code in error_lower for code in ["401", "403", "unauthorized", "invalid api key"]):
            return cls.AUTHENTICATION, False
        elif any(code in error_lower for code in ["550", "invalid email", "bad recipient"]):
            return cls.INVALID_EMAIL, False
        elif any(code in error_lower for code in ["503", "504", "temporary", "timeout"]):
            return cls.TEMPORARY_ERROR, True
        elif any(code in error_lower for code in ["551", "552", "553", "bounce", "permanent"]):
            return cls.PERMANENT_ERROR, False
        
        return cls.UNKNOWN, False


class EmailSender(BaseTools):
    """
    Simplified email sender tool that integrates with SendGrid.
    Supports per-campaign API keys for multi-client environments.
    Uses SendGrid SDK's native features for batch sending and error handling.
    """
    
    # SendGrid rate limits
    RATE_LIMIT_PER_SECOND = 100  # SendGrid allows 100 emails/second
    BATCH_SIZE = 100  # Maximum emails per batch for personalizations
    MAX_RETRIES = 3  # Maximum retry attempts
    
    def __init__(self):
        """Initialize the email sender"""
        super().__init__()
        self.logger = logger
        
    def _create_sendgrid_client(self, api_key: str) -> Optional[SendGridAPIClient]:
        """
        Create a SendGrid client with the provided API key.
        No connection pooling - let SendGrid SDK handle connection management.
        
        Args:
            api_key: SendGrid API key for the campaign
            
        Returns:
            SendGridAPIClient instance or None if invalid
        """
        if not api_key:
            self.logger.error("No SendGrid API key provided")
            return None
        
        try:
            # Create a new client instance - SendGrid SDK handles connection pooling internally
            client = SendGridAPIClient(api_key)
            return client
        except Exception as e:
            self.logger.error(f"Failed to create SendGrid client: {e}")
            return None
    
    @track_tool("send_email")
    async def send_email(
        self,
        message_data: Dict[str, Any],
        api_key: str,
        campaign_footer: Optional[Dict[str, Any]] = None,
        reply_to_domain: Optional[str] = None,
        from_email: str = "noreply@example.com",
        from_name: Optional[str] = None
    ) -> ToolResult:
        """
        Send a single email via SendGrid.
        Simplified to use SendGrid SDK directly.
        """
        sg_client = self._create_sendgrid_client(api_key)
        if not sg_client:
            return ToolResult(
                success=False,
                error="Invalid or missing SendGrid API key"
            )
        
        # Get lead data
        lead_data = await self._get_lead_data(message_data['lead_id'])
        if not lead_data or not lead_data.get('email'):
            return ToolResult(
                success=False,
                error=f"Lead {message_data['lead_id']} not found or missing email"
            )
        
        try:
            # Create personalized content
            personalized_content = self._personalize_text(
                message_data.get('content', ''), lead_data
            )
            formatted_content = self._format_email_content(
                personalized_content, lead_data, campaign_footer
            )
            
            # Create SendGrid message
            message = Mail(
                from_email=From(from_email, from_name),
                subject=self._personalize_text(message_data.get('subject', ''), lead_data),
                html_content=Content("text/html", formatted_content)
            )
            
            # Create personalization for tracking and headers
            personalization = Personalization()
            personalization.add_to(To(lead_data['email']))
            
            # Add custom args for tracking
            personalization.add_custom_arg(CustomArg('message_id', str(message_data['id'])))
            personalization.add_custom_arg(CustomArg('campaign_id', str(message_data.get('campaign_id', ''))))
            personalization.add_custom_arg(CustomArg('lead_id', str(message_data.get('lead_id', ''))))
            
            # Add Reply-To if configured
            if reply_to_domain:
                reply_to_email = f"reply+{message_data['id']}@{reply_to_domain}"
                message.reply_to = Email(reply_to_email)
                # Add headers using Header objects
                personalization.add_header(Header('Message-ID', f"<{message_data['id']}@{reply_to_domain}>"))
            
            message.add_personalization(personalization)
            
            # Send the email
            response = sg_client.send(message)
            
            # Extract SendGrid message ID
            sendgrid_message_id = None
            if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                sendgrid_message_id = response.headers['X-Message-Id']
            
            self.logger.info(f"Email sent to {lead_data['email']}")
            
            return ToolResult(
                success=True,
                data={
                    "message_id": message_data['id'],
                    "sendgrid_message_id": sendgrid_message_id,
                    "status_code": response.status_code,
                    "sent_to": lead_data['email']
                }
            )
            
        except Exception as e:
            error_category, is_retryable = EmailError.categorize(str(e))
            self.logger.error(f"Email send failed: {e}")
            
            return ToolResult(
                success=False,
                error=str(e),
                data={
                    "message_id": message_data['id'],
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
        retry_attempts: int = 0,
        reply_to_domain: Optional[str] = None
    ) -> ToolResult:
        """
        Send multiple emails in batch via SendGrid.
        Simplified to use SendGrid's native batch capabilities.
        
        Args:
            messages: List of message records from database
            api_key: SendGrid API key for the campaign
            campaign_footer: Optional campaign footer configuration  
            from_email: Sender email address
            from_name: Sender display name
            reply_to_domain: Optional domain for reply-to addresses
            
        Returns:
            ToolResult with batch send results
        """
        if not messages:
            return ToolResult(
                success=True,
                data={"sent": 0, "failed": 0, "results": []}
            )
        
        sg_client = self._create_sendgrid_client(api_key)
        if not sg_client:
            return ToolResult(
                success=False,
                error="Invalid or missing SendGrid API key"
            )
        
        results = []
        sent_count = 0
        failed_count = 0
        
        # Process messages in batches respecting SendGrid limits
        for i in range(0, len(messages), self.BATCH_SIZE):
            batch = messages[i:i + self.BATCH_SIZE]
            
            # Send this batch
            batch_result = await self._send_batch_with_personalizations(
                batch, sg_client, campaign_footer, from_email, from_name, reply_to_domain
            )
            
            # Aggregate results
            sent_count += batch_result['sent']
            failed_count += batch_result['failed']
            results.extend(batch_result['results'])
            
            # Rate limit between batches
            if i + self.BATCH_SIZE < len(messages):
                await asyncio.sleep(1)
        
        self.logger.info(
            f"Batch send complete: {sent_count} sent, {failed_count} failed"
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
    
    async def _send_batch_with_personalizations(
        self,
        messages: List[Dict[str, Any]],
        sg_client: SendGridAPIClient,
        campaign_footer: Optional[Dict[str, Any]],
        from_email: str,
        from_name: Optional[str],
        reply_to_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a batch of emails using SendGrid's personalizations.
        Groups messages by content template for efficiency.
        """
        sent = 0
        failed = 0
        results = []
        
        # Group messages by content template
        content_groups = {}
        
        for msg in messages:
            try:
                # Fetch lead data
                lead_data = await self._get_lead_data(msg['lead_id'])
                if not lead_data or not lead_data.get('email'):
                    results.append({
                        "message_id": msg['id'],
                        "error": "Lead not found or missing email",
                        "error_category": EmailError.INVALID_EMAIL,
                        "is_retryable": False
                    })
                    failed += 1
                    continue
                
                # Group by subject and content template
                content_key = f"{msg.get('subject', '')}||{msg.get('content', '')}"
                if content_key not in content_groups:
                    content_groups[content_key] = {
                        'subject_template': msg.get('subject', ''),
                        'content_template': msg.get('content', ''),
                        'recipients': []
                    }
                
                content_groups[content_key]['recipients'].append({
                    'message': msg,
                    'lead': lead_data
                })
                
            except Exception as e:
                error_category, is_retryable = EmailError.categorize(str(e))
                self.logger.error(f"Failed to prepare message {msg['id']}: {e}")
                results.append({
                    "message_id": msg['id'],
                    "error": str(e),
                    "error_category": error_category,
                    "is_retryable": is_retryable
                })
                failed += 1
        
        # Send each content group
        for group_data in content_groups.values():
            if not group_data['recipients']:
                continue
                
            # Create Mail object for this group
            mail = Mail()
            mail.from_email = From(from_email, from_name)
            
            # Use the first message's content as base template
            base_content = self._format_email_content(
                group_data['content_template'],
                {},  # Empty dict for template
                campaign_footer
            )
            mail.add_content(Content("text/html", base_content))
            
            # Add personalizations
            for recipient_data in group_data['recipients']:
                msg = recipient_data['message']
                lead_data = recipient_data['lead']
                
                personalization = Personalization()
                personalization.add_to(To(lead_data['email']))
                
                # Personalized subject
                personalization.subject = self._personalize_text(
                    group_data['subject_template'], lead_data
                )
                
                # Note: We're not using dynamic templates, so we don't need dynamic_template_data
                # The content is already personalized in the message content
                
                # Add tracking using CustomArg objects
                personalization.add_custom_arg(CustomArg('message_id', str(msg['id'])))
                personalization.add_custom_arg(CustomArg('campaign_id', str(msg.get('campaign_id', ''))))
                personalization.add_custom_arg(CustomArg('lead_id', str(msg.get('lead_id', ''))))
                
                # Reply-To header using Header objects
                if reply_to_domain:
                    personalization.add_header(Header('Reply-To', f"reply+{msg['id']}@{reply_to_domain}"))
                    personalization.add_header(Header('Message-ID', f"<{msg['id']}@{reply_to_domain}>"))
                
                mail.add_personalization(personalization)
            
            # Send this batch
            try:
                response = sg_client.send(mail)
                sent += len(mail.personalizations)
                
                sendgrid_message_id = None
                if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                    sendgrid_message_id = response.headers['X-Message-Id']
                
                for personalization in mail.personalizations:
                    # Extract message_id from custom args list of dicts
                    msg_id = None
                    if hasattr(personalization, 'custom_args') and personalization.custom_args:
                        for custom_arg in personalization.custom_args:
                            if 'message_id' in custom_arg:
                                msg_id = custom_arg['message_id']
                                break
                    results.append({
                        "message_id": msg_id,
                        "sendgrid_message_id": sendgrid_message_id,
                        "status_code": response.status_code
                    })
                    
            except Exception as e:
                error_category, is_retryable = EmailError.categorize(str(e))
                self.logger.error(f"Batch send failed: {e}")
                failed += len(mail.personalizations)
                
                for personalization in mail.personalizations:
                    # Extract message_id from custom args list of dicts
                    msg_id = None
                    if hasattr(personalization, 'custom_args') and personalization.custom_args:
                        for custom_arg in personalization.custom_args:
                            if 'message_id' in custom_arg:
                                msg_id = custom_arg['message_id']
                                break
                    results.append({
                        "message_id": msg_id,
                        "error": str(e),
                        "error_category": error_category,
                        "is_retryable": is_retryable
                    })
        
        return {
            'sent': sent,
            'failed': failed,
            'results': results
        }
    
    
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
        Format email content with optional footer.
        Simplified HTML generation.
        """
        # Convert plain text to HTML if needed
        if not content.strip().startswith('<'):
            content = content.replace('\n', '<br>\n')
            content = f"<p>{content}</p>"
        
        # Add footer if enabled
        footer_html = ""
        if campaign_footer and campaign_footer.get('enabled'):
            footer_template = campaign_footer.get('template', '')
            footer_html = f"""
            <hr style="border: 1px solid #eee; margin: 30px 0 20px;">
            <div style="font-size: 12px; color: #666;">
                {self._personalize_text(footer_template, lead_data)}
            </div>
            """
        
        # Simple HTML wrapper
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; padding: 20px;">
            {content}
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
        replacements = self._get_personalization_substitutions(lead_data)
        
        # Replace all variables
        for var, value in replacements.items():
            text = text.replace(var, value or '')
        
        return text
    
    def _get_personalization_substitutions(self, lead_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Get standard personalization substitutions for a lead.
        
        Args:
            lead_data: Lead information
            
        Returns:
            Dictionary of variable names to values
        """
        return {
            '{{first_name}}': lead_data.get('first_name', ''),
            '{{last_name}}': lead_data.get('last_name', ''),
            '{{full_name}}': f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            '{{company}}': lead_data.get('company', ''),
            '{{title}}': lead_data.get('title', ''),
            '{{email}}': lead_data.get('email', '')
        }
    
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
    
    
    async def retry_failed_messages(
        self,
        failed_results: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        api_key: str,
        campaign_footer: Optional[Dict[str, Any]] = None,
        from_email: str = "noreply@example.com",
        from_name: Optional[str] = None,
        reply_to_domain: Optional[str] = None
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
            reply_to_domain: Optional domain for reply-to addresses
            
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
            retry_attempts=1,
            reply_to_domain=reply_to_domain
        )