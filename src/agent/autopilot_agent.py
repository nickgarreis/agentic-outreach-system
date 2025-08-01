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
from .tools import DatabaseTools, ApolloSearchTool, ApolloEnrichTool, TavilyTool
from ..database import get_supabase

logger = logging.getLogger(__name__)


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
        
        # Get campaign settings for phone number requirement
        campaign_response = await get_supabase()
        campaign_data = await campaign_response.table("campaigns").select("require_phone_number").eq(
            "id", campaign_id
        ).single().execute()
        require_phone = campaign_data.data.get("require_phone_number", False) if campaign_data.data else False
        
        logger.info(f"Phone number requirement: {require_phone}")
        
        # Save leads to database
        leads_created = 0
        duplicate_leads = 0
        supabase = await get_supabase()
        
        for lead_data in leads_data:
            try:
                # Extract lead information
                lead_info = self.apollo_search._extract_lead_data(lead_data)
                
                # Check if lead already exists (by email)
                if lead_info.get("email"):
                    existing = await supabase.table("leads").select("id").eq(
                        "email", lead_info["email"]
                    ).eq("campaign_id", campaign_id).execute()
                    
                    if existing.data:
                        duplicate_leads += 1
                        continue
                
                # Enrich lead data if we have basic info
                if lead_info.get("first_name") or lead_info.get("email"):
                    try:
                        enriched = await self.apollo_enrich.execute(
                            first_name=lead_info.get("first_name"),
                            last_name=lead_info.get("last_name"),
                            email=lead_info.get("email"),
                            organization_name=lead_info.get("company"),
                            reveal_phone_number=require_phone
                        )
                        
                        if enriched.success and enriched.data:
                            # Merge enriched data
                            if require_phone and enriched.data.get("phone"):
                                lead_info["phone"] = enriched.data["phone"]
                            
                            # Add enriched data to full_context
                            lead_info["full_context"]["personal_emails"] = enriched.data.get("personal_emails", [])
                            lead_info["full_context"]["linkedin_url"] = enriched.data.get("linkedin_url")
                            lead_info["full_context"]["enriched"] = True
                            lead_info["full_context"]["enrichment_data"] = enriched.data
                    except Exception as e:
                        logger.warning(f"Failed to enrich lead {lead_info.get('email')}: {e}")
                        # Continue without enrichment
                
                # Add source tracking
                lead_info["full_context"]["source"] = "apollo_search"
                lead_info["full_context"]["source_details"] = {
                    "platform": "apollo",
                    "search_page": page_number,
                    "discovered_at": datetime.utcnow().isoformat(),
                    "search_url": search_url
                }
                
                # Create new lead
                lead_info["campaign_id"] = campaign_id
                lead_info["client_id"] = job_data.get("client_id")  # If provided
                # Set status based on enrichment success
                lead_info["status"] = "enriched" if lead_info["full_context"].get("enriched", False) else "enrichment_failed"
                
                await supabase.table("leads").insert(lead_info).execute()
                leads_created += 1
                
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
        
        logger.info(f"Lead discovery completed: {leads_created} new leads, {duplicate_leads} duplicates")
        
        return {
            "leads_found": len(leads_data),
            "leads_created": leads_created,
            "duplicate_leads": duplicate_leads,
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
            self.logger.info(f"Extracting LinkedIn profile content for {linkedin_url}")
            
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
                    
                    self.logger.info("Successfully extracted and parsed LinkedIn profile content")
            except Exception as e:
                self.logger.warning(f"Failed to extract LinkedIn content: {e}")
        
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
