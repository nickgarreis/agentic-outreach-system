# src/main.py
# FastAPI application entry point
# Manages application lifecycle and routing
# RELEVANT FILES: database.py, deps.py, config.py, schemas.py

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from .database import get_supabase, get_pg_pool, close_connections
from .config import get_settings
from .deps import get_db, get_db_with_retry
from .schemas import BaseResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
        client = await get_supabase()
        logger.info(" Supabase client initialized")
        
        # Initialize PostgreSQL pool if DB URL is configured
        if settings.supabase_db_url:
            logger.info("Initializing PostgreSQL connection pool...")
            pool = await get_pg_pool()
            logger.info(f" PostgreSQL pool initialized (max_size={pool._max_size})")
        else:
            logger.info("  PostgreSQL pool not initialized (SUPABASE_DB_URL not set)")
        
        # Add any other startup tasks here
        logger.info(f" {settings.app_name} started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        await close_connections()
        logger.info(" All connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info(" Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Agentic Outreach System",
    description="AI-powered outreach automation system with Supabase backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all requests with timing information.
    Helps with debugging and performance monitoring.
    """
    # Generate request ID for tracing
    request_id = f"{time.time()}"
    
    # Log request
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"- Client: {request.client.host if request.client else 'unknown'}"
    )
    
    # Time the request
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Duration: {duration:.3f}s"
        )
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(duration)
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} "
            f"- Error: {str(e)} - Duration: {duration:.3f}s"
        )
        raise


# Health check endpoints

@app.get("/", response_model=BaseResponse)
async def root():
    """Root endpoint - basic health check"""
    return BaseResponse(
        success=True,
        message=f"{settings.app_name} is running",
        data={"version": "1.0.0", "debug": settings.debug}
    )


@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Detailed health check endpoint.
    Verifies all connections are working properly.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {}
    }
    
    # Check Supabase connection
    try:
        client = await get_supabase()
        # Simple query to verify connection
        await client.table("_test_connection").select("1").limit(1).execute()
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
# Import routers here as you create them
# Example:
# from .routers import campaigns, clients, jobs
# app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
# app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
# app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


# Error handlers

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return BaseResponse(
        success=False,
        message="Resource not found",
        data={"path": request.url.path}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return BaseResponse(
        success=False,
        message="Internal server error",
        data=None
    )


# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )