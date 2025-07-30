# src/auth.py
# Authentication module for JWT validation and user management
# Handles JWT verification using ES256 (Elliptic Curve) asymmetric keys
# RELEVANT FILES: deps.py, config.py, main.py

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from functools import wraps
import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, PyJWKClientError
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

from .config import get_settings, Settings

logger = logging.getLogger(__name__)

# Security scheme for FastAPI docs
security = HTTPBearer()


class UserClaims(BaseModel):
    """Parsed JWT claims for authenticated users"""

    sub: str  # User ID
    email: Optional[str] = None
    role: str = "authenticated"
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    session_id: Optional[str] = None

    @property
    def user_id(self) -> str:
        """Get user ID from sub claim"""
        return self.sub

    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now(timezone.utc).timestamp() > self.exp


class JWTValidator:
    """
    Validates JWTs using Supabase's public keys (JWKS) with ES256 algorithm.
    Implements caching and robust error handling for production use.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        self.issuer = f"{settings.supabase_url}/auth/v1"

        # PyJWKClient handles caching internally
        self.jwks_client = PyJWKClient(
            self.jwks_url,
            cache_keys=True,
            max_cached_keys=2,  # Handle key rotation
            cache_jwk_set=True,
            lifespan=3600,  # Cache for 1 hour
        )

        # Configuration for ES256 validation
        self.algorithms = ["ES256"]  # Only allow Elliptic Curve
        self.audience = "authenticated"

        # For monitoring
        self._validation_count = 0
        self._cache_hits = 0
        self._last_key_refresh = None

    async def verify_token(self, token: str) -> UserClaims:
        """
        Verify JWT token using ES256 asymmetric validation.
        Uses cached public keys for performance.
        """
        try:
            # Get the signing key from JWKS
            try:
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                self._cache_hits += 1
            except PyJWKClientError as e:
                # Log key fetch errors for monitoring
                logger.warning(f"JWKS fetch error (will retry): {e}")
                # Retry once with fresh keys
                self.jwks_client.fetch_data()
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                self._last_key_refresh = datetime.now(timezone.utc)

            # Verify the token with ES256
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_signature": True,
                    "require": ["exp", "iat", "sub"],
                },
            )

            # Track successful validations
            self._validation_count += 1

            # Log validation metrics periodically
            if self._validation_count % 100 == 0:
                logger.info(
                    f"JWT validation metrics: "
                    f"total={self._validation_count}, "
                    f"cache_hits={self._cache_hits}, "
                    f"hit_rate={self._cache_hits/self._validation_count:.2%}"
                )

            return UserClaims(**payload)

        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def prefetch_keys(self) -> None:
        """
        Prefetch JWKS on startup to warm the cache.
        This prevents cold start delays on first request.
        """
        try:
            logger.info("Prefetching JWKS keys...")
            self.jwks_client.fetch_data()
            self._last_key_refresh = datetime.now(timezone.utc)
            logger.info("JWKS keys successfully cached")
        except Exception as e:
            logger.error(f"Failed to prefetch JWKS: {e}")
            # Don't fail startup, keys will be fetched on first use

    def get_metrics(self) -> Dict[str, Any]:
        """Get validation metrics for monitoring"""
        return {
            "total_validations": self._validation_count,
            "cache_hits": self._cache_hits,
            "hit_rate": self._cache_hits / max(1, self._validation_count),
            "last_key_refresh": (
                self._last_key_refresh.isoformat() if self._last_key_refresh else None
            ),
            "jwks_url": self.jwks_url,
            "algorithms": self.algorithms,
        }


# Global validator instance
_validator = None


def get_validator(settings: Settings = Depends(get_settings)) -> JWTValidator:
    """Get or create JWT validator instance"""
    global _validator
    if not _validator:
        _validator = JWTValidator(settings)
    return _validator


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    validator: JWTValidator = Depends(get_validator),
) -> UserClaims:
    """
    Dependency to get current authenticated user from JWT.
    Use this in protected endpoints.

    Example:
        @app.get("/protected")
        async def protected_route(user: UserClaims = Depends(get_current_user)):
            return {"user_id": user.user_id, "email": user.email}
    """
    token = credentials.credentials
    return await validator.verify_token(token)


async def get_current_user_optional(
    request: Request, validator: JWTValidator = Depends(get_validator)
) -> Optional[UserClaims]:
    """
    Optional authentication - returns None if no valid token.
    Use for endpoints that work both authenticated and anonymous.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ", 1)[1]
        return await validator.verify_token(token)
    except HTTPException:
        return None


def require_roles(allowed_roles: List[str]):
    """
    Decorator for role-based access control.

    Example:
        @app.get("/admin")
        @require_roles(["admin", "super_admin"])
        async def admin_route(user: UserClaims = Depends(get_current_user)):
            return {"message": "Admin access granted"}
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by FastAPI)
            user = kwargs.get("user")
            if not user or not isinstance(user, UserClaims):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user.role}' not authorized. Required: {allowed_roles}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class AuthService:
    """Service for authentication operations"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login user with email and password"""
        try:
            response = self.supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.role,
                },
            }
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

    async def logout(self, token: str) -> None:
        """Logout user and revoke token"""
        try:
            # Set the auth token for this request
            self.supabase.auth.set_session(token)
            self.supabase.auth.sign_out()
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            # Don't raise - logout should always succeed client-side

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            response = self.supabase.auth.admin.get_user_by_id(user_id)
            return {
                "id": response.user.id,
                "email": response.user.email,
                "created_at": response.user.created_at,
                "last_sign_in_at": response.user.last_sign_in_at,
                "metadata": response.user.user_metadata,
            }
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
