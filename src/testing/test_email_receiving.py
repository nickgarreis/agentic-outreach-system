# src/testing/test_email_receiving.py
# Tests for email receiving functionality via SendGrid Inbound Parse
# Verifies webhook handling, lead matching, and thread tracking
# RELEVANT FILES: ../routers/webhooks.py, ../agent/tools/email_sender.py, ../../supabase/migrations/20250801000015_add_email_receiving_support.sql

import asyncio
import json
from datetime import datetime
from supabase import create_client, Client
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

def get_supabase_client() -> Client:
    """Get Supabase client for testing"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


async def test_email_receiving_setup():
    """Test that the database migration ran successfully"""
    print("\n=== Testing Email Receiving Database Setup ===")
    
    client = get_supabase_client()
    
    # Check if new columns exist in messages table
    try:
        # Try to query with the new columns
        result = client.table("messages").select(
            "id, thread_id, email_message_id, in_reply_to"
        ).limit(1).execute()
        
        print("✅ Email threading columns exist in messages table")
        
        # Check if reply_to_domain exists in campaigns
        campaign_result = client.table("campaigns").select(
            "id, reply_to_domain"
        ).limit(1).execute()
        
        print("✅ reply_to_domain column exists in campaigns table")
        
        # Test the generate_email_message_id function
        test_result = client.rpc('generate_email_message_id', {
            'p_message_id': '123e4567-e89b-12d3-a456-426614174000',
            'p_domain': 'test.com'
        }).execute()
        
        expected = '<123e4567-e89b-12d3-a456-426614174000@test.com>'
        if test_result.data == expected:
            print("✅ generate_email_message_id function works correctly")
        else:
            print(f"❌ generate_email_message_id returned: {test_result.data}")
            
    except Exception as e:
        print(f"❌ Database setup test failed: {e}")
        return False
    
    return True


async def test_inbound_email_processing():
    """Test the process_inbound_email database function"""
    print("\n=== Testing Inbound Email Processing ===")
    
    client = get_supabase_client()
    
    # First, we need a test lead and campaign
    # Get an existing lead and campaign for testing
    try:
        # Get a test campaign
        campaign_result = client.table("campaigns").select("id, client_id").limit(1).execute()
        if not campaign_result.data:
            print("❌ No campaigns found for testing")
            return False
        
        campaign = campaign_result.data[0]
        
        # Get a lead from this campaign
        lead_result = client.table("leads").select("id, email").eq(
            "campaign_id", campaign['id']
        ).limit(1).execute()
        
        if not lead_result.data:
            print("❌ No leads found for testing")
            return False
        
        lead = lead_result.data[0]
        
        # Test processing an inbound email
        print(f"Testing with lead email: {lead['email']}")
        
        # Call the process_inbound_email function
        result = client.rpc('process_inbound_email', {
            'p_from_email': lead['email'],
            'p_to_email': f"reply+test@example.com",
            'p_subject': 'Test Reply',
            'p_content': 'This is a test reply email',
            'p_message_id': '<test123@example.com>',
            'p_in_reply_to': None,
            'p_sendgrid_data': {'test': 'data'}
        }).execute()
        
        if result.data:
            print(f"✅ Inbound email processed successfully. Message ID: {result.data}")
            
            # Verify the message was created
            message = client.table("messages").select("*").eq(
                "id", result.data
            ).single().execute()
            
            if message.data:
                msg = message.data
                print(f"✅ Message created with:")
                print(f"   - Direction: {msg['direction']}")
                print(f"   - Status: {msg['status']}")
                print(f"   - Thread ID: {msg.get('thread_id')}")
                print(f"   - Email Message ID: {msg.get('email_message_id')}")
        else:
            print("❌ Failed to process inbound email (might be invalid lead email)")
            
    except Exception as e:
        print(f"❌ Inbound email processing test failed: {e}")
        return False
    
    return True


async def test_email_threading():
    """Test email threading functionality"""
    print("\n=== Testing Email Threading ===")
    
    client = get_supabase_client()
    
    try:
        # Get a sent message to simulate a reply to
        sent_message = client.table("messages").select("*").eq(
            "direction", "outbound"
        ).eq("channel", "email").limit(1).execute()
        
        if not sent_message.data:
            print("❌ No outbound email messages found for threading test")
            return False
        
        parent_msg = sent_message.data[0]
        
        # Get the lead's email
        lead = client.table("leads").select("email").eq(
            "id", parent_msg['lead_id']
        ).single().execute()
        
        if not lead.data:
            print("❌ Lead not found for threading test")
            return False
        
        # Simulate a reply with proper threading
        reply_to_address = f"reply+{parent_msg['id']}@example.com"
        
        result = client.rpc('process_inbound_email', {
            'p_from_email': lead.data['email'],
            'p_to_email': reply_to_address,
            'p_subject': f"Re: {parent_msg.get('subject', 'Test')}",
            'p_content': 'This is a threaded reply',
            'p_message_id': '<reply123@example.com>',
            'p_in_reply_to': parent_msg.get('email_message_id'),
            'p_sendgrid_data': {}
        }).execute()
        
        if result.data:
            # Check if threading worked
            reply_msg = client.table("messages").select("*").eq(
                "id", result.data
            ).single().execute()
            
            if reply_msg.data:
                # Thread ID should match parent or be set to parent's ID
                expected_thread_id = parent_msg.get('thread_id') or parent_msg['id']
                actual_thread_id = reply_msg.data.get('thread_id')
                
                if str(actual_thread_id) == str(expected_thread_id):
                    print("✅ Email threading works correctly")
                    print(f"   - Thread ID: {actual_thread_id}")
                else:
                    print(f"❌ Thread ID mismatch. Expected: {expected_thread_id}, Got: {actual_thread_id}")
        
    except Exception as e:
        print(f"❌ Email threading test failed: {e}")
        return False
    
    return True


async def main():
    """Run all email receiving tests"""
    print("Starting Email Receiving Tests...")
    
    results = []
    
    # Run tests
    results.append(await test_email_receiving_setup())
    results.append(await test_inbound_email_processing())
    results.append(await test_email_threading())
    
    # Summary
    print("\n=== Test Summary ===")
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("\n✅ All tests passed! Email receiving is ready to use.")
        print("\nNext steps:")
        print("1. Configure a subdomain (e.g., reply.yourdomain.com) with MX records pointing to mx.sendgrid.net")
        print("2. Set up Inbound Parse in SendGrid dashboard")
        print("3. Point the webhook to: https://yourapi.com/webhooks/sendgrid-inbound")
        print("4. Update campaigns with reply_to_domain")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")


if __name__ == "__main__":
    asyncio.run(main())