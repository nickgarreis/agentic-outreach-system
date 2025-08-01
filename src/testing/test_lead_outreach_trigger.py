# src/testing/test_lead_outreach_trigger.py
# Tests the lead outreach trigger and message scheduling functionality
# Verifies that status change to 'researched' creates jobs and schedules messages properly
# RELEVANT FILES: ../agent/autopilot_agent.py, ../agent/tools/outreach_generator.py, ../agent/tools/message_scheduler.py

import asyncio
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)


async def setup_test_data():
    """Create test campaign and lead for testing outreach trigger"""
    print("\n=== Setting up test data ===")
    
    # Create a test campaign with outreach settings
    campaign_data = {
        "name": "Test Outreach Campaign",
        "status": "active",
        "email_outreach": True,
        "linkedin_outreach": True,
        "daily_sending_limit_email": 5,
        "daily_sending_limit_linkedin": 3,
        "email_footer": {
            "text": "Best regards,\nThe Sales Team\n\nUnsubscribe: {{unsubscribe_link}}"
        }
    }
    
    campaign_response = supabase.table("campaigns").insert(campaign_data).execute()
    campaign = campaign_response.data[0]
    print(f"✓ Created campaign: {campaign['id']}")
    
    # Create a test lead in 'enriched' status
    lead_data = {
        "campaign_id": campaign["id"],
        "first_name": "John",
        "last_name": "TestLead",
        "email": "john.testlead@example.com",
        "company": "Test Company Inc",
        "title": "VP of Engineering",
        "status": "enriched",
        "full_context": {
            "linkedin_url": "https://linkedin.com/in/john-testlead",
            "enriched": True,
            "personal_emails": ["john@personal.com"],
            "tavily_research": {
                "summary": {
                    "company_insights": [
                        "Test Company Inc recently raised $50M Series B",
                        "Expanding engineering team by 50%"
                    ],
                    "person_insights": [
                        "John has 15 years experience in SaaS",
                        "Previously CTO at StartupXYZ"
                    ],
                    "potential_pain_points": [
                        "Scaling engineering team rapidly",
                        "Technical debt from rapid growth"
                    ],
                    "opportunities": [
                        "Looking for developer productivity tools",
                        "Interested in DevOps automation"
                    ]
                }
            }
        }
    }
    
    lead_response = supabase.table("leads").insert(lead_data).execute()
    lead = lead_response.data[0]
    print(f"✓ Created lead: {lead['id']} - {lead['first_name']} {lead['last_name']}")
    
    return campaign, lead


async def test_trigger_activation():
    """Test that changing lead status to 'researched' creates an outreach job"""
    print("\n=== Testing trigger activation ===")
    
    campaign, lead = await setup_test_data()
    
    # Check no jobs exist yet
    jobs_before = supabase.table("jobs")\
        .select("*")\
        .eq("job_type", "lead_outreach")\
        .eq("data->>lead_id", lead["id"])\
        .execute()
    
    print(f"Jobs before status change: {len(jobs_before.data)}")
    
    # Update lead status to 'researched' - this should trigger job creation
    print(f"Updating lead status to 'researched'...")
    update_response = supabase.table("leads")\
        .update({"status": "researched"})\
        .eq("id", lead["id"])\
        .execute()
    
    # Wait a moment for trigger to execute
    await asyncio.sleep(2)
    
    # Check if job was created
    jobs_after = supabase.table("jobs")\
        .select("*")\
        .eq("job_type", "lead_outreach")\
        .eq("data->>lead_id", lead["id"])\
        .execute()
    
    print(f"Jobs after status change: {len(jobs_after.data)}")
    
    if jobs_after.data:
        job = jobs_after.data[0]
        print(f"✓ Job created successfully!")
        print(f"  - Job ID: {job['id']}")
        print(f"  - Status: {job['status']}")
        print(f"  - Priority: {job['priority']}")
        print(f"  - Data: {job['data']}")
        
        # Verify job data contains expected fields
        assert job['data']['lead_id'] == lead['id']
        assert job['data']['campaign_id'] == campaign['id']
        assert job['data']['enabled_channels']['email'] == True
        assert job['data']['enabled_channels']['linkedin'] == True
        assert job['data']['daily_limits']['email'] == 5
        assert job['data']['daily_limits']['linkedin'] == 3
        print("✓ Job data validated successfully!")
    else:
        print("✗ No job created - trigger may have failed")
    
    return campaign, lead, jobs_after.data[0] if jobs_after.data else None


async def test_duplicate_prevention():
    """Test that trigger doesn't create duplicate jobs"""
    print("\n=== Testing duplicate job prevention ===")
    
    campaign, lead, job = await test_trigger_activation()
    
    if not job:
        print("✗ Cannot test duplicate prevention - no initial job created")
        return
    
    # Try to update status again (simulating duplicate trigger)
    print("Attempting to trigger again by updating lead...")
    
    # First change to different status
    supabase.table("leads")\
        .update({"status": "enriched"})\
        .eq("id", lead["id"])\
        .execute()
    
    await asyncio.sleep(1)
    
    # Then back to researched
    supabase.table("leads")\
        .update({"status": "researched"})\
        .eq("id", lead["id"])\
        .execute()
    
    await asyncio.sleep(2)
    
    # Check job count
    all_jobs = supabase.table("jobs")\
        .select("*")\
        .eq("job_type", "lead_outreach")\
        .eq("data->>lead_id", lead["id"])\
        .execute()
    
    print(f"Total jobs for this lead: {len(all_jobs.data)}")
    
    if len(all_jobs.data) == 1:
        print("✓ Duplicate prevention working - only 1 job created")
    else:
        print(f"✗ Duplicate prevention failed - {len(all_jobs.data)} jobs created")


