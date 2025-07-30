# src/routers/auth.py
# Authentication API endpoints for login, logout, token refresh, and user profile
# Provides secure authentication flow for the frontend application
# RELEVANT FILES: ../auth.py, ../deps.py, ../schemas.py

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, EmailStr
import logging

from ..deps import get_auth_service, get_current_user, UserClaims
from ..auth import AuthService, JWTValidator, get_validator

logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)


# Request/Response schemas
class LoginRequest(BaseModel):
    """Login request with email and password"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with tokens and user info"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: Dict[str, Any]


class RefreshRequest(BaseModel):
    """Token refresh request"""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class UserProfileResponse(BaseModel):
    """User profile information"""

    id: str
    email: str
    created_at: str
    last_sign_in_at: str | None = None
    metadata: Dict[str, Any] | None = None


# Endpoints
@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    """
    Login with email and password.
    Returns access token, refresh token, and user information.
    """
    try:
        result = await auth_service.login(request.email, request.password)
        return LoginResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user=result["user"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user: UserClaims = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Logout the current user.
    Revokes the current session on the server side.
    """
    try:
        # Get token from user claims (the token used to authenticate this request)
        # In production, you might want to pass the token explicitly
        await auth_service.logout(user.session_id)

        # Clear cookies if you're using them
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Don't fail logout - always succeed from client perspective


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)
) -> RefreshResponse:
    """
    Refresh access token using refresh token.
    Returns new access and refresh tokens.
    """
    try:
        result = await auth_service.refresh_token(request.refresh_token)
        return RefreshResponse(
            access_token=result["access_token"], refresh_token=result["refresh_token"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    user: UserClaims = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    """
    Get current user profile information.
    Requires authentication.
    """
    try:
        # Get full profile from Supabase
        profile = await auth_service.get_user_profile(user.user_id)

        return UserProfileResponse(
            id=profile["id"],
            email=profile["email"],
            created_at=profile["created_at"],
            last_sign_in_at=profile.get("last_sign_in_at"),
            metadata=profile.get("metadata"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile",
        )


@router.post("/verify", response_model=Dict[str, Any])
async def verify_token(user: UserClaims = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Verify if the current token is valid.
    Returns user claims if valid.
    """
    return {
        "valid": True,
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "expires_at": user.exp,
    }


# Health check endpoint (no auth required)
@router.get("/health", include_in_schema=False)
async def auth_health() -> Dict[str, str]:
    """
    Health check for auth service.
    Used for monitoring.
    """
    return {"status": "healthy", "service": "auth"}


# JWT validation metrics endpoint (for monitoring)
@router.get("/metrics", response_model=Dict[str, Any])
async def get_auth_metrics(
    user: UserClaims = Depends(get_current_user),
    validator: JWTValidator = Depends(get_validator),
) -> Dict[str, Any]:
    """
    Get JWT validation metrics.
    Requires authentication. Useful for monitoring ES256 validation performance.
    """
    return {
        "validation_metrics": validator.get_metrics(),
        "current_user": user.user_id,
        "algorithm": "ES256",
        "key_type": "asymmetric",
    }
