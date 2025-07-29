# src/agent/tools/base_tools.py
# Base class for all tool categories providing common functionality
# Shared initialization and helper methods for all tool types
# RELEVANT FILES: database_tools.py, web_tools.py, ../autopilot_agent.py

import logging
from typing import Optional
from ...database import get_supabase

logger = logging.getLogger(__name__)


class BaseTools:
    """
    Base class for all tool categories.
    Provides common functionality like logging and database client management.
    """

    def __init__(self):
        """Initialize base tools with logging"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.supabase = None
        self.logger.info(f"Initialized {self.__class__.__name__}")

    async def _get_client(self):
        """
        Get or initialize Supabase client.
        Shared by database tools that need direct database access.
        """
        if not self.supabase:
            self.supabase = await get_supabase()
        return self.supabase

    def _log_error(
        self, operation: str, error: Exception, details: Optional[str] = None
    ):
        """
        Standardized error logging across all tools.

        Args:
            operation: Name of the operation that failed
            error: The exception that occurred
            details: Optional additional context
        """
        error_msg = f"{operation} failed: {error}"
        if details:
            error_msg += f" | Details: {details}"
        self.logger.error(error_msg)

    def _log_success(self, operation: str, details: Optional[str] = None):
        """
        Standardized success logging across all tools.

        Args:
            operation: Name of the operation that succeeded
            details: Optional additional context
        """
        success_msg = f"{operation} completed successfully"
        if details:
            success_msg += f" | {details}"
        self.logger.info(success_msg)
