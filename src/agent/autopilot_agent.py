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
from .tools import DatabaseTools, ApolloSearchTool
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
                
                # Create new lead
                lead_info["campaign_id"] = campaign_id
                lead_info["client_id"] = job_data.get("client_id")  # If provided
                lead_info["status"] = "new"
                
                await supabase.table("leads").insert(lead_info).execute()
                leads_created += 1
                
            except Exception as e:
                logger.error(f"Failed to save lead: {e}")
                # Continue with other leads even if one fails
        
        # Update campaign's page number for next run
        await self._update_campaign_page_number(campaign_id, "apollo", page_number + 1)
        
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
