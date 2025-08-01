# src/testing/test_email_sending_flow.py
# Comprehensive test suite for email sending functionality with stress testing
# Tests all aspects: sending, tracking, webhooks, error handling, and performance
# RELEVANT FILES: ../agent/tools/email_sender.py, ../agent/tools/message_scheduler.py, ../routers/webhooks.py

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
import random
import string

from ..config import get_settings
from ..database import get_supabase
from ..agent.tools import EmailSender, MessageScheduler, DatabaseTools
from ..agent.autopilot_agent import AutopilotAgent
from ..routers.webhooks import process_sendgrid_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDataGenerator:
    """Helper class to generate test data"""
    
    @staticmethod
    def generate_email():
        """Generate a random test email"""
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domains = ['test.com', 'example.com', 'demo.org', 'testmail.net']
        return f"{username}@{random.choice(domains)}"
    
    @staticmethod
    def generate_lead(campaign_id: str, client_id: str) -> Dict[str, Any]:
        """Generate a test lead with random data"""
        first_names = ['John', 'Jane', 'Mike', 'Sarah', 'David', 'Emma', 'Chris', 'Lisa']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller']
        companies = ['Tech Corp', 'Global Industries', 'Innovative Solutions', 'Digital Ventures']
        titles = ['CEO', 'CTO', 'VP Sales', 'Marketing Director', 'Product Manager']
        
        return {
            "id": str(uuid4()),
            "campaign_id": campaign_id,
            "client_id": client_id,
            "first_name": random.choice(first_names),
            "last_name": random.choice(last_names),
            "email": TestDataGenerator.generate_email(),
            "company": random.choice(companies),
            "title": random.choice(titles),
            "status": "researched",
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generate_message_content() -> str:
        """Generate test message content with various lengths"""
        templates = [
            "Hi {{first_name}},\n\nI noticed you work at {{company}} as {{title}}. Would love to connect!",
            "Dear {{first_name}} {{last_name}},\n\nI'm reaching out regarding {{company}}'s recent growth...",
            "Hello {{first_name}},\n\n" + "This is a longer message. " * 50 + "\n\nBest regards",
            "👋 Hey {{first_name}}, Quick question about {{company}}... 🚀"  # Unicode test
        ]
        return random.choice(templates)


class EmailSendingTests:
    """Main test class for email sending functionality"""
    
    def __init__(self):
        self.supabase = None
        self.test_data = {
            "clients": [],
            "campaigns": [],
            "leads": [],
            "messages": [],
            "jobs": []
        }
        self.performance_metrics = {
            "batch_send_times": [],
            "webhook_processing_times": [],
            "error_rates": {},
            "connection_pool_stats": []
        }
    
    async def setup(self):
        """Initialize test environment"""
        self.supabase = await get_supabase()
        logger.info("Test environment initialized")
    
    async def cleanup(self):
        """Clean up all test data"""
        logger.info("Cleaning up test data...")
        
        # Delete in reverse order of dependencies
        for message_id in self.test_data["messages"]:
            try:
                await self.supabase.table("messages").delete().eq("id", message_id).execute()
            except:
                pass
        
        for job_id in self.test_data["jobs"]:
            try:
                await self.supabase.table("jobs").delete().eq("id", job_id).execute()
            except:
                pass
        
        for lead_id in self.test_data["leads"]:
            try:
                await self.supabase.table("leads").delete().eq("id", lead_id).execute()
            except:
                pass
        
        for campaign_id in self.test_data["campaigns"]:
            try:
                await self.supabase.table("campaigns").delete().eq("id", campaign_id).execute()
            except:
                pass
        
        for client_id in self.test_data["clients"]:
            try:
                await self.supabase.table("clients").delete().eq("id", client_id).execute()
            except:
                pass
        
        logger.info("Cleanup completed")
    
    async def create_test_campaign(self, sendgrid_api_key: str = "SG.test_key_123") -> Dict[str, Any]:
        """Create a test campaign with all email settings"""
        client_id = str(uuid4())
        campaign_id = str(uuid4())
        
        # Create client
        client_data = {
            "id": client_id,
            "name": f"Test Client {client_id[:8]}",
            "created_at": datetime.utcnow().isoformat()
        }
        await self.supabase.table("clients").insert(client_data).execute()
        self.test_data["clients"].append(client_id)
        
        # Create campaign with full email configuration
        campaign_data = {
            "id": campaign_id,
            "client_id": client_id,
            "name": f"Test Campaign {campaign_id[:8]}",
            "status": "active",
            "email_outreach": True,
            "sendgrid_api_key": sendgrid_api_key,
            "from_email": "test@example.com",
            "from_name": "Test Sender",
            "email_footer": {
                "enabled": True,
                "template": "Best regards,\nThe {{company}} Team\n\nUnsubscribe: {{unsubscribe_link}}"
            },
            "daily_sending_limit_email": 100,
            "email_metrics": {
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "bounced": 0,
                "unsubscribed": 0,
                "open_rate": 0,
                "click_rate": 0
            },
            "created_at": datetime.utcnow().isoformat()
        }
        await self.supabase.table("campaigns").insert(campaign_data).execute()
        self.test_data["campaigns"].append(campaign_id)
        
        return {
            "client_id": client_id,
            "campaign_id": campaign_id,
            "campaign_data": campaign_data
        }
    
    async def create_test_leads(self, campaign_id: str, client_id: str, count: int) -> List[Dict[str, Any]]:
        """Create multiple test leads"""
        leads = []
        for _ in range(count):
            lead_data = TestDataGenerator.generate_lead(campaign_id, client_id)
            await self.supabase.table("leads").insert(lead_data).execute()
            self.test_data["leads"].append(lead_data["id"])
            leads.append(lead_data)
        
        return leads
    
    # Test 1: Basic Email Sending
    async def test_basic_email_sending(self):
        """Test basic single and batch email sending"""
        logger.info("\n=== Test 1: Basic Email Sending ===")
        
        campaign_info = await self.create_test_campaign()
        leads = await self.create_test_leads(
            campaign_info["campaign_id"], 
            campaign_info["client_id"], 
            5
        )
        
        # Create test messages
        scheduler = MessageScheduler()
        sequences = {
            "email": [{
                "sequence_number": 1,
                "day_delay": 0,
                "subject": "Test Subject for {{first_name}}",
                "content": TestDataGenerator.generate_message_content()
            }]
        }
        
        # Schedule messages for each lead
        for lead in leads:
            result = await scheduler.schedule_outreach_messages(
                sequences=sequences,
                campaign_id=campaign_info["campaign_id"],
                lead_id=lead["id"],
                daily_limits={"email": 100}
            )
            
            assert result.success, f"Failed to schedule messages: {result.error}"
            
            # Create messages in database
            db_tools = DatabaseTools()
            messages = result.data.get("scheduled_messages", [])
            create_result = await db_tools.bulk_schedule_messages(messages)
            assert create_result["success"], f"Failed to create messages: {create_result.get('error')}"
            
            for msg in create_result["messages"]:
                self.test_data["messages"].append(msg["id"])
        
        logger.info(f"✅ Created {len(self.test_data['messages'])} test messages")
    
    # Test 2: Batch Size Testing
    async def test_batch_sizes(self):
        """Test different batch sizes including edge cases"""
        logger.info("\n=== Test 2: Batch Size Testing ===")
        
        test_sizes = [1, 50, 100, 150, 237]  # Various sizes including > BATCH_SIZE
        
        for batch_size in test_sizes:
            logger.info(f"\nTesting batch size: {batch_size}")
            
            campaign_info = await self.create_test_campaign()
            leads = await self.create_test_leads(
                campaign_info["campaign_id"],
                campaign_info["client_id"],
                batch_size
            )
            
            # Create messages
            messages = []
            for i, lead in enumerate(leads):
                msg = {
                    "id": str(uuid4()),
                    "campaign_id": campaign_info["campaign_id"],
                    "lead_id": lead["id"],
                    "channel": "email",
                    "subject": f"Batch test {i+1} for {{{{first_name}}}}",
                    "content": f"Message {i+1}: " + TestDataGenerator.generate_message_content(),
                    "status": "scheduled",
                    "send_at": datetime.utcnow().isoformat(),
                    "created_at": datetime.utcnow().isoformat()
                }
                messages.append(msg)
            
            # Mock SendGrid for testing
            with patch('sendgrid.SendGridAPIClient') as mock_sg:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.status_code = 202
                mock_response.headers = {'X-Message-Id': 'test-message-id'}
                mock_client.send.return_value = mock_response
                mock_sg.return_value = mock_client
                
                # Test batch sending
                email_sender = EmailSender()
                start_time = time.time()
                
                result = await email_sender.send_batch_emails(
                    messages=messages,
                    api_key="SG.test_key",
                    campaign_footer=campaign_info["campaign_data"]["email_footer"],
                    from_email="test@example.com",
                    from_name="Test Sender"
                )
                
                send_time = time.time() - start_time
                self.performance_metrics["batch_send_times"].append({
                    "batch_size": batch_size,
                    "time": send_time,
                    "emails_per_second": batch_size / send_time if send_time > 0 else 0
                })
                
                assert result.success, f"Batch send failed: {result.error}"
                logger.info(f"✅ Batch {batch_size}: {send_time:.2f}s ({batch_size/send_time:.1f} emails/sec)")
    
    # Test 3: Error Handling
    async def test_error_handling(self):
        """Test all error categories and retry logic"""
        logger.info("\n=== Test 3: Error Handling ===")
        
        error_scenarios = [
            {
                "name": "Rate Limit Error",
                "error": "429 Too Many Requests",
                "expected_category": "rate_limit",
                "is_retryable": True
            },
            {
                "name": "Authentication Error", 
                "error": "401 Unauthorized - Invalid API key",
                "expected_category": "authentication",
                "is_retryable": False
            },
            {
                "name": "Invalid Email Error",
                "error": "550 Invalid email address",
                "expected_category": "invalid_email", 
                "is_retryable": False
            },
            {
                "name": "Network Error",
                "error": "Connection timeout",
                "expected_category": "network_error",
                "is_retryable": True
            },
            {
                "name": "Content Error",
                "error": "Message rejected due to spam content",
                "expected_category": "content_error",
                "is_retryable": False
            }
        ]
        
        campaign_info = await self.create_test_campaign()
        lead = (await self.create_test_leads(campaign_info["campaign_id"], campaign_info["client_id"], 1))[0]
        
        for scenario in error_scenarios:
            logger.info(f"\nTesting: {scenario['name']}")
            
            # Create test message
            message = {
                "id": str(uuid4()),
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "channel": "email",
                "subject": f"Error test: {scenario['name']}",
                "content": "Test content",
                "status": "scheduled"
            }
            
            # Mock SendGrid to raise specific error
            with patch('sendgrid.SendGridAPIClient') as mock_sg:
                mock_client = Mock()
                mock_client.send.side_effect = Exception(scenario["error"])
                mock_sg.return_value = mock_client
                
                email_sender = EmailSender()
                result = await email_sender.send_email(
                    message_data=message,
                    api_key="SG.test_key"
                )
                
                assert not result.success
                assert result.data["error_category"] == scenario["expected_category"]
                assert result.data["is_retryable"] == scenario["is_retryable"]
                
                logger.info(f"✅ {scenario['name']}: Category={result.data['error_category']}, Retryable={result.data['is_retryable']}")
    
    # Test 4: Connection Pool Testing
    async def test_connection_pool(self):
        """Test connection pool management and performance"""
        logger.info("\n=== Test 4: Connection Pool Testing ===")
        
        email_sender = EmailSender()
        
        # Test multiple API keys
        api_keys = [f"SG.test_key_{i}" for i in range(5)]
        
        # Create mock clients for different API keys
        with patch('sendgrid.SendGridAPIClient') as mock_sg:
            mock_sg.return_value = Mock()
            
            # Test pool creation and round-robin
            for i in range(50):  # 50 requests across 5 API keys
                api_key = api_keys[i % len(api_keys)]
                client = email_sender._get_sendgrid_client(api_key)
                assert client is not None
            
            # Check pool statistics
            pool_stats = email_sender.get_pool_stats()
            self.performance_metrics["connection_pool_stats"].append(pool_stats)
            
            logger.info("Pool Statistics:")
            for key, stats in pool_stats.items():
                logger.info(f"  {key}: {stats}")
            
            # Test pool timeout and cleanup
            logger.info("\nTesting pool cleanup...")
            
            # Manually expire clients by backdating timestamps
            for api_key in email_sender._client_timestamps:
                email_sender._client_timestamps[api_key] = [
                    datetime.utcnow().timestamp() - 400  # Expired (> 300s)
                    for _ in email_sender._client_timestamps[api_key]
                ]
            
            # Request new client to trigger cleanup
            client = email_sender._get_sendgrid_client(api_keys[0])
            
            # Verify cleanup occurred
            pool_stats_after = email_sender.get_pool_stats()
            logger.info(f"✅ Pool cleanup completed. Stats after cleanup: {pool_stats_after}")
    
    # Test 5: Webhook and Tracking
    async def test_webhook_tracking(self):
        """Test SendGrid webhook processing and tracking updates"""
        logger.info("\n=== Test 5: Webhook and Tracking ===")
        
        campaign_info = await self.create_test_campaign()
        lead = (await self.create_test_leads(campaign_info["campaign_id"], campaign_info["client_id"], 1))[0]
        
        # Create a test message
        message_id = str(uuid4())
        message_data = {
            "id": message_id,
            "campaign_id": campaign_info["campaign_id"],
            "lead_id": lead["id"],
            "channel": "email",
            "subject": "Webhook test",
            "content": "Test content",
            "status": "sent",
            "sendgrid_message_id": "test-sg-id",
            "tracking_events": [],
            "created_at": datetime.utcnow().isoformat()
        }
        await self.supabase.table("messages").insert(message_data).execute()
        self.test_data["messages"].append(message_id)
        
        # Test different webhook events
        webhook_events = [
            {
                "event": "processed",
                "timestamp": int(datetime.utcnow().timestamp()),
                "message_id": message_id,
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "sg_event_id": "evt_1",
                "sg_message_id": "test-sg-id"
            },
            {
                "event": "delivered",
                "timestamp": int(datetime.utcnow().timestamp()) + 10,
                "message_id": message_id,
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "sg_event_id": "evt_2",
                "response": "250 OK"
            },
            {
                "event": "open",
                "timestamp": int(datetime.utcnow().timestamp()) + 3600,
                "message_id": message_id,
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "sg_event_id": "evt_3",
                "ip": "192.168.1.1",
                "useragent": "Mozilla/5.0"
            },
            {
                "event": "click",
                "timestamp": int(datetime.utcnow().timestamp()) + 3700,
                "message_id": message_id,
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "sg_event_id": "evt_4",
                "url": "https://example.com/link"
            }
        ]
        
        # Process each webhook event
        for event in webhook_events:
            start_time = time.time()
            await process_sendgrid_event(self.supabase, event)
            process_time = time.time() - start_time
            
            self.performance_metrics["webhook_processing_times"].append({
                "event": event["event"],
                "time": process_time
            })
            
            logger.info(f"✅ Processed {event['event']} event in {process_time:.3f}s")
        
        # Verify tracking data
        message_response = await self.supabase.table("messages").select("*").eq("id", message_id).single().execute()
        message = message_response.data
        
        assert message["delivered_at"] is not None
        assert message["opened_at"] is not None
        assert message["clicked_at"] is not None
        assert len(message["tracking_events"]) == 4
        
        # Verify campaign metrics
        campaign_response = await self.supabase.table("campaigns").select("email_metrics").eq(
            "id", campaign_info["campaign_id"]
        ).single().execute()
        metrics = campaign_response.data["email_metrics"]
        
        assert metrics["delivered"] == 1
        assert metrics["opened"] == 1
        assert metrics["clicked"] == 1
        
        logger.info(f"✅ Campaign metrics updated: {metrics}")
    
    # Test 6: Performance and Scale
    async def test_performance_scale(self):
        """Test performance with large volumes"""
        logger.info("\n=== Test 6: Performance and Scale Testing ===")
        
        campaign_info = await self.create_test_campaign()
        
        # Create many leads
        lead_count = 1000
        logger.info(f"Creating {lead_count} test leads...")
        
        # Create leads in batches to avoid timeouts
        all_leads = []
        batch_size = 100
        for i in range(0, lead_count, batch_size):
            batch_count = min(batch_size, lead_count - i)
            leads = await self.create_test_leads(
                campaign_info["campaign_id"],
                campaign_info["client_id"],
                batch_count
            )
            all_leads.extend(leads)
            logger.info(f"  Created {i + batch_count}/{lead_count} leads")
        
        # Create messages for all leads
        logger.info("Creating messages...")
        all_messages = []
        scheduler = MessageScheduler()
        db_tools = DatabaseTools()
        
        for i, lead in enumerate(all_leads):
            sequences = {
                "email": [{
                    "sequence_number": 1,
                    "day_delay": 0,
                    "subject": f"Scale test {i+1}",
                    "content": f"Message {i+1} content"
                }]
            }
            
            result = await scheduler.schedule_outreach_messages(
                sequences=sequences,
                campaign_id=campaign_info["campaign_id"],
                lead_id=lead["id"],
                daily_limits={"email": 10000}
            )
            
            if result.success:
                messages = result.data.get("scheduled_messages", [])
                create_result = await db_tools.bulk_schedule_messages(messages)
                if create_result["success"]:
                    all_messages.extend(create_result["messages"])
                    for msg in create_result["messages"]:
                        self.test_data["messages"].append(msg["id"])
            
            if (i + 1) % 100 == 0:
                logger.info(f"  Created messages for {i + 1}/{lead_count} leads")
        
        logger.info(f"✅ Created {len(all_messages)} messages total")
        
        # Test job creation performance
        logger.info("\nTesting job creation performance...")
        start_time = time.time()
        
        job_result = await scheduler._create_email_jobs(all_messages, campaign_info["campaign_id"])
        
        job_creation_time = time.time() - start_time
        jobs_created = job_result.get("jobs_created", 0)
        
        logger.info(f"✅ Created {jobs_created} jobs in {job_creation_time:.2f}s")
        logger.info(f"  Performance: {len(all_messages)/job_creation_time:.1f} messages/second")
        
        # Track job IDs for cleanup
        jobs_response = await self.supabase.table("jobs").select("id").eq(
            "job_type", "send_email"
        ).eq("data->>campaign_id", campaign_info["campaign_id"]).execute()
        
        for job in jobs_response.data:
            self.test_data["jobs"].append(job["id"])
    
    # Test 7: Edge Cases
    async def test_edge_cases(self):
        """Test various edge cases and unusual scenarios"""
        logger.info("\n=== Test 7: Edge Cases ===")
        
        campaign_info = await self.create_test_campaign()
        
        edge_cases = [
            {
                "name": "Empty message list",
                "messages": []
            },
            {
                "name": "Missing lead email",
                "lead_data": {"email": None}
            },
            {
                "name": "Invalid email format",
                "lead_data": {"email": "not-an-email"}
            },
            {
                "name": "Unicode in content",
                "content": "Hello 👋 {{first_name}}! 🚀 Special chars: ñáéíóú"
            },
            {
                "name": "Very long content",
                "content": "A" * 10000  # 10KB of content
            },
            {
                "name": "Special characters in name",
                "lead_data": {"first_name": "O'Brien", "last_name": "Smith-Jones"}
            },
            {
                "name": "Missing personalization variables",
                "content": "Hello {{undefined_var}}!"
            }
        ]
        
        email_sender = EmailSender()
        
        for case in edge_cases:
            logger.info(f"\nTesting: {case['name']}")
            
            try:
                if "messages" in case:
                    # Test empty message list
                    result = await email_sender.send_batch_emails(
                        messages=case["messages"],
                        api_key="SG.test_key"
                    )
                    assert result.success
                    assert result.data["sent"] == 0
                    logger.info(f"✅ {case['name']}: Handled correctly")
                
                elif "lead_data" in case:
                    # Test lead data issues
                    lead = TestDataGenerator.generate_lead(
                        campaign_info["campaign_id"],
                        campaign_info["client_id"]
                    )
                    lead.update(case["lead_data"])
                    
                    # Mock the lead fetch
                    with patch.object(email_sender, '_get_lead_data', return_value=lead):
                        message = {
                            "id": str(uuid4()),
                            "lead_id": lead["id"],
                            "subject": "Test",
                            "content": "Test content"
                        }
                        
                        with patch('sendgrid.SendGridAPIClient'):
                            result = await email_sender.send_email(
                                message_data=message,
                                api_key="SG.test_key"
                            )
                            
                            if lead.get("email") and "@" in str(lead.get("email", "")):
                                assert result.success
                            else:
                                assert not result.success
                    
                    logger.info(f"✅ {case['name']}: Handled correctly")
                
                elif "content" in case:
                    # Test content issues
                    lead = TestDataGenerator.generate_lead(
                        campaign_info["campaign_id"],
                        campaign_info["client_id"]
                    )
                    
                    message = {
                        "id": str(uuid4()),
                        "lead_id": lead["id"],
                        "subject": "Test",
                        "content": case["content"]
                    }
                    
                    with patch('sendgrid.SendGridAPIClient') as mock_sg:
                        mock_client = Mock()
                        mock_response = Mock()
                        mock_response.status_code = 202
                        mock_client.send.return_value = mock_response
                        mock_sg.return_value = mock_client
                        
                        with patch.object(email_sender, '_get_lead_data', return_value=lead):
                            result = await email_sender.send_email(
                                message_data=message,
                                api_key="SG.test_key"
                            )
                            
                            assert result.success
                            logger.info(f"✅ {case['name']}: Handled correctly")
            
            except Exception as e:
                logger.error(f"❌ {case['name']}: Failed with {str(e)}")
    
    # Test 8: Concurrent Operations
    async def test_concurrent_operations(self):
        """Test concurrent email sending and webhook processing"""
        logger.info("\n=== Test 8: Concurrent Operations ===")
        
        campaign_info = await self.create_test_campaign()
        leads = await self.create_test_leads(
            campaign_info["campaign_id"],
            campaign_info["client_id"],
            20
        )
        
        # Create messages for concurrent sending
        messages = []
        for lead in leads:
            msg = {
                "id": str(uuid4()),
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "channel": "email",
                "subject": "Concurrent test",
                "content": "Test content",
                "status": "scheduled"
            }
            messages.append(msg)
        
        # Mock SendGrid
        with patch('sendgrid.SendGridAPIClient') as mock_sg:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.headers = {'X-Message-Id': 'test-id'}
            
            # Add random delay to simulate network latency
            async def delayed_send(*args):
                await asyncio.sleep(random.uniform(0.1, 0.5))
                return mock_response
            
            mock_client.send = Mock(side_effect=lambda x: mock_response)
            mock_sg.return_value = mock_client
            
            # Test concurrent batch sends
            email_sender = EmailSender()
            
            async def send_batch(batch_messages):
                return await email_sender.send_batch_emails(
                    messages=batch_messages,
                    api_key="SG.test_key",
                    from_email="test@example.com"
                )
            
            # Split messages into batches and send concurrently
            batch_size = 5
            batches = [messages[i:i+batch_size] for i in range(0, len(messages), batch_size)]
            
            start_time = time.time()
            
            # Send all batches concurrently
            tasks = [send_batch(batch) for batch in batches]
            results = await asyncio.gather(*tasks)
            
            concurrent_time = time.time() - start_time
            
            # Verify all succeeded
            total_sent = sum(r.data["sent"] for r in results if r.success)
            assert total_sent == len(messages)
            
            logger.info(f"✅ Sent {total_sent} emails concurrently in {concurrent_time:.2f}s")
            logger.info(f"  Performance: {total_sent/concurrent_time:.1f} emails/second")
    
    # Test 9: Agent Integration
    async def test_agent_integration(self):
        """Test the full agent flow with email sending"""
        logger.info("\n=== Test 9: Agent Integration ===")
        
        campaign_info = await self.create_test_campaign("SG.actual_test_key")  # Would use real key in actual test
        leads = await self.create_test_leads(
            campaign_info["campaign_id"],
            campaign_info["client_id"],
            3
        )
        
        # Test the agent's send_email job handler
        agent = AutopilotAgent("send_email", str(uuid4()))
        
        # Create test messages
        message_ids = []
        for lead in leads:
            msg = {
                "id": str(uuid4()),
                "campaign_id": campaign_info["campaign_id"],
                "lead_id": lead["id"],
                "channel": "email",
                "subject": "Agent test",
                "content": "Test content from agent",
                "status": "scheduled",
                "created_at": datetime.utcnow().isoformat()
            }
            await self.supabase.table("messages").insert(msg).execute()
            message_ids.append(msg["id"])
            self.test_data["messages"].append(msg["id"])
        
        # Create job data
        job_data = {
            "campaign_id": campaign_info["campaign_id"],
            "message_ids": message_ids
        }
        
        # Mock SendGrid for agent
        with patch('sendgrid.SendGridAPIClient') as mock_sg:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 202
            mock_response.headers = {'X-Message-Id': 'test-agent-id'}
            mock_client.send.return_value = mock_response
            mock_sg.return_value = mock_client
            
            # Execute job
            result = await agent._handle_send_email(job_data)
            
            assert result["status"] == "completed"
            assert result["messages_processed"] == len(message_ids)
            
            # Check for pool stats
            assert "pool_stats" in result
            
            logger.info(f"✅ Agent processed {result['messages_processed']} messages")
            logger.info(f"  Pool stats: {result['pool_stats']}")
    
    async def generate_report(self):
        """Generate a comprehensive test report"""
        logger.info("\n" + "="*60)
        logger.info("TEST REPORT SUMMARY")
        logger.info("="*60)
        
        # Batch send performance
        if self.performance_metrics["batch_send_times"]:
            logger.info("\nBatch Send Performance:")
            for metric in self.performance_metrics["batch_send_times"]:
                logger.info(f"  Batch size {metric['batch_size']}: {metric['time']:.2f}s ({metric['emails_per_second']:.1f} emails/sec)")
        
        # Webhook processing times
        if self.performance_metrics["webhook_processing_times"]:
            logger.info("\nWebhook Processing Times:")
            by_event = {}
            for metric in self.performance_metrics["webhook_processing_times"]:
                event = metric["event"]
                if event not in by_event:
                    by_event[event] = []
                by_event[event].append(metric["time"])
            
            for event, times in by_event.items():
                avg_time = sum(times) / len(times)
                logger.info(f"  {event}: avg {avg_time:.3f}s")
        
        # Connection pool stats
        if self.performance_metrics["connection_pool_stats"]:
            logger.info("\nConnection Pool Statistics:")
            for stats in self.performance_metrics["connection_pool_stats"]:
                logger.info(f"  {stats}")
        
        # Test data created
        logger.info("\nTest Data Created:")
        logger.info(f"  Clients: {len(self.test_data['clients'])}")
        logger.info(f"  Campaigns: {len(self.test_data['campaigns'])}")
        logger.info(f"  Leads: {len(self.test_data['leads'])}")
        logger.info(f"  Messages: {len(self.test_data['messages'])}")
        logger.info(f"  Jobs: {len(self.test_data['jobs'])}")
        
        logger.info("\n" + "="*60)


async def run_all_tests():
    """Run all email sending tests"""
    tests = EmailSendingTests()
    
    try:
        await tests.setup()
        
        # Run all tests
        test_methods = [
            tests.test_basic_email_sending,
            tests.test_batch_sizes,
            tests.test_error_handling,
            tests.test_connection_pool,
            tests.test_webhook_tracking,
            tests.test_performance_scale,
            tests.test_edge_cases,
            tests.test_concurrent_operations,
            tests.test_agent_integration
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                logger.error(f"Test {test_method.__name__} failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Generate report
        await tests.generate_report()
        
    finally:
        # Always cleanup
        await tests.cleanup()


async def main():
    """Main entry point"""
    logger.info("Starting comprehensive email sending tests...")
    logger.info("This will test all aspects of the email system including:")
    logger.info("- Basic sending and batching")
    logger.info("- Error handling and recovery")
    logger.info("- Connection pooling")
    logger.info("- Webhook tracking")
    logger.info("- Performance at scale")
    logger.info("- Edge cases")
    logger.info("- Concurrent operations")
    logger.info("- Agent integration")
    
    await run_all_tests()
    
    logger.info("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())