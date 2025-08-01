#!/usr/bin/env python3
"""
Test script to validate Tavily tool improvements.
Tests async functionality, parallel searches, and LinkedIn extraction.
"""

import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.agent.tools.tavily_tool import TavilyTool

async def test_tavily_improvements():
    """Test the improved Tavily tool functionality"""
    
    # Initialize the tool
    tavily_tool = TavilyTool()
    
    # Test data
    test_lead = {
        "first_name": "Satya",
        "last_name": "Nadella",
        "company": "Microsoft",
        "title": "CEO",
        "email": "satya@microsoft.com",
        "full_context": {
            "linkedin_url": "https://www.linkedin.com/in/satyanadella/"
        }
    }
    
    test_campaign = {
        "id": "test-campaign-123",
        "name": "Tech Leaders Outreach"
    }
    
    logger.info("Starting Tavily tool improvement tests...")
    
    # Test 1: Basic research with parallel searches
    logger.info("\nTest 1: Testing parallel search functionality")
    start_time = datetime.now()
    
    result = await tavily_tool.execute(
        lead_data=test_lead,
        campaign_data=test_campaign
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if result.success:
        logger.info(f"✅ Parallel search completed in {duration:.2f} seconds")
        logger.info(f"Research summary keys: {list(result.data.get('summary', {}).keys())}")
        
        # Check if all expected research types were performed
        research_data = result.data.get('research_data', {})
        expected_keys = ['person_info', 'company_info', 'recent_news', 'industry_insights']
        found_keys = [k for k in expected_keys if k in research_data and research_data[k]]
        
        logger.info(f"Research types completed: {found_keys}")
        
        # Display sample results
        if 'person_info' in research_data and research_data['person_info'].get('answer'):
            logger.info(f"\nPerson research answer preview: {research_data['person_info']['answer'][:200]}...")
            
        if 'company_info' in research_data and research_data['company_info'].get('sources'):
            sources = research_data['company_info']['sources']
            logger.info(f"\nCompany sources found: {len(sources)}")
            for source in sources[:2]:  # Show first 2 sources
                logger.info(f"  - {source.get('title')} (score: {source.get('score', 0):.2f})")
    else:
        logger.error(f"❌ Research failed: {result.error}")
    
    # Test 2: LinkedIn extraction
    logger.info("\nTest 2: Testing LinkedIn extraction")
    
    if test_lead['full_context'].get('linkedin_url'):
        extract_result = await tavily_tool.extract_from_urls(
            urls=[test_lead['full_context']['linkedin_url']],
            extract_depth="advanced"
        )
        
        if extract_result.success:
            logger.info("✅ LinkedIn extraction successful")
            extracted = extract_result.data.get('extracted_content', [])
            if extracted:
                logger.info(f"Extracted content length: {len(extracted[0].get('raw_content', ''))} characters")
        else:
            logger.error(f"❌ LinkedIn extraction failed: {extract_result.error}")
    
    # Test 3: Credit usage tracking
    logger.info("\nTest 3: Credit usage report")
    credit_report = tavily_tool.get_credit_usage_report()
    logger.info(f"Credit usage report:")
    logger.info(f"  - Total credits used: {credit_report['total_credits_used']}")
    logger.info(f"  - Basic searches: {credit_report['basic_searches']}")
    logger.info(f"  - Advanced searches: {credit_report['advanced_searches']}")
    logger.info(f"  - Extractions: {credit_report['extractions']}")
    logger.info(f"  - Estimated cost: ${credit_report['estimated_cost']:.2f}")
    
    # Test 4: Rate limiting
    logger.info("\nTest 4: Testing rate limiting")
    
    # Try to make multiple rapid requests
    rapid_queries = []
    for i in range(5):
        rapid_queries.append(
            tavily_tool.execute(
                lead_data={
                    "first_name": f"Test{i}",
                    "last_name": "User",
                    "company": "TestCorp",
                    "title": "Manager"
                },
                campaign_data=test_campaign
            )
        )
    
    # Execute all at once
    rapid_results = await asyncio.gather(*rapid_queries, return_exceptions=True)
    
    successful = sum(1 for r in rapid_results if not isinstance(r, Exception) and r.success)
    logger.info(f"Rapid requests - Successful: {successful}/5")
    
    logger.info("\n✅ All tests completed!")
    
    # Final credit usage
    final_credit_report = tavily_tool.get_credit_usage_report()
    logger.info(f"\nFinal credit usage: {final_credit_report['total_credits_used']} credits")
    logger.info(f"Final estimated cost: ${final_credit_report['estimated_cost']:.2f}")


if __name__ == "__main__":
    # Run the async test
    asyncio.run(test_tavily_improvements())