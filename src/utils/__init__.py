# src/utils/__init__.py
# Utility modules for common functionality
# Provides helper functions and shared utilities across the application
# RELEVANT FILES: client_auth.py

from .client_auth import (
    ClientAuthError,
    get_user_client_role,
    check_client_access,
    require_client_role,
    can_manage_member,
    is_sole_owner,
)

__all__ = [
    "ClientAuthError",
    "get_user_client_role", 
    "check_client_access",
    "require_client_role",
    "can_manage_member",
    "is_sole_owner",
]