# src/agent/autopilot_agent.py
# Main AutopilotAgent implementation with AgentOps monitoring
# Provides a framework for autonomous job execution
# RELEVANT FILES: tools.py, ../config/agentops_config.py, ../database.py

import agentops
import logging
from typing import Dict, Any
from datetime import datetime
from openai import AsyncOpenAI

from ..config import get_settings
from .agentops_config import (
    track_operation,
)
from .tools import DatabaseTools, ApolloSearchTool, ApolloEnrichTool, TavilyTool, OutreachGenerator, MessageScheduler, EmailSender
from ..database import get_supabase

logger = logging.getLogger(__name__)


def is_placeholder_email(email: str) -> bool:
    """
    Check if an email is a placeholder.
    
    Args:
        email: Email address to check
        
    Returns:
        bool: True if email is a placeholder
    """
    if not email:
        return True
        
    email_lower = email.lower()
    placeholders = [
        'placeholder.com',
        'email_not_unlocked@domain.com',
        'example.com',
        'noemail@',
        'unknown@'
    ]
    
    return any(placeholder in email_lower for placeholder in placeholders)


@agentops.agent
class AutopilotAgent:
    """
    Main agent class for executing autonomous tasks.
    Decorated with @agentops.agent for full observability.
    """

    def __init__(self, job_type: str, job_id: str):
        """
        Initialize AutopilotAgent with job context.

        Args:
            job_type: Type of job to execute
            job_id: Unique identifier for the job
        """
        self.job_type = job_type
        self.job_id = job_id
        self.settings = get_settings()

        # Initialize tool sets
        self.db_tools = DatabaseTools()
        
        # Initialize individual tools
        self.apollo_search = ApolloSearchTool()
        self.apollo_enrich = ApolloEnrichTool()
        self.tavily_tool = TavilyTool()
        self.outreach_generator = OutreachGenerator()
        self.message_scheduler = MessageScheduler()
        self.email_sender = EmailSender()

        # For backwards compatibility
        self.tools = self.db_tools

        # Initialize OpenAI client for OpenRouter
        self.client = AsyncOpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )

        # Agent configuration
        self.model = "anthropic/claude-3-5-sonnet"  # Can be made configurable
        self.temperature = 0.7
        self.max_tokens = 4000

        logger.info(f"Initialized AutopilotAgent for {job_type} job: {job_id}")

    @track_operation("execute_job")
    async def execute_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for job execution.
        Override this method or add job type handlers as needed.

        Args:
            job_data: Job configuration and parameters

        Returns:
            dict: Job execution results
        """
        logger.info(f"Starting job execution: {self.job_type}")

        try:
            # Route to appropriate job handler based on job type
            if self.job_type == "campaign_active":
                result = await self._handle_campaign_active(job_data)
            elif self.job_type == "lead_research":
                result = await self._handle_lead_research(job_data)
            elif self.job_type == "lead_outreach":
                result = await self._handle_lead_outreach(job_data)
            elif self.job_type == "send_email":
                result = await self._handle_send_email(job_data)
            elif self.job_type == "lead_enrichment":
                result = await self._handle_lead_enrichment(job_data)
            else:
                # Unknown job type
                result = {
                    "message": f"Job type '{self.job_type}' execution framework ready",
                    "job_data_received": job_data,
                    "status": "framework_only",
                }

            logger.info(f"Job execution completed: {self.job_id}")
            return {
                "success": True,
                "job_id": self.job_id,
                "job_type": self.job_type,
                "result": result,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            return {
                "success": False,
                "job_id": self.job_id,
                "job_type": self.job_type,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            }

    @track_operation("handle_campaign_active")
    async def _handle_campaign_active(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle campaign_active job type - discover leads using configured search platforms.
        
        Args:
            job_data: Contains campaign_id, campaign_name, and platform_urls
            
        Returns:
            dict: Job execution results including leads found
        """
        campaign_id = job_data.get("campaign_id")
        campaign_name = job_data.get("campaign_name", "Unknown")
        platform_urls = job_data.get("platform_urls", {})
        
        logger.info(f"Starting lead discovery for campaign: {campaign_name} ({campaign_id})")
        
        # Check if Apollo is configured
        if "apollo" not in platform_urls:
            raise Exception("No Apollo search URL configured for this campaign")
        
        apollo_config = platform_urls["apollo"]
        search_url = apollo_config.get("search_url")
        page_number = apollo_config.get("page_number", 1)
        
        if not search_url:
            raise Exception("Apollo search URL is empty")
        
        logger.info(f"Executing Apollo search for page {page_number}")
        
        # Execute Apollo search
        search_result = await self.apollo_search.execute(
            search_url=search_url,
            page_number=page_number
        )
        
        if not search_result.success:
            # Job fails with the specific error from Apollo tool
            raise Exception(search_result.error)
        
        # Extract leads from search results
        leads_data = search_result.data.get("people", [])
        
        logger.info(f"Apollo search returned {len(leads_data)} leads")
        
        # Save leads to database
        leads_created = 0
        supabase = await get_supabase()
        
        for lead_data in leads_data:
            try:
                # Extract lead information
                lead_info = self.apollo_search._extract_lead_data(lead_data)
                
                # Add source tracking
                lead_info["full_context"]["source"] = "apollo_search"
                lead_info["full_context"]["source_details"] = {
                    "platform": "apollo",
                    "search_page": page_number,
                    "discovered_at": datetime.utcnow().isoformat(),
                    "search_url": search_url
                }
                
                # Create new lead with discovered status
                lead_info["campaign_id"] = campaign_id
                lead_info["client_id"] = job_data.get("client_id")  # If provided
                lead_info["status"] = "discovered"
                
                await supabase.table("leads").insert(lead_info).execute()
                leads_created += 1
                
                logger.info(f"Discovered lead: {lead_info.get('first_name')} {lead_info.get('last_name')} - Enrichment job will be created automatically")
                
            except Exception as e:
                logger.error(f"Failed to save lead: {e}")
                # Continue with other leads even if one fails
        
        # Update campaign's page number for next run
        await self._update_campaign_page_number(campaign_id, "apollo", page_number + 1)
        
        # Update campaign's total leads discovered
        if leads_created > 0:
            try:
                await supabase.rpc("increment_campaign_leads", {
                    "campaign_uuid": campaign_id,
                    "increment_by": leads_created
                }).execute()
                logger.info(f"Updated campaign total_leads_discovered by {leads_created}")
            except Exception as e:
                logger.error(f"Failed to update campaign lead count: {e}")
        
        logger.info(f"Lead discovery completed: {leads_created} new leads created")
        
        return {
            "leads_found": len(leads_data),
            "leads_created": leads_created,
            "next_page": page_number + 1,
            "platform": "apollo"
        }
    
    async def _update_campaign_page_number(self, campaign_id: str, platform: str, new_page: int):
        """
        Update the page number for a platform in campaign search_url.
        
        Args:
            campaign_id: Campaign UUID
            platform: Platform name (e.g., "apollo")
            new_page: New page number to set
        """
        supabase = await get_supabase()
        
        # Fetch current search_url
        campaign_response = await supabase.table("campaigns").select("search_url").eq(
            "id", campaign_id
        ).single().execute()
        
        if not campaign_response.data:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        search_url = campaign_response.data.get("search_url", {})
        
        # Update page number for the platform
        if platform in search_url:
            search_url[platform]["page_number"] = new_page
        
        # Save back to database
        await supabase.table("campaigns").update({
            "search_url": search_url
        }).eq("id", campaign_id).execute()
        
        logger.info(f"Updated {platform} page number to {new_page} for campaign {campaign_id}")
    
    @track_operation("handle_lead_research")
    async def _handle_lead_research(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle lead_research job type - research leads using Tavily.
        
        Args:
            job_data: Contains lead_id to research
            
        Returns:
            dict: Job execution results including research data
        """
        lead_id = job_data.get("lead_id")
        
        if not lead_id:
            raise Exception("lead_id is required for lead_research job")
        
        logger.info(f"Starting lead research for lead: {lead_id}")
        
        # Get lead data from database
        supabase = await get_supabase()
        lead_response = await supabase.table("leads").select("*").eq(
            "id", lead_id
        ).single().execute()
        
        if not lead_response.data:
            raise Exception(f"Lead {lead_id} not found")
        
        lead_data = lead_response.data
        campaign_id = lead_data.get("campaign_id")
        
        # Get campaign data for context
        campaign_response = await supabase.table("campaigns").select("*").eq(
            "id", campaign_id
        ).single().execute()
        
        campaign_data = campaign_response.data if campaign_response.data else {}
        
        logger.info(f"Researching lead: {lead_data.get('first_name')} {lead_data.get('last_name')} at {lead_data.get('company')}")
        
        # Execute Tavily research
        research_result = await self.tavily_tool.execute(
            lead_data=lead_data,
            campaign_data=campaign_data
        )
        
        if not research_result.success:
            raise Exception(f"Tavily research failed: {research_result.error}")
        
        # Check if we have LinkedIn URL and extract additional content
        linkedin_url = lead_data.get("full_context", {}).get("linkedin_url")
        if linkedin_url:
            logger.info(f"Extracting LinkedIn profile content for {linkedin_url}")
            
            try:
                extract_result = await self.tavily_tool.extract_from_urls(
                    urls=[linkedin_url],
                    extract_depth="advanced"  # Use advanced for LinkedIn
                )
                
                if extract_result.success:
                    # Add LinkedIn extraction to research data
                    research_result.data["linkedin_extraction"] = extract_result.data
                    
                    # Enhance research data with parsed LinkedIn information
                    research_result.data = self.tavily_tool._enhance_research_with_linkedin(
                        research_result.data,
                        extract_result.data
                    )
                    
                    logger.info("Successfully extracted and parsed LinkedIn profile content")
            except Exception as e:
                logger.warning(f"Failed to extract LinkedIn content: {e}")
        
        # Update lead with research data
        existing_context = lead_data.get("full_context", {})
        
        # Merge research data into full_context
        updated_context = {
            **existing_context,
            "tavily_research": research_result.data,
            "researched_at": datetime.utcnow().isoformat()
        }
        
        # Update lead in database
        await supabase.table("leads").update({
            "full_context": updated_context,
            "status": "researched"
        }).eq("id", lead_id).execute()
        
        logger.info(f"Lead research completed for {lead_id}")
        
        # Log credit usage for monitoring
        credit_report = self.tavily_tool.get_credit_usage_report()
        logger.info(f"Tavily credit usage - Total: {credit_report['total_credits_used']}, "
                   f"Estimated cost: ${credit_report['estimated_cost']:.2f}")
        
        return {
            "lead_id": lead_id,
            "lead_name": f"{lead_data.get('first_name')} {lead_data.get('last_name')}",
            "company": lead_data.get("company"),
            "research_summary": research_result.data.get("summary", {}),
            "status": "researched",
            "credit_usage": credit_report
        }
    
    @track_operation("handle_lead_outreach")
    async def _handle_lead_outreach(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle lead_outreach job type - generate and schedule personalized outreach messages.
        
        Args:
            job_data: Contains lead_id, campaign_id, and channel settings
            
        Returns:
            dict: Job execution results including scheduled messages
        """
        lead_id = job_data.get("lead_id")
        campaign_id = job_data.get("campaign_id")
        enabled_channels = job_data.get("enabled_channels", {})
        daily_limits = job_data.get("daily_limits", {})
        
        if not lead_id or not campaign_id:
            raise Exception("lead_id and campaign_id are required for lead_outreach job")
        
        logger.info(f"Starting outreach generation for lead: {lead_id}")
        
        # Get lead data from database
        supabase = await get_supabase()
        lead_response = await supabase.table("leads").select("*").eq(
            "id", lead_id
        ).single().execute()
        
        if not lead_response.data:
            raise Exception(f"Lead {lead_id} not found")
        
        lead_data = lead_response.data
        
        # Get campaign data for context
        campaign_response = await supabase.table("campaigns").select("*").eq(
            "id", campaign_id
        ).single().execute()
        
        if not campaign_response.data:
            raise Exception(f"Campaign {campaign_id} not found")
        
        campaign_data = campaign_response.data
        
        logger.info(
            f"Generating outreach for {lead_data.get('first_name')} {lead_data.get('last_name')} "
            f"at {lead_data.get('company')} - Channels: {list(enabled_channels.keys())}"
        )
        
        # Generate personalized outreach sequences
        generation_result = await self.outreach_generator.generate_outreach_sequence(
            lead_data=lead_data,
            campaign_data=campaign_data,
            enabled_channels=enabled_channels
        )
        
        if not generation_result.success:
            raise Exception(f"Failed to generate outreach: {generation_result.error}")
        
        sequences = generation_result.data.get("sequences", {})
        
        logger.info(f"Generated {generation_result.data.get('total_messages')} messages")
        
        # Schedule messages respecting constraints
        scheduling_result = await self.message_scheduler.schedule_outreach_messages(
            sequences=sequences,
            campaign_id=campaign_id,
            lead_id=lead_id,
            daily_limits=daily_limits
        )
        
        if not scheduling_result.success:
            raise Exception(f"Failed to schedule messages: {scheduling_result.error}")
        
        scheduled_messages = scheduling_result.data.get("scheduled_messages", [])
        
        # Bulk create messages in database
        messages_with_ids = []
        if scheduled_messages:
            create_result = await self.db_tools.bulk_schedule_messages(scheduled_messages)
            
            if not create_result.get("success"):
                raise Exception(f"Failed to create messages: {create_result.get('error')}")
            
            # Get the created messages with their IDs
            messages_with_ids = create_result.get("messages", [])
            
            logger.info(
                f"Successfully created {create_result.get('created')} messages "
                f"for lead {lead_id}"
            )
            
            # Create email jobs for the scheduled messages
            if messages_with_ids:
                email_job_results = await self.message_scheduler._create_email_jobs(
                    messages_with_ids, 
                    campaign_id
                )
                logger.info(
                    f"Created {email_job_results.get('jobs_created', 0)} email jobs "
                    f"for {email_job_results.get('messages_grouped', 0)} messages"
                )
        
        # Get campaign metrics for reporting
        metrics = await self.db_tools.get_campaign_sending_metrics(campaign_id, days=7)
        
        return {
            "lead_id": lead_id,
            "lead_name": f"{lead_data.get('first_name')} {lead_data.get('last_name')}",
            "company": lead_data.get("company"),
            "messages_generated": generation_result.data.get("total_messages"),
            "messages_scheduled": len(scheduled_messages),
            "scheduling_log": scheduling_result.data.get("scheduling_log", []),
            "campaign_metrics": metrics,
            "status": "outreach_scheduled"
        }
    
    @track_operation("handle_send_email")
    async def _handle_send_email(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle send_email job type - send emails via SendGrid.
        
        Args:
            job_data: Contains campaign_id and message_ids
            
        Returns:
            dict: Job execution results including send status
        """
        campaign_id = job_data.get("campaign_id")
        message_ids = job_data.get("message_ids", [])
        
        if not campaign_id or not message_ids:
            raise Exception("campaign_id and message_ids are required for send_email job")
        
        logger.info(f"Starting email send for {len(message_ids)} messages in campaign {campaign_id}")
        
        # Get campaign data including SendGrid API key and sender settings
        supabase = await get_supabase()
        campaign_response = await supabase.table("campaigns").select(
            "id, name, sendgrid_api_key, email_footer, from_email, from_name"
        ).eq("id", campaign_id).single().execute()
        
        if not campaign_response.data:
            raise Exception(f"Campaign {campaign_id} not found")
        
        campaign_data = campaign_response.data
        sendgrid_api_key = campaign_data.get("sendgrid_api_key")
        
        if not sendgrid_api_key:
            raise Exception(f"No SendGrid API key configured for campaign {campaign_data.get('name')}")
        
        # Get messages to send
        messages_response = await supabase.table("messages").select("*").in_(
            "id", message_ids
        ).eq("status", "scheduled").eq("channel", "email").execute()
        
        if not messages_response.data:
            logger.warning(f"No scheduled email messages found for IDs: {message_ids}")
            return {
                "campaign_id": campaign_id,
                "messages_processed": 0,
                "sent": 0,
                "failed": 0,
                "status": "no_messages"
            }
        
        messages = messages_response.data
        logger.info(f"Found {len(messages)} email messages to send")
        
        # Send emails in batch with campaign sender settings
        send_result = await self.email_sender.send_batch_emails(
            messages=messages,
            api_key=sendgrid_api_key,
            campaign_footer=campaign_data.get("email_footer"),
            from_email=campaign_data.get("from_email", "noreply@example.com"),
            from_name=campaign_data.get("from_name")
        )
        
        if not send_result.success:
            raise Exception(f"Failed to send emails: {send_result.error}")
        
        # Update message statuses based on results
        send_data = send_result.data
        results = send_data.get("results", [])
        
        # Separate successful and failed results
        failed_results = []
        for result in results:
            message_id = result.get("message_id")
            if result.get("sendgrid_message_id"):
                # Successfully sent
                await self.email_sender.update_message_status(
                    message_id=message_id,
                    status="sent",
                    sendgrid_message_id=result.get("sendgrid_message_id")
                )
            else:
                # Failed to send
                error_msg = result.get("error", "Unknown error")
                error_category = result.get("error_category", "unknown")
                is_retryable = result.get("is_retryable", False)
                
                # Only mark as permanently failed if not retryable
                status = "failed" if not is_retryable else "retry_pending"
                
                await self.email_sender.update_message_status(
                    message_id=message_id,
                    status=status,
                    error=f"{error_msg} (Category: {error_category})"
                )
                
                if is_retryable:
                    failed_results.append(result)
        
        # Retry failed messages if any are retryable
        retry_results = None
        retry_details = []
        if failed_results:
            logger.info(f"Found {len(failed_results)} retryable failed messages")
            retry_result = await self.email_sender.retry_failed_messages(
                failed_results=failed_results,
                messages=messages,
                api_key=sendgrid_api_key,
                campaign_footer=campaign_data.get("email_footer"),
                from_email=campaign_data.get("from_email", "noreply@example.com"),
                from_name=campaign_data.get("from_name")
            )
            if retry_result.success:
                retry_results = retry_result.data
                retry_details = retry_results.get("results", [])
                
                # Update message statuses based on retry results
                for retry_msg in retry_details:
                    message_id = retry_msg.get("message_id")
                    if retry_msg.get("sendgrid_message_id"):
                        # Retry succeeded
                        await self.email_sender.update_message_status(
                            message_id=message_id,
                            status="sent",
                            sendgrid_message_id=retry_msg.get("sendgrid_message_id")
                        )
                    else:
                        # Retry failed permanently
                        error_msg = retry_msg.get("error", "Retry failed")
                        await self.email_sender.update_message_status(
                            message_id=message_id,
                            status="failed",
                            error=f"Retry failed: {error_msg}"
                        )
        
        # Calculate final statistics
        initial_sent = send_data.get("sent", 0)
        initial_failed = send_data.get("failed", 0)
        retry_sent = retry_results.get("sent", 0) if retry_results else 0
        retry_failed = retry_results.get("failed", 0) if retry_results else 0
        
        # Final counts
        final_sent = initial_sent + retry_sent
        final_failed = initial_failed - len(failed_results) + retry_failed  # Subtract retried, add retry failures
        
        logger.info(
            f"Email send completed: {final_sent} sent, "
            f"{final_failed} failed out of {len(messages)} messages"
        )
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign_data.get("name"),
            "messages_processed": len(messages),
            "initial_sent": initial_sent,
            "initial_failed": initial_failed,
            "retry_attempted": len(failed_results),
            "retry_sent": retry_sent,
            "retry_failed": retry_failed,
            "final_sent": final_sent,
            "final_failed": final_failed,
            "results": results,
            "retry_results": retry_results,
            "status": "completed"
        }
    
    @track_operation("handle_lead_enrichment")
    async def _handle_lead_enrichment(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle lead_enrichment job type - enrich a single lead with Apollo.
        
        Args:
            job_data: Contains lead_id to enrich
            
        Returns:
            dict: Job execution results including enrichment status
        """
        lead_id = job_data.get("lead_id")
        
        if not lead_id:
            raise Exception("lead_id is required for lead_enrichment job")
        
        logger.info(f"Starting enrichment for lead: {lead_id}")
        
        # Get lead data from database
        supabase = await get_supabase()
        lead_response = await supabase.table("leads").select("*").eq(
            "id", lead_id
        ).single().execute()
        
        if not lead_response.data:
            raise Exception(f"Lead {lead_id} not found")
        
        lead_data = lead_response.data
        campaign_id = lead_data.get("campaign_id")
        
        # Get campaign data for phone requirement
        campaign_response = await supabase.table("campaigns").select(
            "require_phone_number"
        ).eq("id", campaign_id).single().execute()
        
        require_phone = False
        if campaign_response.data:
            require_phone = campaign_response.data.get("require_phone_number", False)
        
        logger.info(
            f"Enriching lead: {lead_data.get('first_name')} {lead_data.get('last_name')} "
            f"at {lead_data.get('company')} - Phone required: {require_phone}"
        )
        
        # Attempt enrichment
        try:
            enriched = await self.apollo_enrich.execute(
                first_name=lead_data.get("first_name"),
                last_name=lead_data.get("last_name"),
                email=None,  # Don't pass placeholder email
                organization_name=lead_data.get("company"),
                reveal_phone_number=require_phone
            )
            
            # Prepare update data based on enrichment results
            update_data = {}
            
            if enriched.success and enriched.data:
                enriched_email = enriched.data.get("email")
                
                # Check if we got a real email
                if enriched_email and not is_placeholder_email(enriched_email):
                    # Successfully enriched with real email
                    update_data["email"] = enriched_email
                    update_data["status"] = "enriched"
                    
                    # Update phone if requested and available
                    if require_phone and enriched.data.get("phone"):
                        update_data["phone"] = enriched.data["phone"]
                    
                    # Update full context with enrichment data
                    full_context = lead_data.get("full_context", {})
                    full_context["enriched"] = True
                    full_context["enrichment_data"] = enriched.data
                    full_context["personal_emails"] = enriched.data.get("personal_emails", [])
                    full_context["linkedin_url"] = enriched.data.get("linkedin_url")
                    full_context["enriched_at"] = datetime.utcnow().isoformat()
                    update_data["full_context"] = full_context
                    
                    logger.info(f"Successfully enriched lead {lead_id} with email: {enriched_email}")
                else:
                    # Enrichment succeeded but no real email found
                    update_data["status"] = "enrichment_failed"
                    
                    full_context = lead_data.get("full_context", {})
                    full_context["enriched"] = False
                    full_context["enrichment_data"] = enriched.data
                    full_context["enrichment_error"] = "No real email found - still placeholder"
                    full_context["enrichment_attempted_at"] = datetime.utcnow().isoformat()
                    update_data["full_context"] = full_context
                    
                    logger.warning(f"Enrichment for lead {lead_id} returned placeholder email: {enriched_email}")
            else:
                # Enrichment API call failed
                update_data["status"] = "enrichment_failed"
                
                full_context = lead_data.get("full_context", {})
                full_context["enriched"] = False
                full_context["enrichment_error"] = enriched.error if enriched else "Unknown error"
                full_context["enrichment_attempted_at"] = datetime.utcnow().isoformat()
                update_data["full_context"] = full_context
                
                logger.error(f"Enrichment failed for lead {lead_id}: {enriched.error if enriched else 'Unknown error'}")
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error during enrichment for lead {lead_id}: {e}")
            
            update_data = {
                "status": "enrichment_failed",
                "full_context": {
                    **lead_data.get("full_context", {}),
                    "enriched": False,
                    "enrichment_error": str(e),
                    "enrichment_attempted_at": datetime.utcnow().isoformat()
                }
            }
        
        # Update the lead in database
        await supabase.table("leads").update(update_data).eq("id", lead_id).execute()
        
        return {
            "lead_id": lead_id,
            "lead_name": f"{lead_data.get('first_name')} {lead_data.get('last_name')}",
            "company": lead_data.get("company"),
            "status": update_data["status"],
            "enriched": update_data.get("full_context", {}).get("enriched", False),
            "error": update_data.get("full_context", {}).get("enrichment_error")
        }
    
    @track_operation("chat")
    async def chat(self, conversation_id: str, user_message: str) -> str:
        """
        Handle synchronous chat with context from conversation history.
        
        Args:
            conversation_id: UUID of the conversation
            user_message: User's message
            
        Returns:
            str: Agent's response
        """
        logger.info(f"Processing chat message for conversation: {conversation_id}")
        
        supabase = await get_supabase()
        
        # Get recent conversation history
        history_result = await supabase.table("chat_messages")\
            .select("role, content")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=False)\
            .limit(10)\
            .execute()
        
        # Build messages for OpenAI
        messages = [
            {
                "role": "system", 
                "content": """You are the AutopilotAgent, an AI assistant for managing outreach campaigns. 
                
You can help users with:
- Getting new leads (e.g., "get 10 new leads from Apollo")
- Enriching specific leads (e.g., "enrich lead with ID xyz" or "find email for John Doe")
- Researching leads for personalized outreach
- Creating and scheduling outreach messages
- Viewing campaign statistics and performance
- Managing campaign settings

Be conversational, helpful, and suggest specific actions the user can take.
When users ask for actions, acknowledge what you'll do but explain that they need to create a job for actual execution."""
            }
        ]
        
        # Add conversation history
        for msg in history_result.data:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        # Generate response
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=self.max_tokens
        )
        
        agent_response = response.choices[0].message.content
        
        logger.info(f"Generated chat response for conversation {conversation_id}")
        
        return agent_response
