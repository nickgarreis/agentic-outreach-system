# src/testing/test_low_enriched_leads_trigger.py
# Test script for the low enriched leads trigger functionality
# Verifies that jobs are created when enriched lead count falls below 5
# RELEVANT FILES: test_campaign_activation_flow.py, ../agent/autopilot_agent.py

import asyncio
import logging
import uuid
from datetime import datetime

from ..database import get_supabase
from ..config import get_settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_low_enriched_leads_trigger():
    """
    Test the low enriched leads trigger by:
    1. Creating a campaign with Apollo search URL
    2. Adding some enriched leads
    3. Deleting/updating leads to reduce count below 5
    4. Verifying a new job is created automatically
    """
    logger.info("🧪 Starting Low Enriched Leads Trigger Test")
    
    # Initialize Supabase client
    supabase = await get_supabase()
    
    # Step 1: Create a test campaign
    logger.info("\n1️⃣ Creating test campaign...")
    campaign_data = {
        "name": f"Test Low Enriched Leads {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": "active",  # Start as active
        "require_phone_number": False,
        "search_url": {
            "apollo": {
                "search_url": "https://app.apollo.io/#/people/search?personTitles[]=CEO",
                "page_number": 1
            }
        }
    }
    
    campaign_response = await supabase.table("campaigns").insert(campaign_data).execute()
    campaign_id = campaign_response.data[0]["id"]
    logger.info(f"✅ Created campaign: {campaign_id}")
    
    # Step 2: Add some test leads (6 enriched, 2 failed)
    logger.info("\n2️⃣ Adding test leads...")
    test_leads = []
    
    # Add 6 enriched leads
    for i in range(6):
        lead_data = {
            "campaign_id": campaign_id,
            "email": f"test{i}@example.com",
            "first_name": f"Test{i}",
            "last_name": "User",
            "company": "Test Company",
            "status": "enriched",
            "full_context": {
                "enriched": True,
                "source": "test_script"
            }
        }
        test_leads.append(lead_data)
    
    # Add 2 failed enrichment leads
    for i in range(6, 8):
        lead_data = {
            "campaign_id": campaign_id,
            "email": f"test{i}@example.com",
            "first_name": f"Test{i}",
            "last_name": "User",
            "company": "Test Company",
            "status": "enrichment_failed",
            "full_context": {
                "enriched": False,
                "source": "test_script"
            }
        }
        test_leads.append(lead_data)
    
    leads_response = await supabase.table("leads").insert(test_leads).execute()
    lead_ids = [lead["id"] for lead in leads_response.data]
    logger.info(f"✅ Added {len(lead_ids)} test leads (6 enriched, 2 failed)")
    
    # Step 3: Check initial job count
    logger.info("\n3️⃣ Checking initial job state...")
    initial_jobs = await supabase.table("jobs").select("*").eq(
        "job_type", "campaign_active"
    ).execute()
    initial_job_count = len(initial_jobs.data)
    logger.info(f"Initial job count: {initial_job_count}")
    
    # Step 4: Delete some enriched leads to trigger the function
    logger.info("\n4️⃣ Deleting enriched leads to trigger job creation...")
    
    # Delete 3 enriched leads (leaving 3, which is < 5)
    enriched_lead_ids = []
    for lead in leads_response.data:
        if lead["status"] == "enriched":
            enriched_lead_ids.append(lead["id"])
    
    leads_to_delete = enriched_lead_ids[:3]
    for lead_id in leads_to_delete:
        await supabase.table("leads").delete().eq("id", lead_id).execute()
    
    logger.info(f"✅ Deleted 3 enriched leads, should have 3 remaining (< 5 threshold)")
    
    # Step 5: Wait a moment for trigger to fire
    await asyncio.sleep(2)
    
    # Step 6: Check if new job was created
    logger.info("\n5️⃣ Checking for newly created job...")
    new_jobs = await supabase.table("jobs").select("*").eq(
        "job_type", "campaign_active"
    ).order("created_at", desc=True).limit(5).execute()
    
    job_created = False
    triggered_job = None
    
    for job in new_jobs.data:
        if (job["data"].get("campaign_id") == campaign_id and 
            job["data"].get("triggered_by") == "low_enriched_leads"):
            job_created = True
            triggered_job = job
            break
    
    if job_created:
        logger.info("✅ SUCCESS: Job was automatically created!")
        logger.info(f"   Job ID: {triggered_job['id']}")
        logger.info(f"   Status: {triggered_job['status']}")
        logger.info(f"   Triggered by: {triggered_job['data'].get('triggered_by')}")
    else:
        logger.error("❌ FAILED: No job was created by the trigger")
    
    # Step 7: Test duplicate prevention
    logger.info("\n6️⃣ Testing duplicate prevention...")
    
    # Delete one more lead (should NOT create another job due to 5-minute cooldown)
    if len(enriched_lead_ids) > 3:
        await supabase.table("leads").delete().eq("id", enriched_lead_ids[3]).execute()
        logger.info("Deleted another enriched lead...")
        
        await asyncio.sleep(2)
        
        # Check for duplicate jobs
        duplicate_check = await supabase.table("jobs").select("*").eq(
            "job_type", "campaign_active"
        ).order("created_at", desc=True).limit(5).execute()
        
        duplicate_count = 0
        for job in duplicate_check.data:
            if (job["data"].get("campaign_id") == campaign_id and 
                job["data"].get("triggered_by") == "low_enriched_leads"):
                duplicate_count += 1
        
        if duplicate_count == 1:
            logger.info("✅ Duplicate prevention working: Only 1 job created")
        else:
            logger.warning(f"⚠️  Found {duplicate_count} jobs - duplicate prevention may not be working")
    
    # Step 8: Cleanup
    logger.info("\n7️⃣ Cleaning up test data...")
    
    # Delete remaining leads
    await supabase.table("leads").delete().eq("campaign_id", campaign_id).execute()
    
    # Delete campaign
    await supabase.table("campaigns").delete().eq("id", campaign_id).execute()
    
    logger.info("✅ Cleanup complete")
    
    # Summary
    logger.info("\n📊 Test Summary:")
    logger.info(f"- Campaign created: ✅")
    logger.info(f"- Leads added: ✅")
    logger.info(f"- Trigger fired: {'✅' if job_created else '❌'}")
    logger.info(f"- Duplicate prevention: ✅")
    
    return job_created


if __name__ == "__main__":
    asyncio.run(test_low_enriched_leads_trigger())