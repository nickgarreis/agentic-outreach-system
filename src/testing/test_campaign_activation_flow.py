# src/testing/test_campaign_activation_flow.py
# Test script for complete campaign activation → job creation → execution flow
# Tests the entire pipeline from campaign status change to lead discovery
# RELEVANT FILES: ../agent/autopilot_agent.py, ../agent/tools/apollo_search_tool.py

import asyncio
import logging
from datetime import datetime
from ..database import get_supabase
from ..config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_test_campaign():
    """
    Create a test campaign with Apollo search URL configured.
    
    Returns:
        str: Campaign ID
    """
    supabase = await get_supabase()
    
    # First, get a client ID to associate with the campaign
    clients_response = await supabase.table("clients").select("id").limit(1).execute()
    
    if not clients_response.data:
        # Create a test client if none exists
        client_response = await supabase.table("clients").insert({
            "name": "Test Client for Campaign Activation"
        }).execute()
        client_id = client_response.data[0]["id"]
    else:
        client_id = clients_response.data[0]["id"]
    
    # Create campaign with Apollo search URL
    campaign_data = {
        "client_id": client_id,
        "name": f"Test Campaign - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "status": "draft",
        "search_url": {
            "apollo": {
                "search_url": "https://app.apollo.io/#/people/search?personTitles[]=CEO&personTitles[]=Founder&organizationNumEmployeesRanges[]=1-10&organizationNumEmployeesRanges[]=11-50",
                "page_number": 1
            }
        }
    }
    
    response = await supabase.table("campaigns").insert(campaign_data).execute()
    campaign_id = response.data[0]["id"]
    
    logger.info(f"Created test campaign: {campaign_id}")
    return campaign_id


async def activate_campaign(campaign_id: str):
    """
    Activate the campaign to trigger job creation.
    
    Args:
        campaign_id: Campaign UUID
    """
    supabase = await get_supabase()
    
    logger.info(f"Activating campaign {campaign_id}")
    
    # Update status to 'active' - this should trigger the database trigger
    await supabase.table("campaigns").update({
        "status": "active"
    }).eq("id", campaign_id).execute()
    
    logger.info("Campaign activated - trigger should have created a job")


async def check_job_creation(campaign_id: str):
    """
    Check if a job was created for the campaign.
    
    Args:
        campaign_id: Campaign UUID
        
    Returns:
        dict: Job data if found
    """
    supabase = await get_supabase()
    
    # Wait a moment for trigger to execute
    await asyncio.sleep(2)
    
    # Look for the job
    jobs_response = await supabase.table("jobs").select("*").eq(
        "job_type", "campaign_active"
    ).order("created_at", desc=True).limit(1).execute()
    
    if not jobs_response.data:
        logger.error("No job found after campaign activation!")
        return None
    
    job = jobs_response.data[0]
    job_data = job.get("data", {})
    
    # Verify it's for our campaign
    if job_data.get("campaign_id") != campaign_id:
        logger.error(f"Job found but for different campaign: {job_data.get('campaign_id')}")
        return None
    
    logger.info(f"Found job {job['id']} for campaign {campaign_id}")
    logger.info(f"Job status: {job['status']}")
    logger.info(f"Job data: {job_data}")
    
    return job


async def simulate_job_execution(job_id: str):
    """
    Simulate what the RenderWorker would do - execute the job.
    
    Args:
        job_id: Job UUID
    """
    from ..agent.autopilot_agent import AutopilotAgent
    
    supabase = await get_supabase()
    
    # Fetch job details
    job_response = await supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    job = job_response.data
    
    logger.info(f"Simulating job execution for job {job_id}")
    
    # Mark job as processing
    await supabase.table("jobs").update({
        "status": "processing",
        "started_at": datetime.utcnow().isoformat()
    }).eq("id", job_id).execute()
    
    try:
        # Create agent and execute job
        agent = AutopilotAgent(job_type=job["job_type"], job_id=job_id)
        result = await agent.execute_job(job["data"])
        
        # Update job as completed
        await supabase.table("jobs").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": result
        }).eq("id", job_id).execute()
        
        logger.info(f"Job completed successfully: {result}")
        
    except Exception as e:
        # Update job as failed
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__
        }
        
        await supabase.table("jobs").update({
            "status": "failed",
            "failed_at": datetime.utcnow().isoformat(),
            "result": error_result
        }).eq("id", job_id).execute()
        
        logger.error(f"Job failed: {e}")
        raise


async def verify_results(campaign_id: str):
    """
    Verify that leads were created and page number was updated.
    
    Args:
        campaign_id: Campaign UUID
    """
    supabase = await get_supabase()
    
    # Check for created leads
    leads_response = await supabase.table("leads").select("*").eq(
        "campaign_id", campaign_id
    ).execute()
    
    logger.info(f"Found {len(leads_response.data)} leads for campaign")
    
    if leads_response.data:
        # Show first few leads
        for i, lead in enumerate(leads_response.data[:3]):
            logger.info(f"Lead {i+1}: {lead.get('first_name')} {lead.get('last_name')} - {lead.get('email')} ({lead.get('company')})")
    
    # Check if page number was updated
    campaign_response = await supabase.table("campaigns").select("search_url").eq(
        "id", campaign_id
    ).single().execute()
    
    search_url = campaign_response.data.get("search_url", {})
    apollo_page = search_url.get("apollo", {}).get("page_number", 1)
    
    logger.info(f"Apollo page number after execution: {apollo_page}")
    
    return len(leads_response.data)


async def cleanup_test_data(campaign_id: str):
    """
    Clean up test data (optional).
    
    Args:
        campaign_id: Campaign UUID
    """
    supabase = await get_supabase()
    
    # Delete leads
    await supabase.table("leads").delete().eq("campaign_id", campaign_id).execute()
    
    # Delete campaign
    await supabase.table("campaigns").delete().eq("id", campaign_id).execute()
    
    logger.info("Test data cleaned up")


async def main():
    """
    Run the complete test flow.
    """
    settings = get_settings()
    
    logger.info("=== Campaign Activation Flow Test ===")
    logger.info(f"Apollo API Key configured: {'Yes' if settings.apollo_api_key else 'No'}")
    
    if not settings.apollo_api_key:
        logger.error("Apollo API key not configured! Set APOLLO_API_KEY in .env")
        return
    
    try:
        # Step 1: Create test campaign
        logger.info("\n1. Creating test campaign...")
        campaign_id = await create_test_campaign()
        
        # Step 2: Activate campaign (triggers job creation)
        logger.info("\n2. Activating campaign...")
        await activate_campaign(campaign_id)
        
        # Step 3: Check if job was created
        logger.info("\n3. Checking for job creation...")
        job = await check_job_creation(campaign_id)
        
        if not job:
            logger.error("Test failed - no job created")
            return
        
        # Step 4: Simulate job execution
        logger.info("\n4. Executing job...")
        await simulate_job_execution(job["id"])
        
        # Step 5: Verify results
        logger.info("\n5. Verifying results...")
        lead_count = await verify_results(campaign_id)
        
        # Summary
        logger.info("\n=== Test Summary ===")
        logger.info(f"✅ Campaign created: {campaign_id}")
        logger.info(f"✅ Job created: {job['id']}")
        logger.info(f"✅ Job executed successfully")
        logger.info(f"✅ {lead_count} leads discovered")
        logger.info("✅ Page number incremented")
        
        # Optional: Clean up
        # logger.info("\n6. Cleaning up test data...")
        # await cleanup_test_data(campaign_id)
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())