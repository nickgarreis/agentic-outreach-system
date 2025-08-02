# src/main.py
# FastAPI application entry point
# Manages application lifecycle and routing
# RELEVANT FILES: database.py, deps.py, config.py, schemas.py

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from .database import get_supabase, get_pg_pool, close_connections
from .config import get_settings
from .schemas import BaseResponse
from .middleware import setup_middleware
from .auth import get_validator
from .routers import auth_router, client_members_router, chat_router, webhooks
from .agent.agentops_config import init_agentops

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Initialize connections on startup, clean up on shutdown.
    """
    settings = get_settings()

    # Startup
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Running on Render: {settings.is_render}")

    try:
        # Initialize Supabase client
        logger.info("Initializing Supabase client...")
        await get_supabase()
        logger.info("✓ Supabase client initialized")

        # Initialize PostgreSQL pool if DB URL is configured
        if settings.supabase_db_url:
            logger.info("Initializing PostgreSQL connection pool...")
            pool = await get_pg_pool()
            logger.info(f"✓ PostgreSQL pool initialized (max_size={pool._max_size})")
        else:
            logger.info("⚠ PostgreSQL pool not initialized (SUPABASE_DB_URL not set)")

        # Initialize JWT validator and prefetch JWKS
        logger.info("Initializing JWT validator...")
        validator = get_validator(settings)
        # Prefetch JWKS keys to warm the cache
        await validator.prefetch_keys()
        # Set validator on auth middleware
        for middleware in app.user_middleware:
            if (
                hasattr(middleware, "cls")
                and middleware.cls.__name__ == "AuthMiddleware"
            ):
                middleware.kwargs["validator"] = validator
        logger.info("✓ JWT validator initialized with ES256 support")

        # Initialize AgentOps if API key is configured
        if settings.agentops_api_key:
            if init_agentops(settings.agentops_api_key):
                logger.info("✓ AgentOps initialized for monitoring")
            else:
                logger.warning(
                    "⚠ AgentOps initialization failed, continuing without monitoring"
                )
        else:
            logger.info("ℹ AgentOps not configured (no API key)")

        # Add any other startup tasks here
        logger.info(f"✓ {settings.app_name} started successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")

    try:
        await close_connections()
        logger.info("✓ All connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    logger.info("✓ Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Agentic Outreach System",
    description="AI-powered outreach automation system with Supabase backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup all middleware (CORS, Auth, Logging, Error handling)
settings = get_settings()
setup_middleware(app, settings)


# Health check endpoints


@app.get("/", response_model=BaseResponse)
async def root():
    """Root endpoint - basic health check"""
    return BaseResponse(
        success=True,
        message=f"{settings.app_name} is running",
        data={"version": "1.0.0", "debug": settings.debug},
    )


@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Detailed health check endpoint.
    Verifies all connections are working properly.
    """
    health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}

    # Check Supabase connection
    try:
        client = await get_supabase()
        # Simple query to verify connection
        await client.table("_test_connection").select("status").limit(1).execute()
        health_status["checks"]["supabase"] = "ok"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["supabase"] = f"error: {str(e)}"

    # Check PostgreSQL pool if configured
    if settings.supabase_db_url:
        try:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_status["checks"]["postgresql"] = "ok"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["postgresql"] = f"error: {str(e)}"

    return health_status


# API Routes - organize by feature

# Authentication routes (no additional prefix since it has /api/auth built in)
app.include_router(auth_router)

# Client member management routes
app.include_router(client_members_router)

# Chat routes for agent communication
app.include_router(chat_router, prefix="/api", tags=["chat"])

# Webhook routes (no auth required for external services)
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])

# Future routers will be added here:
# app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
# app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
# app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
# app.include_router(messages.router, prefix="/api/messages", tags=["messages"])


# Error handlers


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return BaseResponse(
        success=False, message="Resource not found", data={"path": request.url.path}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return BaseResponse(success=False, message="Internal server error", data=None)


# For local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=settings.debug, log_level="info"
    )
