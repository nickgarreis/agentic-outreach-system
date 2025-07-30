# src/deps.py
# FastAPI dependency injection factories
# Provides database access and retry decorators
# RELEVANT FILES: database.py, config.py, main.py

from typing import AsyncGenerator, Callable, TypeVar
from fastapi import Depends, HTTPException, status
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from httpx import HTTPStatusError
from supabase import Client
import asyncpg
import logging

from .database import get_supabase, get_pg_pool
from .config import get_settings, Settings

logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar("T")


def create_retry_decorator(settings: Settings) -> Callable:
    """
    Create a retry decorator with exponential backoff for 429/5xx errors.
    Logs retry attempts for debugging.
    """

    def should_retry(exception: Exception) -> bool:
        """Determine if we should retry based on exception type and status"""
        if isinstance(exception, HTTPStatusError):
            # Retry on rate limit (429) or server errors (5xx)
            return (
                exception.response.status_code == 429
                or exception.response.status_code >= 500
            )
        return False

    return retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(
            multiplier=settings.retry_delay,
            max=settings.max_retry_delay,
        ),
        retry=retry_if_exception_type(HTTPStatusError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# FastAPI Dependencies


async def get_db() -> Client:
    """
    Get Supabase client dependency.
    Use this in FastAPI routes that need database access.

    Example:
        @app.get("/items")
        async def get_items(db: Client = Depends(get_db)):
            response = await db.table("items").select("*").execute()
            return response.data
    """
    return await get_supabase()


async def get_db_with_retry(
    settings: Settings = Depends(get_settings),
) -> tuple[Client, Callable]:
    """
    Get Supabase client with retry decorator.
    Returns both the client and a retry decorator configured with app settings.

    Example:
        @app.get("/items")
        async def get_items(db_retry = Depends(get_db_with_retry)):
            db, with_retry = db_retry

            @with_retry
            async def fetch_items():
                return await db.table("items").select("*").execute()

            response = await fetch_items()
            return response.data
    """
    client = await get_supabase()
    retry_decorator = create_retry_decorator(settings)
    return client, retry_decorator


async def get_raw_db() -> AsyncGenerator[asyncpg.Pool, None]:
    """
    Get PostgreSQL connection pool for raw SQL queries.
    Only use this when you need features not available through Supabase SDK.

    Example:
        @app.get("/custom-query")
        async def custom_query(pool: asyncpg.Pool = Depends(get_raw_db)):
            async with pool.acquire() as conn:
                result = await conn.fetch("SELECT * FROM users WHERE active = $1", True)
                return [dict(row) for row in result]
    """
    pool = await get_pg_pool()
    try:
        yield pool
    except Exception as e:
        logger.error(f"Error in raw database operation: {e}")
        raise


async def get_settings_dep() -> Settings:
    """
    Get application settings as a dependency.
    Useful when you need access to configuration in routes.
    """
    return get_settings()


from .auth import get_current_user, get_current_user_optional, UserClaims, AuthService  # noqa: E402

# Re-export auth dependencies for easy access
__all__ = ["get_current_user", "get_current_user_optional", "UserClaims"]


async def get_auth_service(db: Client = Depends(get_db)) -> AuthService:
    """
    Get AuthService instance for authentication operations.
    Use this in auth endpoints that need to perform login/logout.
    """
    return AuthService(db)


async def require_authenticated_user(
    user: UserClaims = Depends(get_current_user),
) -> UserClaims:
    """
    Dependency that requires an authenticated user.
    Use this for endpoints that must have authentication.

    Example:
        @app.get("/profile")
        async def get_profile(user: UserClaims = Depends(require_authenticated_user)):
            return {"user_id": user.user_id, "email": user.email}
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


async def get_user_client_access(
    user: UserClaims = Depends(get_current_user), db: Client = Depends(get_db)
) -> list[str]:
    """
    Get list of client IDs that the user has access to.
    This will be used to filter data based on user permissions.
    """
    try:
        # Query clients where user has access
        response = (
            await db.table("clients").select("id").eq("user_id", user.user_id).execute()
        )
        return [client["id"] for client in response.data]
    except Exception as e:
        logger.error(f"Failed to get user client access: {e}")
        return []


# Secret key dependency (only for background workers)


async def get_service_db(settings: Settings = Depends(get_settings_dep)) -> Client:
    """
    Get Supabase client with secret key.
    ONLY use this in background workers, never in web-facing routes!
    """
    if not settings.supabase_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Secret key not configured",
        )

    # Create a separate client with secret key
    from supabase import create_client

    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options={"is_async": True},
    )
