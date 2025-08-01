# src/agent/tools/outreach_generator.py
# Generates personalized outreach messages using AI based on lead and campaign context
# Creates multi-step sequences for email and LinkedIn outreach
# RELEVANT FILES: base_tools.py, ../autopilot_agent.py, database_tools.py

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from ..agentops_config import track_tool
from .base_tools import BaseTools, ToolResult

logger = logging.getLogger(__name__)


class OutreachGenerator(BaseTools):
    """
    AI-powered tool for generating personalized outreach sequences.
    Uses OpenAI to craft contextual messages based on lead research and campaign goals.
    """

    def __init__(self):
        """Initialize the outreach generator with AI client"""
        super().__init__()
        self.logger = logger
        
    @track_tool("generate_outreach_sequence")
    async def generate_outreach_sequence(
        self,
        lead_data: Dict[str, Any],
        campaign_data: Dict[str, Any],
        enabled_channels: Dict[str, bool]
    ) -> ToolResult:
        """
        Generate a complete outreach sequence for a lead.
        
        Args:
            lead_data: Complete lead information including research data
            campaign_data: Campaign settings and context
            enabled_channels: Dict indicating which channels are enabled (email/linkedin)
            
        Returns:
            ToolResult with generated message sequences
        """
        try:
            # Extract key information for personalization
            lead_context = self._extract_lead_context(lead_data)
            campaign_context = self._extract_campaign_context(campaign_data)
            
            # Generate sequences for each enabled channel
            sequences = {}
            
            if enabled_channels.get("email", False):
                email_sequence = await self._generate_email_sequence(
                    lead_context, campaign_context, campaign_data
                )
                sequences["email"] = email_sequence
                
            if enabled_channels.get("linkedin", False):
                linkedin_sequence = await self._generate_linkedin_sequence(
                    lead_context, campaign_context
                )
                sequences["linkedin"] = linkedin_sequence
            
            # Calculate total messages
            total_messages = sum(len(seq) for seq in sequences.values())
            
            self.logger.info(
                f"Generated {total_messages} messages across {len(sequences)} channels "
                f"for {lead_data.get('first_name')} {lead_data.get('last_name')}"
            )
            
            return ToolResult(
                success=True,
                data={
                    "sequences": sequences,
                    "total_messages": total_messages,
                    "lead_id": lead_data.get("id"),
                    "campaign_id": campaign_data.get("id")
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate outreach sequence: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to generate outreach sequence: {str(e)}"
            )
    
    def _extract_lead_context(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant context from lead data for personalization.
        
        Args:
            lead_data: Complete lead information
            
        Returns:
            Structured context for AI prompt
        """
        full_context = lead_data.get("full_context", {})
        
        # Extract research insights
        research_data = full_context.get("tavily_research", {})
        research_summary = research_data.get("summary", {})
        
        # Extract LinkedIn insights if available
        linkedin_data = research_data.get("linkedin_extraction", {})
        
        return {
            "name": f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            "email": lead_data.get("email"),
            "title": lead_data.get("title", ""),
            "company": lead_data.get("company", ""),
            "phone": lead_data.get("phone"),
            "linkedin_url": full_context.get("linkedin_url"),
            "research_insights": {
                "company_info": research_summary.get("company_insights", []),
                "person_info": research_summary.get("person_insights", []),
                "pain_points": research_summary.get("potential_pain_points", []),
                "opportunities": research_summary.get("opportunities", [])
            },
            "linkedin_profile": {
                "headline": linkedin_data.get("headline", ""),
                "summary": linkedin_data.get("summary", ""),
                "experience": linkedin_data.get("recent_experience", [])
            }
        }
    
    def _extract_campaign_context(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract campaign context for message generation.
        
        Args:
            campaign_data: Campaign settings
            
        Returns:
            Campaign context for AI
        """
        return {
            "name": campaign_data.get("name", ""),
            "daily_limits": {
                "email": campaign_data.get("daily_sending_limit_email", 0),
                "linkedin": campaign_data.get("daily_sending_limit_linkedin", 0)
            },
            # Future: Add campaign-specific value propositions, tone, etc.
            "tone": "professional",  # Default for now
            "goal": "schedule_meeting"  # Default for now
        }
    
    async def _generate_email_sequence(
        self,
        lead_context: Dict[str, Any],
        campaign_context: Dict[str, Any],
        campaign_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate email outreach sequence.
        
        Args:
            lead_context: Extracted lead information
            campaign_context: Campaign settings
            campaign_data: Full campaign data including email footer
            
        Returns:
            List of email messages
        """
        try:
            # Create prompt for AI
            prompt = self._create_email_prompt(lead_context, campaign_context)
            
            # Call OpenAI to generate sequence
            client = await self._get_openai_client()
            
            response = await client.chat.completions.create(
                model="anthropic/claude-opus-4",  # Using Claude Opus 4 for high-quality copywriting
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert B2B outreach specialist. Generate personalized, compelling email sequences that get responses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            sequence_data = json.loads(response.choices[0].message.content)
            emails = sequence_data.get("emails", [])
            
            # Add email footer if configured
            email_footer = campaign_data.get("email_footer")
            if email_footer:
                footer_html = email_footer.get("html", "")
                footer_text = email_footer.get("text", "")
                
                for email in emails:
                    if footer_html:
                        email["content"] = f"{email['content']}\n\n{footer_html}"
                    elif footer_text:
                        email["content"] = f"{email['content']}\n\n{footer_text}"
            
            return emails
            
        except Exception as e:
            self.logger.error(f"Failed to generate email sequence: {e}")
            # Return a simple fallback sequence
            return self._get_fallback_email_sequence(lead_context)
    
    async def _generate_linkedin_sequence(
        self,
        lead_context: Dict[str, Any],
        campaign_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate LinkedIn outreach sequence.
        
        Args:
            lead_context: Extracted lead information
            campaign_context: Campaign settings
            
        Returns:
            List of LinkedIn messages
        """
        try:
            # Create prompt for AI
            prompt = self._create_linkedin_prompt(lead_context, campaign_context)
            
            # Call OpenAI to generate sequence
            client = await self._get_openai_client()
            
            response = await client.chat.completions.create(
                model="anthropic/claude-opus-4",  # Using Claude Opus 4 for high-quality copywriting
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert LinkedIn outreach specialist. Generate personalized, conversational messages that build genuine connections."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            sequence_data = json.loads(response.choices[0].message.content)
            return sequence_data.get("messages", [])
            
        except Exception as e:
            self.logger.error(f"Failed to generate LinkedIn sequence: {e}")
            # Return a simple fallback sequence
            return self._get_fallback_linkedin_sequence(lead_context)
    
    def _create_email_prompt(self, lead_context: Dict[str, Any], campaign_context: Dict[str, Any]) -> str:
        """Create prompt for email sequence generation"""
        return f"""
        Generate a 3-email outreach sequence for the following lead:
        
        Lead Information:
        - Name: {lead_context['name']}
        - Title: {lead_context['title']}
        - Company: {lead_context['company']}
        - Email: {lead_context['email']}
        
        Research Insights:
        - Company Info: {json.dumps(lead_context['research_insights']['company_info'][:3])}
        - Person Info: {json.dumps(lead_context['research_insights']['person_info'][:3])}
        - Pain Points: {json.dumps(lead_context['research_insights']['pain_points'][:2])}
        
        Campaign Goal: {campaign_context['goal']}
        Tone: {campaign_context['tone']}
        
        Generate exactly 3 emails:
        1. Initial outreach (day 1) - Personalized, value-focused, clear CTA
        2. Follow-up (day 3) - Add value, different angle, maintain context
        3. Final follow-up (day 7) - Brief, direct, create urgency
        
        Return JSON with this structure:
        {{
            "emails": [
                {{
                    "sequence_number": 1,
                    "subject": "subject line",
                    "content": "email body (plain text, use \\n for line breaks)",
                    "day_delay": 0
                }},
                {{
                    "sequence_number": 2,
                    "subject": "subject line",
                    "content": "email body",
                    "day_delay": 3
                }},
                {{
                    "sequence_number": 3,
                    "subject": "subject line",
                    "content": "email body",
                    "day_delay": 7
                }}
            ]
        }}
        
        Make emails concise, personalized, and focused on the lead's potential challenges.
        """
    
    def _create_linkedin_prompt(self, lead_context: Dict[str, Any], campaign_context: Dict[str, Any]) -> str:
        """Create prompt for LinkedIn sequence generation"""
        return f"""
        Generate a 2-message LinkedIn outreach sequence for the following lead:
        
        Lead Information:
        - Name: {lead_context['name']}
        - Title: {lead_context['title']}
        - Company: {lead_context['company']}
        - LinkedIn: {lead_context['linkedin_url']}
        
        LinkedIn Profile:
        - Headline: {lead_context['linkedin_profile']['headline']}
        - Recent Experience: {json.dumps(lead_context['linkedin_profile']['experience'][:2])}
        
        Research Insights:
        - Person Info: {json.dumps(lead_context['research_insights']['person_info'][:2])}
        - Opportunities: {json.dumps(lead_context['research_insights']['opportunities'][:2])}
        
        Campaign Goal: {campaign_context['goal']}
        Tone: Conversational and professional
        
        Generate exactly 2 messages:
        1. Connection request (day 1) - Brief, personalized note referencing something specific
        2. Follow-up message (day 3 after connection) - Value-focused, conversational, soft CTA
        
        Return JSON with this structure:
        {{
            "messages": [
                {{
                    "sequence_number": 1,
                    "type": "connection_request",
                    "content": "connection request note (max 300 chars)",
                    "day_delay": 0
                }},
                {{
                    "sequence_number": 2,
                    "type": "message",
                    "content": "follow-up message",
                    "day_delay": 3
                }}
            ]
        }}
        
        Keep messages natural, avoid being salesy, focus on building genuine connection.
        """
    
    def _get_fallback_email_sequence(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate fallback email sequence if AI fails"""
        name = lead_context['name'].split()[0] if lead_context['name'] else "there"
        company = lead_context['company'] or "your company"
        
        return [
            {
                "sequence_number": 1,
                "subject": f"Quick question about {company}'s growth",
                "content": f"Hi {name},\n\nI noticed {company} has been making impressive strides in the market. "
                          f"I've helped similar companies accelerate their growth and would love to share some insights.\n\n"
                          f"Would you be open to a brief 15-minute call next week?\n\nBest regards",
                "day_delay": 0
            },
            {
                "sequence_number": 2,
                "subject": f"Re: Quick question about {company}'s growth",
                "content": f"Hi {name},\n\nI wanted to follow up on my previous email. "
                          f"I've put together some specific ideas that could benefit {company}.\n\n"
                          f"Are you the right person to discuss this with, or could you point me in the right direction?\n\nThanks",
                "day_delay": 3
            },
            {
                "sequence_number": 3,
                "subject": "Final follow-up",
                "content": f"Hi {name},\n\nI haven't heard back and understand you're busy. "
                          f"If exploring growth opportunities isn't a priority right now, no worries.\n\n"
                          f"Should I close the loop on this, or is there a better time to reconnect?\n\nBest",
                "day_delay": 7
            }
        ]
    
    def _get_fallback_linkedin_sequence(self, lead_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate fallback LinkedIn sequence if AI fails"""
        name = lead_context['name'].split()[0] if lead_context['name'] else "there"
        title = lead_context['title'] or "your role"
        
        return [
            {
                "sequence_number": 1,
                "type": "connection_request",
                "content": f"Hi {name}, I'm impressed by your work as {title}. Would love to connect and exchange insights.",
                "day_delay": 0
            },
            {
                "sequence_number": 2,
                "type": "message",
                "content": f"Hi {name}, thanks for connecting! I've been following your company's journey and have some ideas "
                          f"that might be valuable. Would you be open to a quick chat to explore potential synergies?",
                "day_delay": 3
            }
        ]