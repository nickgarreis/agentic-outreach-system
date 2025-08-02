# src/agent/tools/tavily_tool.py
# Tavily search tool for researching leads using web search
# Provides intelligent research capabilities for lead enrichment
# RELEVANT FILES: base_tools.py, ../autopilot_agent.py, ../../config.py

# Standard library imports
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

# Third-party imports
from tavily import AsyncTavilyClient, TavilyClient

# Local imports
from .base_tools import BaseTool, ToolResult
from ...config import get_settings

logger = logging.getLogger(__name__)

# Domain configurations for different research types
TRUSTED_DOMAINS = {
    "company_research": [
        "crunchbase.com",
        "techcrunch.com",
        "reuters.com",
        "bloomberg.com",
        "businessinsider.com",
        "forbes.com",
        "wsj.com"
    ],
    "person_research": [
        "linkedin.com",
        "twitter.com",
        "github.com",
        "medium.com",
        "crunchbase.com"
    ],
    "industry_insights": [
        "gartner.com",
        "forrester.com",
        "mckinsey.com",
        "hbr.org",
        "mit.edu",
        "stanford.edu"
    ]
}

# Domains to exclude for better quality
EXCLUDED_DOMAINS = [
    "pinterest.com",
    "quora.com",
    "reddit.com",
    "facebook.com"
]

# Rate limiting configuration
RATE_LIMIT_WINDOW = timedelta(minutes=1)
MAX_REQUESTS_PER_WINDOW = 30

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0  # seconds

# Query templates for optimization
QUERY_TEMPLATES = {
    "person_research": "{name} {company} {title} {location}",
    "company_research": "{company} company {industry} {location} recent developments {year}",
    "industry_insights": "{title} role challenges trends {industry} {year}",
    "news_search": "{company} latest news announcements {location}"
}


