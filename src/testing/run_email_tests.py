#!/usr/bin/env python3
# run_email_tests.py
# Standalone test runner for email sending functionality
# Sets up environment and runs comprehensive tests
# RELEVANT FILES: src/testing/test_email_sending_flow.py

import os
import sys
import asyncio

# Set up environment variables for testing
os.environ.update({
    "SUPABASE_URL": "https://tqjyyedrazaimtujdjrw.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_secret_vnJVcpnH7Qh3mhJHAzf8mQ_F0WleuLV",
    "APP_NAME": "Agentic Outreach System - Test",
    "DEBUG": "true",
    "OPENROUTER_API_KEY": "sk-or-v1-test",
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "AGENTOPS_API_KEY": "test-key",
    "APOLLO_API_KEY": "test-key",
    "TAVILY_API_KEY": "test-key"
})

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import and run tests
from src.testing.test_email_sending_flow import run_all_tests

if __name__ == "__main__":
    print("Starting email sending test suite...")
    print("=" * 60)
    asyncio.run(run_all_tests())