async def test_message_scheduling():
    """Test the complete flow including message scheduling"""
    print("\n=== Testing message scheduling (requires worker) ===")
    
    # Note: This test requires the render worker to be running
    # to actually process the job and create messages
    
    campaign, lead, job = await test_trigger_activation()
    
    if not job:
        print("✗ Cannot test message scheduling - no job created")
        return
    
    print("Waiting for worker to process job (30 seconds)...")
    await asyncio.sleep(30)
    
    # Check if job was processed
    processed_job = supabase.table("jobs")\
        .select("*")\
        .eq("id", job["id"])\
        .single()\
        .execute()
    
    if processed_job.data:
        job_status = processed_job.data["status"]
        print(f"Job status: {job_status}")
        
        if job_status == "completed":
            print("✓ Job processed successfully!")
            
            # Check for created messages
            messages = supabase.table("messages")\
                .select("*")\
                .eq("lead_id", lead["id"])\
                .eq("campaign_id", campaign["id"])\
                .order("send_at")\
                .execute()
            
            print(f"\nMessages created: {len(messages.data)}")
            
            for idx, msg in enumerate(messages.data):
                send_at = datetime.fromisoformat(msg['send_at'].replace('Z', '+00:00'))
                print(f"\nMessage {idx + 1}:")
                print(f"  - Channel: {msg['channel']}")
                print(f"  - Status: {msg['status']}")
                print(f"  - Send at: {send_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  - Subject: {msg.get('subject', 'N/A')}")
                print(f"  - Content preview: {msg['content'][:100]}...")
            
            # Verify scheduling constraints
            if len(messages.data) > 1:
                print("\n=== Verifying scheduling constraints ===")
                
                # Group by channel and date
                by_channel_date = {}
                for msg in messages.data:
                    channel = msg['channel']
                    send_at = datetime.fromisoformat(msg['send_at'].replace('Z', '+00:00'))
                    date_key = send_at.date()
                    
                    if channel not in by_channel_date:
                        by_channel_date[channel] = {}
                    if date_key not in by_channel_date[channel]:
                        by_channel_date[channel][date_key] = []
                    
                    by_channel_date[channel][date_key].append(send_at)
                
                # Check daily limits
                for channel, dates in by_channel_date.items():
                    for date, times in dates.items():
                        count = len(times)
                        limit = campaign[f'daily_sending_limit_{channel}']
                        print(f"{channel} on {date}: {count} messages (limit: {limit})")
                        
                        if count <= limit:
                            print(f"  ✓ Within daily limit")
                        else:
                            print(f"  ✗ Exceeds daily limit!")
                
                # Check time gaps within same campaign
                all_times = sorted([
                    datetime.fromisoformat(msg['send_at'].replace('Z', '+00:00'))
                    for msg in messages.data
                ])
                
                print("\nChecking message timing gaps:")
                for i in range(1, len(all_times)):
                    gap = (all_times[i] - all_times[i-1]).total_seconds() / 60
                    print(f"  Gap between message {i} and {i+1}: {gap:.1f} minutes")
                    
                    if gap >= 5:
                        print(f"    ✓ Meets 5-minute minimum")
                    else:
                        print(f"    ✗ Below 5-minute minimum!")
            
        elif job_status == "failed":
            print(f"✗ Job failed: {processed_job.data.get('result', {}).get('error', 'Unknown error')}")
        else:
            print(f"Job still in status: {job_status}")
            print("Worker may still be processing or not running")


async def cleanup_test_data():
    """Clean up test data after tests"""
    print("\n=== Cleaning up test data ===")
    
    # Delete test campaigns and related data
    test_campaigns = supabase.table("campaigns")\
        .select("id")\
        .like("name", "%Test Outreach Campaign%")\
        .execute()
    
    for campaign in test_campaigns.data:
        campaign_id = campaign["id"]
        
        # Delete messages
        supabase.table("messages")\
            .delete()\
            .eq("campaign_id", campaign_id)\
            .execute()
        
        # Delete leads
        supabase.table("leads")\
            .delete()\
            .eq("campaign_id", campaign_id)\
            .execute()
        
        # Delete jobs
        supabase.table("jobs")\
            .delete()\
            .eq("data->>campaign_id", campaign_id)\
            .execute()
        
        # Delete campaign
        supabase.table("campaigns")\
            .delete()\
            .eq("id", campaign_id)\
            .execute()
        
        print(f"✓ Cleaned up campaign: {campaign_id}")


async def main():
    """Run all tests"""
    print("=== Lead Outreach Trigger Test Suite ===")
    print("Testing the automated outreach system...")
    
    try:
        # Run tests
        await test_duplicate_prevention()
        
        # Optionally test full flow with worker
        # Uncomment if render worker is running
        # await test_message_scheduling()
        
    finally:
        # Always cleanup
        await cleanup_test_data()
    
    print("\n✓ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())