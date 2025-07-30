# src/database.py
# Supabase async client singleton for FastAPI
# Manages connection lifecycle and provides dependency injection
# RELEVANT FILES: config.py, deps.py, main.py

import os
from typing import Optional
from supabase import create_client, Client
import asyncpg
import logging

logger = logging.getLogger(__name__)

# Global singleton instances
_supabase: Optional[Client] = None
_pg_pool: Optional[asyncpg.Pool] = None


async def get_supabase(use_secret_key: bool = False) -> Client:
    """
    Get or create singleton Supabase client with async support.
    
    Args:
        use_secret_key: If True, uses SUPABASE_SECRET_KEY for backend operations.
                       If False, uses SUPABASE_PUBLISHABLE_KEY for web-facing API routes.
    """
    global _supabase

    if _supabase is None:
        # Initialize with async support enabled
        logger.info("Creating new Supabase client...")
        
        # Choose the appropriate key based on usage context
        api_key = (
            os.environ["SUPABASE_SECRET_KEY"] if use_secret_key 
            else os.environ["SUPABASE_PUBLISHABLE_KEY"]
        )
        
        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            api_key
        )
        logger.info(f"Supabase client created successfully with {'secret' if use_secret_key else 'publishable'} key")

    return _supabase


async def get_pg_pool() -> asyncpg.Pool:
    """
    Get or create PostgreSQL connection pool for raw SQL queries.
    Uses Supavisor pooling on port 6543 for efficient connection management.
    Only initialize if SUPABASE_DB_URL is provided.
    """
    global _pg_pool

    if _pg_pool is None:
        db_url = os.environ.get("SUPABASE_DB_URL")
        if not db_url:
            raise ValueError("SUPABASE_DB_URL not configured")

        logger.info("Creating PostgreSQL connection pool...")

        # Create pool with Supavisor connection (port 6543)
        # Connection string format: postgresql://postgres:[password]@[project].supabase.co:6543/postgres
        _pg_pool = await asyncpg.create_pool(
            dsn=db_url,
            max_size=20,  # Maximum number of connections in the pool
            min_size=2,  # Minimum number of connections to maintain
            timeout=10,  # Connection timeout in seconds
            command_timeout=10,  # Default timeout for queries
            max_inactive_connection_lifetime=300,  # Close idle connections after 5 minutes
        )

        logger.info(f"PostgreSQL pool created with max_size={_pg_pool._max_size}")

    return _pg_pool


async def close_connections():
    """
    Close all database connections gracefully.
    Called during application shutdown.
    """
    global _supabase, _pg_pool

    # Close Supabase client (httpx session)
    if _supabase and hasattr(_supabase, "_session") and _supabase._session:
        logger.info("Closing Supabase client session...")
        await _supabase._session.aclose()
        _supabase = None

    # Close PostgreSQL pool
    if _pg_pool:
        logger.info("Closing PostgreSQL connection pool...")
        await _pg_pool.close()
        _pg_pool = None