class TavilyTool(BaseTool):
    """
    Tool for researching leads using Tavily's search API.
    Provides comprehensive web research about companies and individuals.
    """

    def __init__(self):
        """Initialize the Tavily tool with API credentials"""
        super().__init__(
            name="tavily_research",
            description="Research leads using Tavily API for comprehensive insights"
        )
        
        # Get settings and API key
        settings = get_settings()
        self.api_key = settings.tavily_api_key
        
        # Initialize Tavily clients if API key is available
        if self.api_key:
            self.async_client = AsyncTavilyClient(api_key=self.api_key)
            self.sync_client = TavilyClient(api_key=self.api_key)  # Fallback for sync operations
            self.logger.info("Tavily clients initialized successfully")
        else:
            self.async_client = None
            self.sync_client = None
            self.logger.warning("Tavily API key not configured")
        
        # Initialize rate limiting
        self.request_times: List[datetime] = []
        self.credit_usage = {
            "total": 0,
            "basic_searches": 0,
            "advanced_searches": 0,
            "extractions": 0
        }

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now()
        # Remove old requests outside the window
        self.request_times = [
            t for t in self.request_times 
            if now - t < RATE_LIMIT_WINDOW
        ]
        
        return len(self.request_times) < MAX_REQUESTS_PER_WINDOW
    
    def _track_request(self, search_depth: str = "advanced") -> None:
        """Track a request for rate limiting and credit usage"""
        self.request_times.append(datetime.now())
        
        # Track credit usage - always advanced now
        self.credit_usage["advanced_searches"] += 1
        self.credit_usage["total"] += 10
    
    async def _search_with_retry(
        self, 
        query: str, 
        params: Dict[str, Any], 
        max_retries: int = MAX_RETRIES
    ) -> Optional[Dict[str, Any]]:
        """Execute search with exponential backoff retry logic"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Check rate limit before attempting
                if not self._check_rate_limit():
                    wait_time = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                    self.logger.warning(f"Rate limit reached, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Execute the search
                result = await self.async_client.search(query, **params)
                self._track_request(params.get("search_depth", "advanced"))
                return result
                
            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:
                    self.logger.error(f"Search failed after {max_retries} attempts for query '{query}': {e}")
                    raise
                
                # Calculate backoff time
                wait_time = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                self.logger.warning(
                    f"Search attempt {attempt + 1}/{max_retries} failed for '{query}', "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
        
        # Should not reach here, but just in case
        raise last_error or Exception("Search failed with unknown error")
    
    def _build_optimized_query(
        self, 
        template_key: str, 
        lead_data: Dict[str, Any], 
        **extra_params
    ) -> str:
        """Build optimized search query using templates and dynamic data"""
        template = QUERY_TEMPLATES.get(template_key, "{name} {company}")
        
        # Extract location from full_context if available
        location = ""
        if "full_context" in lead_data:
            location = lead_data["full_context"].get("location", "")
            if not location and "headquarters" in lead_data["full_context"]:
                location = lead_data["full_context"]["headquarters"]
        
        # Get current year
        current_year = datetime.now().year
        
        # Extract industry from full_context
        industry = ""
        if "full_context" in lead_data:
            industry = lead_data["full_context"].get("industry", "")
        
        # Build query parameters
        query_params = {
            "name": f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            "company": lead_data.get("company", ""),
            "title": lead_data.get("title", ""),
            "location": location,
            "industry": industry,
            "year": str(current_year),
            **extra_params
        }
        
        # Format template with available parameters, using empty string for missing keys
        try:
            query = template.format(**query_params)
        except KeyError:
            # Fallback to safe formatting if template has missing keys
            safe_params = {k: v if v else "" for k, v in query_params.items()}
            query = template.format_map(safe_params)
        
        # Clean up extra spaces and limit length
        query = " ".join(query.split())[:400]  # Limit to 400 chars
        
        return query.strip()
    
    async def _parallel_search(self, queries: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Execute multiple searches in parallel for better performance with retry logic"""
        tasks = []
        query_map = {}  # Map task index to query for result processing
        
        for idx, (query, params) in enumerate(queries):
            # Create task with retry logic
            task = self._search_with_retry(query, params)
            tasks.append(task)
            query_map[idx] = query
        
        if not tasks:
            return {}
        
        # Execute all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = {}
        for idx, result in enumerate(results):
            query = query_map.get(idx)
            if query and not isinstance(result, Exception):
                processed_results[query] = result
            elif isinstance(result, Exception):
                self.logger.error(f"Search failed for '{query}' after retries: {result}")
        
        return processed_results

    async def execute(
        self,
        lead_data: Dict[str, Any],
        campaign_data: Dict[str, Any],
        **kwargs
    ) -> ToolResult:
        """
        Research a lead using Tavily search.
        
        Args:
            lead_data: Dictionary containing lead information (name, company, title, etc.)
            campaign_data: Dictionary containing campaign context
            
        Returns:
            ToolResult with research findings
        """
        if not self.async_client:
            return ToolResult(
                success=False,
                error="Tavily API key not configured"
            )
        
        try:
            # Extract lead information
            first_name = lead_data.get("first_name", "")
            last_name = lead_data.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            company = lead_data.get("company", "")
            title = lead_data.get("title", "")
            
            # Build research queries
            research_data = {
                "person_info": {},
                "company_info": {},
                "recent_news": {},
                "industry_insights": {}
            }
            
            # Prepare all search queries for parallel execution
            search_queries = []
            
            # Person research query
            if full_name and company:
                person_query = self._build_optimized_query("person_research", lead_data)
                search_queries.append((
                    "person_info",
                    (person_query, {
                        "search_depth": "advanced",  # Always advanced
                        "max_results": 5,
                        "include_answer": True,
                        "include_domains": TRUSTED_DOMAINS["person_research"],
                        "exclude_domains": EXCLUDED_DOMAINS
                    })
                ))
            
            # Company research queries
            if company:
                # Company overview
                company_query = self._build_optimized_query("company_research", lead_data)
                search_queries.append((
                    "company_info",
                    (company_query, {
                        "search_depth": "advanced",  # Always advanced
                        "max_results": 5,
                        "include_answer": True,
                        "time_range": "month",
                        "include_domains": TRUSTED_DOMAINS["company_research"],
                        "exclude_domains": EXCLUDED_DOMAINS
                    })
                ))
                
                # Recent news
                news_query = self._build_optimized_query("news_search", lead_data)
                search_queries.append((
                    "recent_news",
                    (news_query, {
                        "search_depth": "advanced",  # Always advanced
                        "topic": "news",
                        "days": 7,
                        "max_results": 3,
                        "exclude_domains": EXCLUDED_DOMAINS
                    })
                ))
            
            # Industry insights query
            if title and company:
                industry_query = self._build_optimized_query("industry_insights", lead_data)
                search_queries.append((
                    "industry_insights",
                    (industry_query, {
                        "search_depth": "advanced",  # Always advanced
                        "max_results": 3,
                        "include_answer": True,
                        "include_domains": TRUSTED_DOMAINS["industry_insights"],
                        "exclude_domains": EXCLUDED_DOMAINS,
                        "time_range": "year"
                    })
                ))
            
            # Execute all searches in parallel
            self.logger.info(f"Executing {len(search_queries)} parallel searches for lead research")
            
            # Convert queries for parallel execution
            queries_for_parallel = [(q[1][0], q[1][1]) for q in search_queries]
            search_results = await self._parallel_search(queries_for_parallel)
            
            # Process results
            for query_type, (query_text, _) in search_queries:
                if query_text in search_results:
                    result = search_results[query_text]
                    
                    if query_type == "person_info":
                        research_data["person_info"] = {
                            "query": query_text,
                            "answer": result.get("answer", ""),
                            "sources": self._filter_sources_by_score(
                                self._extract_relevant_sources(result.get("results", [])),
                                min_score=0.5
                            )
                        }
                    elif query_type == "company_info":
                        research_data["company_info"] = {
                            "query": query_text,
                            "answer": result.get("answer", ""),
                            "sources": self._filter_sources_by_score(
                                self._extract_relevant_sources(result.get("results", [])),
                                min_score=0.5
                            )
                        }
                    elif query_type == "recent_news":
                        research_data["recent_news"] = {
                            "articles": self._extract_news_items(result.get("results", []))
                        }
                    elif query_type == "industry_insights":
                        research_data["industry_insights"] = {
                            "query": query_text,
                            "answer": result.get("answer", ""),
                            "trends": self._filter_sources_by_score(
                                self._extract_relevant_sources(result.get("results", [])),
                                min_score=0.4
                            )
                        }
            
            # Build comprehensive research summary
            summary = self._build_research_summary(research_data, lead_data)
            
            return ToolResult(
                success=True,
                data={
                    "research_data": research_data,
                    "summary": summary,
                    "research_timestamp": self._get_timestamp()
                },
                message=f"Successfully researched lead: {full_name} at {company}"
            )
            
        except Exception as e:
            self.logger.error(f"Tavily research failed: {e}")
            return ToolResult(
                success=False,
                error=f"Research failed: {str(e)}"
            )
    
    def _extract_relevant_sources(self, results: List[Dict]) -> List[Dict]:
        """
        Extract relevant information from search results.
        
        Args:
            results: Raw search results from Tavily
            
        Returns:
            List of formatted source information
        """
        sources = []
        for result in results[:3]:  # Limit to top 3 most relevant
            sources.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")[:500],  # Limit content length
                "score": result.get("score", 0)
            })
        return sources
    
    def _filter_sources_by_score(self, sources: List[Dict], min_score: float = 0.5) -> List[Dict]:
        """
        Filter sources by relevance score.
        
        Args:
            sources: List of source dictionaries
            min_score: Minimum score threshold (0-1)
            
        Returns:
            Filtered list of sources above the threshold
        """
        filtered = [s for s in sources if s.get("score", 0) >= min_score]
        # Sort by score descending
        return sorted(filtered, key=lambda x: x.get("score", 0), reverse=True)
    
    def _extract_news_items(self, results: List[Dict]) -> List[Dict]:
        """
        Extract news items from search results.
        
        Args:
            results: News search results from Tavily
            
        Returns:
            List of formatted news items
        """
        news_items = []
        for result in results:
            news_items.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "published_date": result.get("published_date", ""),
                "summary": result.get("content", "")[:300]  # Brief summary
            })
        return news_items
    
    def _build_research_summary(
        self, 
        research_data: Dict[str, Any], 
        lead_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a comprehensive summary of research findings.
        
        Args:
            research_data: All research findings
            lead_data: Original lead data
            
        Returns:
            Structured summary for outreach personalization
        """
        summary = {
            "lead_name": f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            "company": lead_data.get("company", ""),
            "title": lead_data.get("title", ""),
            "key_insights": [],
            "recent_developments": [],
            "conversation_starters": []
        }
        
        # Extract key insights from person research
        if research_data["person_info"].get("answer"):
            summary["key_insights"].append({
                "type": "professional_background",
                "insight": research_data["person_info"]["answer"]
            })
        
        # Extract company insights
        if research_data["company_info"].get("answer"):
            summary["key_insights"].append({
                "type": "company_overview",
                "insight": research_data["company_info"]["answer"]
            })
        
        # Add recent news as developments
        for article in research_data.get("recent_news", {}).get("articles", []):
            summary["recent_developments"].append({
                "title": article["title"],
                "date": article.get("published_date", ""),
                "relevance": "company_news"
            })
        
        # Generate conversation starters based on research
        if research_data["industry_insights"].get("answer"):
            summary["conversation_starters"].append({
                "topic": "industry_trends",
                "suggestion": f"Discuss: {research_data['industry_insights']['answer'][:200]}..."
            })
        
        return summary
    
    async def extract_from_urls(self, urls: List[str], extract_depth: str = "basic") -> ToolResult:
        """
        Extract content from specific URLs using Tavily Extract API.
        Useful for LinkedIn profiles and other specific pages.
        
        Args:
            urls: List of URLs to extract content from
            extract_depth: 'basic' or 'advanced' (use advanced for LinkedIn)
            
        Returns:
            ToolResult with extracted content
        """
        if not self.async_client:
            return ToolResult(
                success=False,
                error="Tavily API key not configured"
            )
        
        try:
            # Check rate limit
            if not self._check_rate_limit():
                return ToolResult(
                    success=False,
                    error="Rate limit exceeded. Please wait before making more requests."
                )
            
            # Track extraction credit usage (1 credit per 5 URLs for basic, 2 for advanced)
            credit_cost = 2 if extract_depth == "advanced" else 1
            self.credit_usage["extractions"] += len(urls)
            self.credit_usage["total"] += credit_cost * (len(urls) // 5 + 1)
            
            # Extract content
            results = await self.async_client.extract(
                urls=urls,
                include_images=False,
                extract_depth=extract_depth
            )
            
            return ToolResult(
                success=True,
                data={
                    "extracted_content": results.get("results", []),
                    "failed_urls": results.get("failed_results", []),
                    "extraction_time": self._get_timestamp()
                },
                message=f"Successfully extracted content from {len(results.get('results', []))} URLs"
            )
            
        except Exception as e:
            self.logger.error(f"URL extraction failed: {e}")
            return ToolResult(
                success=False,
                error=f"Extraction failed: {str(e)}"
            )
    
    def _get_timestamp(self) -> str:
        """Get current UTC timestamp"""
        return datetime.utcnow().isoformat()
    
    def _parse_linkedin_extraction(self, extraction_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse LinkedIn extraction results into structured data"""
        structured_data = {
            "profile_summary": "",
            "experience": [],
            "skills": [],
            "education": [],
            "accomplishments": [],
            "connections": 0,
            "about": "",
            "headline": ""
        }
        
        if not extraction_data:
            return structured_data
        
        # Process each extracted result
        for result in extraction_data:
            content = result.get("raw_content", "")
            if not content:
                continue
            
            # Extract headline (usually appears early in the profile)
            headline_match = re.search(r'<h2[^>]*>([^<]+)</h2>', content)
            if headline_match and not structured_data["headline"]:
                structured_data["headline"] = headline_match.group(1).strip()
            
            # Extract About section
            about_match = re.search(r'About\s*</[^>]+>\s*<[^>]+>([^<]+)', content, re.IGNORECASE)
            if about_match:
                structured_data["about"] = about_match.group(1).strip()
            
            # Extract Experience section with pattern matching
            experience_pattern = r'Experience\s*</[^>]+>(.*?)(?:Education|Skills|$)'
            experience_match = re.search(experience_pattern, content, re.IGNORECASE | re.DOTALL)
            if experience_match:
                exp_content = experience_match.group(1)
                # Parse individual experiences
                job_pattern = r'<h3[^>]*>([^<]+)</h3>.*?<[^>]+>([^<]+)(?:·|-)([^<]+)'
                jobs = re.findall(job_pattern, exp_content, re.DOTALL)
                
                for job_title, company, duration in jobs[:5]:  # Limit to 5 most recent
                    structured_data["experience"].append({
                        "title": job_title.strip(),
                        "company": company.strip(),
                        "duration": duration.strip()
                    })
            
            # Extract Skills
            skills_pattern = r'Skills\s*</[^>]+>(.*?)(?:Education|Accomplishments|$)'
            skills_match = re.search(skills_pattern, content, re.IGNORECASE | re.DOTALL)
            if skills_match:
                skills_content = skills_match.group(1)
                # Extract skill names
                skill_pattern = r'<[^>]+>([^<]+)(?:</[^>]+>)?(?:\s*·\s*\d+)?'
                skills = re.findall(skill_pattern, skills_content)
                structured_data["skills"] = [s.strip() for s in skills[:20] if len(s.strip()) > 2]
            
            # Extract Education
            education_pattern = r'Education\s*</[^>]+>(.*?)(?:Skills|Experience|$)'
            education_match = re.search(education_pattern, content, re.IGNORECASE | re.DOTALL)
            if education_match:
                edu_content = education_match.group(1)
                # Parse individual education entries
                school_pattern = r'<h3[^>]*>([^<]+)</h3>.*?<[^>]+>([^<]+)'
                schools = re.findall(school_pattern, edu_content, re.DOTALL)
                
                for school, degree in schools[:3]:  # Limit to 3 entries
                    structured_data["education"].append({
                        "school": school.strip(),
                        "degree": degree.strip()
                    })
            
            # Extract connections count
            connections_match = re.search(r'(\d+)\+?\s*connections', content, re.IGNORECASE)
            if connections_match:
                try:
                    structured_data["connections"] = int(connections_match.group(1))
                except ValueError:
                    pass
            
            # Create profile summary from available data
            if not structured_data["profile_summary"]:
                summary_parts = []
                if structured_data["headline"]:
                    summary_parts.append(structured_data["headline"])
                if structured_data["about"]:
                    summary_parts.append(structured_data["about"][:200] + "...")
                structured_data["profile_summary"] = " | ".join(summary_parts)
        
        return structured_data
    
    def _enhance_research_with_linkedin(
        self, 
        research_data: Dict[str, Any], 
        linkedin_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance research data with structured LinkedIn information"""
        if "linkedin_extraction" in research_data:
            parsed_linkedin = self._parse_linkedin_extraction(
                research_data["linkedin_extraction"].get("extracted_content", [])
            )
            
            # Add parsed LinkedIn data to research
            research_data["linkedin_profile"] = parsed_linkedin
            
            # Enhance person_info with LinkedIn data
            if research_data.get("person_info") and parsed_linkedin["profile_summary"]:
                research_data["person_info"]["linkedin_summary"] = parsed_linkedin["profile_summary"]
                research_data["person_info"]["linkedin_headline"] = parsed_linkedin.get("headline", "")
        
        return research_data
    
    def get_credit_usage_report(self) -> Dict[str, Any]:
        """
        Get a report of credit usage for monitoring.
        
        Returns:
            Dictionary with credit usage statistics
        """
        return {
            "total_credits_used": self.credit_usage["total"],
            "basic_searches": 0,  # No longer used - all searches are advanced
            "advanced_searches": self.credit_usage["advanced_searches"],
            "extractions": self.credit_usage["extractions"],
            "estimated_cost": self.credit_usage["total"] * 0.01  # Assuming $0.01 per credit
        }
