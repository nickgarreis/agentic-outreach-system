# src/middleware.py
# FastAPI middleware for authentication and request processing
# Handles JWT validation, user context injection, and CORS
# RELEVANT FILES: auth.py, main.py, deps.py

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import logging
import time


logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject user context into requests.
    This runs on every request and adds user info if authenticated.
    """

    def __init__(self, app, validator=None):
        super().__init__(app)
        self.validator = validator

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/auth/login",
            "/api/auth/refresh",
        ]

        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        user = None

        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ", 1)[1]
                if self.validator:
                    user = await self.validator.verify_token(token)
                    # Attach user to request state
                    request.state.user = user
            except HTTPException:
                # Invalid token - let individual endpoints handle auth requirements
                pass
            except Exception as e:
                logger.error(f"Auth middleware error: {e}")

        # Process request
        response = await call_next(request)

        # Add user ID to response headers for debugging (optional)
        if user:
            response.headers["X-User-ID"] = user.user_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests for debugging and monitoring.
    Logs request details and response time.
    """

    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()

        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Response: {response.status_code} "
                f"for {request.method} {request.url.path} "
                f"({duration:.3f}s)"
            )

            # Add timing header
            response.headers["X-Process-Time"] = str(duration)

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"({duration:.3f}s) - Error: {str(e)}"
            )
            raise


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler middleware.
    Catches unhandled exceptions and returns proper JSON responses.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "type": type(e).__name__},
            )


def setup_cors(app, settings):
    """
    Configure CORS middleware for the application.
    Allows frontend applications to access the API.
    """
    # Get allowed origins from settings or use defaults
    allowed_origins = getattr(
        settings,
        "cors_origins",
        [
            "http://localhost:3000",  # React default
            "http://localhost:5173",  # Vite default
            "http://localhost:8080",  # Vue default
            "http://localhost:4200",  # Angular default
        ],
    )

    # Add production origins if configured
    if hasattr(settings, "frontend_url") and settings.frontend_url:
        allowed_origins.append(settings.frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,  # Allow cookies for auth
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
        expose_headers=["X-User-ID", "X-Process-Time"],  # Custom headers
    )

    logger.info(f"CORS configured for origins: {allowed_origins}")


def setup_middleware(app, settings):
    """
    Setup all middleware for the FastAPI application.
    Order matters - middleware runs in reverse order of registration.
    """
    # Error handler (outermost - catches everything)
    app.add_middleware(ErrorHandlerMiddleware)

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # CORS (before auth so preflight requests work)
    setup_cors(app, settings)

    # Authentication (innermost - runs first)
    # Note: We'll initialize the validator later after app startup
    app.add_middleware(AuthMiddleware)

    logger.info("All middleware configured successfully")
