# src/agent/agentops_config.py
# AgentOps configuration and initialization utilities
# Provides functions to initialize and configure AgentOps for agent monitoring
# RELEVANT FILES: ../config.py, autopilot_agent.py, tools/database_tools.py

import agentops
import logging
from typing import Optional
from ..config import get_settings

logger = logging.getLogger(__name__)


def init_agentops(api_key: Optional[str] = None) -> bool:
    """
    Initialize AgentOps with API key from settings or parameter.

    Args:
        api_key: Optional API key, if not provided uses settings

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        # Get API key from parameter or settings
        if not api_key:
            settings = get_settings()
            api_key = settings.agentops_api_key

        # Skip initialization if no API key
        if not api_key:
            logger.warning("AgentOps API key not found, skipping initialization")
            return False

        # Initialize AgentOps with configuration to suppress OpenAI instrumentor warnings
        agentops.init(
            api_key=api_key,
            skip_auto_start_session=True,  # We manage sessions manually
            instrument_llm_calls=False,  # Disable automatic LLM instrumentation to avoid warnings
        )
        logger.info("✓ AgentOps initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize AgentOps: {e}")
        return False


def get_agentops_config() -> dict:
    """
    Get AgentOps configuration for advanced settings.

    Returns:
        dict: Configuration dictionary for AgentOps
    """
    settings = get_settings()

    config = {
        "auto_start_session": False,  # We'll manage sessions manually
        "max_wait_time": 30,  # Max time to wait for session to end
        "max_queue_size": 1000,  # Max events to queue before dropping
        "tags": {
            "environment": "dev" if settings.debug else "production",
            "service": "autopilot-agent",
            "app_name": settings.app_name,
        },
    }

    # Add render-specific tags if running on Render
    if settings.is_render:
        config["tags"]["render_service"] = settings.render_service_name
        config["tags"]["render_id"] = settings.render_service_id

    return config


def create_session_tags(job_type: str, job_id: str, **kwargs) -> dict:
    """
    Create standardized tags for an AgentOps session.

    Args:
        job_type: Type of job being executed (e.g., "campaign_execution", "lead_enrichment")
        job_id: Unique identifier for the job
        **kwargs: Additional tags to include

    Returns:
        dict: Tags dictionary for the session
    """
    settings = get_settings()

    tags = {
        "job_type": job_type,
        "job_id": job_id,
        "environment": "dev" if settings.debug else "production",
        **kwargs,
    }

    return tags


class AgentOpsContextManager:
    """
    Context manager for AgentOps sessions with automatic cleanup.
    Ensures sessions are properly ended even if exceptions occur.
    """

    def __init__(self, session_name: str, tags: Optional[dict] = None):
        """
        Initialize context manager.

        Args:
            session_name: Name for the session
            tags: Optional tags to attach to the session
        """
        self.session_name = session_name
        self.tags = tags or {}
        self.session = None

    async def __aenter__(self):
        """Start AgentOps session"""
        try:
            # Start session with tags
            self.session = agentops.start_session(
                session_name=self.session_name, tags=self.tags
            )
            logger.info(f"Started AgentOps session: {self.session_name}")
            return self.session
        except Exception as e:
            logger.error(f"Failed to start AgentOps session: {e}")
            return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End AgentOps session with appropriate status"""
        if self.session:
            try:
                # Determine session status based on exception
                if exc_type:
                    status = "Error"
                    logger.error(
                        f"Session {self.session_name} ended with error: {exc_val}"
                    )
                else:
                    status = "Success"
                    logger.info(f"Session {self.session_name} completed successfully")

                # End the session
                agentops.end_session(status)

            except Exception as e:
                logger.error(f"Failed to end AgentOps session: {e}")


# Decorator for tracking agent operations
def track_operation(operation_name: str):
    """
    Decorator to track individual operations within an agent.

    Args:
        operation_name: Name of the operation being tracked
    """

    def decorator(func):
        # Use AgentOps operation decorator
        return agentops.operation(name=operation_name)(func)

    return decorator


# Decorator for tracking tool usage
def track_tool(tool_name: str):
    """
    Decorator to track tool usage within agents.

    Args:
        tool_name: Name of the tool being used
    """

    def decorator(func):
        # Use AgentOps operation decorator with tool prefix
        return agentops.operation(name=f"tool_{tool_name}")(func)

    return decorator
