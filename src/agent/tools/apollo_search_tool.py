# src/agent/tools/apollo_search_tool.py
# Apollo search tool for lead discovery using pre-configured search URLs
# Uses the search URL directly from campaign configuration
# RELEVANT FILES: ../autopilot_agent.py, ../../config.py, ./base_tools.py

import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from ...config import get_settings
from .base_tools import BaseTool, ToolResult


class ApolloSearchTool(BaseTool):
    """
    Execute Apollo searches using pre-configured search URLs.
    Simply uses the URL provided by the campaign configuration.
    """
    
    def __init__(self):
        """Initialize the Apollo search tool."""
        super().__init__(name="apollo_search", description="Search for leads using Apollo API")
        self.settings = get_settings()
        self.base_url = "https://api.apollo.io/api/v1/mixed_people/search"
        
    async def execute(self, search_url: str, page_number: int = 1) -> ToolResult:
        """
        Execute Apollo search with the provided URL.
        
        Args:
            search_url: Complete Apollo search URL from campaign config
            page_number: Page number to append to the URL
            
        Returns:
            ToolResult with discovered leads
        """
        # Validate API key is configured
        if not self.settings.apollo_api_key:
            return ToolResult(
                success=False,
                error="Apollo API key not configured"
            )
        
        # Extract query parameters from the search URL
        # Apollo search URLs look like: https://app.apollo.io/#/people/search?personTitles[]=CEO&personLocations[]=San%20Francisco%2C%20CA
        # We need to convert this to API parameters
        try:
            # Parse the URL to extract parameters
            if "#/people/search?" in search_url:
                query_string = search_url.split("#/people/search?")[1]
            else:
                return ToolResult(
                    success=False,
                    error="Invalid Apollo search URL format"
                )
            
            # Build API request with page parameter
            api_url = f"{self.base_url}?{query_string}&page={page_number}"
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to parse search URL: {str(e)}"
            )
        
        # Set up headers for Apollo API
        headers = {
            "X-Api-Key": self.settings.apollo_api_key,
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }
        
        # Execute the API request
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(api_url, headers=headers, timeout=30) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        people = response_data.get("people", [])
                        
                        # Check if we have results
                        if not people:
                            return ToolResult(
                                success=False,
                                error=f"No more leads found at page {page_number}"
                            )
                        
                        return ToolResult(
                            success=True,
                            data={
                                "people": people,
                                "total_found": len(people),
                                "page": page_number
                            },
                            message=f"Found {len(people)} leads on page {page_number}"
                        )
                    
                    elif response.status == 401:
                        return ToolResult(
                            success=False,
                            error="Apollo API authentication failed - invalid API key"
                        )
                    
                    elif response.status == 429:
                        # Rate limit reached
                        retry_after = response.headers.get('Retry-After', '60')
                        return ToolResult(
                            success=False,
                            error=f"Apollo API rate limit reached. Retry after {retry_after} seconds"
                        )
                    
                    elif response.status == 402:
                        return ToolResult(
                            success=False,
                            error="Apollo API credits exhausted"
                        )
                    
                    else:
                        # Other API errors
                        error_message = response_data.get('error', {}).get('message', f'Unknown error: {response.status}')
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
                    error=f"Unexpected error during Apollo search: {str(e)}"
                )
    
    def _extract_lead_data(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant lead data from Apollo person object.
        
        Args:
            person: Raw person data from Apollo API
            
        Returns:
            Formatted lead data for our database
        """
        return {
            "email": person.get("email"),
            "first_name": person.get("first_name"),
            "last_name": person.get("last_name"),
            "title": person.get("title"),
            "company": person.get("organization", {}).get("name"),
            "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None,
            "full_context": {
                "apollo_id": person.get("id"),
                "linkedin_url": person.get("linkedin_url"),
                "organization": person.get("organization", {}),
                "seniority": person.get("seniority"),
                "departments": person.get("departments", []),
                "city": person.get("city"),
                "state": person.get("state"),
                "country": person.get("country"),
                "email_confidence": person.get("email_confidence")
            }
        }