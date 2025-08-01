# src/agent/tools/apollo_enrich_tool.py
# Apollo enrichment tool for getting complete contact details
# Uses Apollo's people/match endpoint to enrich lead data  
# RELEVANT FILES: ./apollo_search_tool.py, ../autopilot_agent.py, ../../config.py

import aiohttp
import asyncio
from typing import Dict, Any, Optional
from ...config import get_settings
from .base_tools import BaseTool, ToolResult


class ApolloEnrichTool(BaseTool):
    """
    Enrich lead data using Apollo's people/match endpoint.
    Reveals personal emails and optionally phone numbers based on campaign settings.
    """
    
    def __init__(self):
        """Initialize the Apollo enrich tool."""
        super().__init__(name="apollo_enrich", description="Enrich lead data with contact details from Apollo")
        self.settings = get_settings()
        self.base_url = "https://api.apollo.io/api/v1/people/match"
        
    async def execute(
        self, 
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        organization_name: Optional[str] = None,
        reveal_phone_number: bool = False
    ) -> ToolResult:
        """
        Enrich a person's data using Apollo's match endpoint.
        
        Args:
            first_name: Person's first name
            last_name: Person's last name  
            email: Person's email (if known)
            organization_name: Person's company name
            reveal_phone_number: Whether to reveal phone numbers (costs more credits)
            
        Returns:
            ToolResult with enriched data or error
        """
        # Validate API key is configured
        if not self.settings.apollo_api_key:
            return ToolResult(
                success=False,
                error="Apollo API key not configured"
            )
        
        # Build request payload
        # Apollo requires at least some identifying information
        if not any([first_name, last_name, email, organization_name]):
            return ToolResult(
                success=False,
                error="At least one identifying parameter required (name, email, or organization)"
            )
        
        payload = {}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if email:
            payload["email"] = email
        if organization_name:
            payload["organization_name"] = organization_name
            
        # Always reveal personal emails, phone based on parameter
        payload["reveal_personal_emails"] = True
        payload["reveal_phone_number"] = reveal_phone_number
        
        # Set up headers for Apollo API
        headers = {
            "X-Api-Key": self.settings.apollo_api_key,
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }
        
        # Execute the API request
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.base_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=30
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        # Check if we got a match
                        person = response_data.get("person")
                        if not person:
                            return ToolResult(
                                success=False,
                                error="No matching person found in Apollo database"
                            )
                        
                        # Extract enriched data
                        enriched_data = self._extract_enriched_data(person, reveal_phone_number)
                        
                        return ToolResult(
                            success=True,
                            data=enriched_data,
                            message=f"Successfully enriched data for {person.get('name', 'unknown')}"
                        )
                    
                    elif response.status == 401:
                        return ToolResult(
                            success=False,
                            error="Apollo API authentication failed - invalid API key"
                        )
                    
                    elif response.status == 402:
                        return ToolResult(
                            success=False,
                            error="Apollo API credits exhausted"
                        )
                    
                    elif response.status == 429:
                        retry_after = response.headers.get('Retry-After', '60')
                        return ToolResult(
                            success=False,
                            error=f"Apollo API rate limit reached. Retry after {retry_after} seconds"
                        )
                    
                    else:
                        error_message = response_data.get('error', f'Unknown error: {response.status}')
                        return ToolResult(
                            success=False,
                            error=f"Apollo API error: {error_message}"
                        )
                        
            except asyncio.TimeoutError:
                return ToolResult(
                    success=False,
                    error="Apollo API request timed out after 30 seconds"
                )
            except aiohttp.ClientError as e:
                return ToolResult(
                    success=False,
                    error=f"Network error while calling Apollo API: {str(e)}"
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Unexpected error during Apollo enrichment: {str(e)}"
                )
    
    def _extract_enriched_data(self, person: Dict[str, Any], include_phone: bool) -> Dict[str, Any]:
        """
        Extract relevant enriched data from Apollo person response.
        
        Args:
            person: Raw person data from Apollo API
            include_phone: Whether to include phone numbers
            
        Returns:
            Formatted enriched data
        """
        enriched = {
            "apollo_id": person.get("id"),
            "email": person.get("email"),
            "email_status": person.get("email_status"),
            "personal_emails": person.get("personal_emails", []),
            "linkedin_url": person.get("linkedin_url"),
            "twitter_url": person.get("twitter_url"),
            "facebook_url": person.get("facebook_url"),
            "github_url": person.get("github_url"),
            "title": person.get("title"),
            "seniority": person.get("seniority"),
            "departments": person.get("departments", []),
            "functions": person.get("functions", []),
            "photo_url": person.get("photo_url"),
        }
        
        # Include phone numbers if requested
        if include_phone:
            phone_numbers = person.get("phone_numbers", [])
            if phone_numbers:
                # Get the first phone number (usually the most relevant)
                primary_phone = phone_numbers[0]
                enriched["phone"] = primary_phone.get("sanitized_number")
                enriched["phone_type"] = primary_phone.get("type")
                enriched["all_phones"] = [
                    {
                        "number": p.get("sanitized_number"),
                        "type": p.get("type")
                    }
                    for p in phone_numbers
                ]
        
        # Employment details
        employment = person.get("employment_history", [])
        if employment:
            current_job = employment[0]  # Most recent
            enriched["current_employer"] = {
                "name": current_job.get("organization_name"),
                "title": current_job.get("title"),
                "start_date": current_job.get("start_date"),
            }
        
        return enriched