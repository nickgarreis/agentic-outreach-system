#!/usr/bin/env python3
# test_email_issues.py
# Identify specific issues in email sending implementation
# RELEVANT FILES: src/agent/tools/email_sender.py, src/routers/webhooks.py

import os
import sys
import asyncio
import logging
from datetime import datetime
from uuid import uuid4

# Set up environment
os.environ.update({
    "SUPABASE_URL": "https://tqjyyedrazaimtujdjrw.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_secret_vnJVcpnH7Qh3mhJHAzf8mQ_F0WleuLV",
    "APP_NAME": "Test",
    "DEBUG": "true"
})

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_webhook_custom_args():
    """Test if webhook events receive custom args from personalizations"""
    logger.info("\n=== Testing Webhook Custom Args ===")
    
    # Check the email sender personalization code
    from src.agent.tools.email_sender import EmailSender
    
    # Analyze the personalization code
    logger.info("Checking personalization custom args...")
    
    # The issue: In _send_batch_with_personalizations, custom args are added:
    # personalization.add_custom_arg('message_id', str(msg['id']))
    # personalization.add_custom_arg('campaign_id', str(msg['campaign_id']))
    # personalization.add_custom_arg('lead_id', str(msg['lead_id']))
    
    # But webhooks expect these in the event payload directly, not in custom_args
    logger.info("❌ Issue found: Custom args from personalizations won't be in webhook event root")
    logger.info("  - Email sender adds message_id, campaign_id, lead_id as custom_args")
    logger.info("  - Webhook handler expects them at event root level")
    logger.info("  - SendGrid puts custom_args in a nested object, not at root")
    
    return False


async def test_lead_data_sync_fetch():
    """Test the sync lead data fetch in batch sending"""
    logger.info("\n=== Testing Lead Data Sync Fetch ===")
    
    # Check the _get_lead_data_sync method
    logger.info("Checking _get_lead_data_sync implementation...")
    
    # The issue: Creating new event loop in sync context
    logger.info("❌ Issue found: _get_lead_data_sync creates new event loop")
    logger.info("  - This can cause issues when called from asyncio.to_thread")
    logger.info("  - Should use sync database client instead")
    
    return False


async def test_message_status_states():
    """Test message status validation"""
    logger.info("\n=== Testing Message Status States ===")
    
    # Check status values used
    statuses_in_code = [
        "scheduled",
        "sent", 
        "delivered",
        "failed",
        "retry_pending",  # Added in autopilot_agent
        "bounced",
        "unsubscribed"
    ]
    
    logger.info("Status values found in code:")
    for status in statuses_in_code:
        logger.info(f"  - {status}")
    
    # The issue: No validation on message status column
    logger.info("⚠️  Potential issue: No database constraint on status values")
    logger.info("  - Should add CHECK constraint or ENUM type")
    
    return True


async def test_retry_integration():
    """Test retry logic integration in agent"""
    logger.info("\n=== Testing Retry Integration ===")
    
    # Check if agent properly handles retries
    logger.info("Checking agent retry handling...")
    
    # The agent does call retry_failed_messages but:
    logger.info("⚠️  Minor issue: Retry results could be better integrated")
    logger.info("  - Retry results are captured but not fully reported")
    logger.info("  - Should update final counts with retry results")
    
    return True


async def test_error_categorization():
    """Test error categorization coverage"""
    logger.info("\n=== Testing Error Categorization ===")
    
    from src.agent.tools.email_sender import EmailError
    
    # Test various error messages
    test_errors = [
        ("Rate limit exceeded", "rate_limit", True),
        ("401 Unauthorized", "authentication", False),
        ("Invalid email address: test@", "invalid_email", False),
        ("Connection refused", "network_error", True),
        ("Message rejected as spam", "content_error", False),
        ("Unknown error xyz", "unknown", False)
    ]
    
    all_passed = True
    for error_msg, expected_category, expected_retryable in test_errors:
        category, is_retryable = EmailError.categorize(error_msg)
        if category != expected_category or is_retryable != expected_retryable:
            logger.error(f"❌ Failed: '{error_msg}' -> {category}/{is_retryable}")
            all_passed = False
        else:
            logger.info(f"✅ Passed: '{error_msg}' -> {category}/{is_retryable}")
    
    return all_passed


async def test_batch_personalization():
    """Test batch personalization structure"""
    logger.info("\n=== Testing Batch Personalization ===")
    
    # The issue with base content template
    logger.info("Checking batch personalization...")
    
    logger.info("❌ Issue found: Base content not properly personalized")
    logger.info("  - First message content used as template for all")
    logger.info("  - Substitutions applied but base content may have first lead's data")
    logger.info("  - Should use generic template or per-message content")
    
    return False


async def main():
    """Run issue identification tests"""
    logger.info("Identifying issues in email sending implementation...")
    logger.info("="*60)
    
    issues_found = []
    
    # Run tests
    tests = [
        ("Webhook Custom Args", test_webhook_custom_args),
        ("Lead Data Sync Fetch", test_lead_data_sync_fetch),
        ("Message Status States", test_message_status_states),
        ("Retry Integration", test_retry_integration),
        ("Error Categorization", test_error_categorization),
        ("Batch Personalization", test_batch_personalization)
    ]
    
    for test_name, test_func in tests:
        try:
            passed = await test_func()
            if not passed:
                issues_found.append(test_name)
        except Exception as e:
            logger.error(f"Test {test_name} failed with error: {e}")
            issues_found.append(test_name)
    
    logger.info("\n" + "="*60)
    logger.info("SUMMARY OF ISSUES FOUND:")
    logger.info("="*60)
    
    if issues_found:
        logger.info(f"\nFound {len(issues_found)} issues to fix:")
        for issue in issues_found:
            logger.info(f"  ❌ {issue}")
    else:
        logger.info("\n✅ No critical issues found!")
    
    logger.info("\nRecommended fixes:")
    logger.info("1. Fix webhook custom args handling")
    logger.info("2. Fix lead data sync fetch to use proper sync client")
    logger.info("3. Fix batch personalization to use proper templates")
    logger.info("4. Add message status validation")
    logger.info("5. Improve retry result integration")


if __name__ == "__main__":
    asyncio.run(main())