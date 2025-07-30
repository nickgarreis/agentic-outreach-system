# src/config.py
# Application configuration and environment settings
# Loads environment variables and defines app-wide settings
# RELEVANT FILES: database.py, main.py, deps.py

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic-settings for validation and type conversion.
    """

    # Supabase configuration
    supabase_url: str
    supabase_publishable_key: str  # Public key for web-facing routes (replaces anon key)
    supabase_secret_key: Optional[str] = None  # Private key for backend operations (replaces service role key)
    supabase_db_url: Optional[str] = None  # Only if raw SQL needed (port 6543)

    # Application settings
    app_name: str = "Agentic Outreach System"
    debug: bool = False

    # Retry configuration for API calls
    max_retries: int = 3
    retry_delay: float = 1.0  # Initial delay in seconds
    max_retry_delay: float = 60.0  # Maximum delay between retries

    # Timeouts (in seconds)
    postgrest_timeout: int = 10
    storage_timeout: int = 10
    default_timeout: int = 30

    # Connection pool settings (for raw SQL if used)
    db_pool_min_size: int = 2
    db_pool_max_size: int = 20
    db_pool_timeout: int = 10
    db_pool_max_inactive_lifetime: int = 300  # 5 minutes

    # OpenRouter API settings (for AI agents)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # AgentOps configuration (for agent monitoring and observability)
    agentops_api_key: Optional[str] = None

    # Render deployment settings
    render_service_name: Optional[str] = None
    render_service_id: Optional[str] = None
    is_render: bool = False  # Auto-detected from RENDER env var

    class Config:
        """Pydantic config for environment loading"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Automatically detect if running on Render
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            # Check if RENDER environment variable exists
            import os

            if os.getenv("RENDER"):
                os.environ["IS_RENDER"] = "true"
            return (init_settings, env_settings, file_secret_settings)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Convenience function for getting settings in non-FastAPI contexts
settings = get_settings()
