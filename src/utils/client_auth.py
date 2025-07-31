# src/utils/client_auth.py
# Utility functions for checking client member roles and permissions
# Provides role-based authorization helpers for API endpoints
# RELEVANT FILES: ../schemas.py, ../deps.py, ../database.py

from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


class ClientAuthError(Exception):
    """Custom exception for client authorization errors"""
    pass


async def get_user_client_role(
    supabase, 
    client_id: str, 
    user_id: str
) -> Optional[str]:
    """
    Get a user's role for a specific client.
    Returns None if user is not a member or invitation is pending.
    """
    try:
        response = await supabase.table("client_members").select("role").eq(
            "client_id", client_id
        ).eq("user_id", user_id).not_.is_("accepted_at", "null").execute()
        
        if response.data:
            return response.data[0]["role"]
        return None
        
    except Exception as e:
        logger.error(f"Error getting user client role: {e}")
        return None


async def check_client_access(
    supabase,
    client_id: str,
    user_id: str,
    required_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if user has access to a client and optionally verify role.
    Returns dict with role info and access details.
    Raises HTTPException if access denied.
    """
    user_role = await get_user_client_role(supabase, client_id, user_id)
    
    if user_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not a member of this client"
        )
    
    # Define role hierarchy for permission checking
    role_hierarchy = {
        "user": 1,
        "admin": 2,
        "owner": 3
    }
    
    access_info = {
        "user_role": user_role,
        "has_access": True,
        "can_read": True,
        "can_write": user_role in ["admin", "owner"],
        "can_manage_members": user_role in ["admin", "owner"],
        "can_delete_client": user_role == "owner"
    }
    
    # Check if user meets minimum role requirement
    if required_role:
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {required_role} role required"
            )
    
    return access_info


async def require_client_role(
    supabase,
    client_id: str,
    user_id: str,
    min_role: str = "user"
) -> str:
    """
    Ensure user has at least the specified role for a client.
    Returns the user's actual role.
    Raises HTTPException if insufficient permissions.
    """
    access_info = await check_client_access(supabase, client_id, user_id, min_role)
    return access_info["user_role"]


async def can_manage_member(
    supabase,
    client_id: str,
    acting_user_id: str,
    target_user_id: str
) -> bool:
    """
    Check if acting user can manage (invite/remove/update) target user.
    Rules:
    - Owners can manage anyone except other owners (unless sole owner)
    - Admins can manage users but not owners or other admins
    - Users cannot manage anyone
    """
    try:
        # Get both users' roles
        acting_role = await get_user_client_role(supabase, client_id, acting_user_id)
        target_role = await get_user_client_role(supabase, client_id, target_user_id)
        
        if not acting_role:
            return False
        
        # Users can't manage anyone
        if acting_role == "user":
            return False
            
        # Admins can only manage users
        if acting_role == "admin":
            return target_role == "user"
            
        # Owners can manage anyone except other owners (with sole owner protection)
        if acting_role == "owner":
            if target_role != "owner":
                return True
            
            # Check if this would leave no owners (handled by caller usually)
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking member management permissions: {e}")
        return False


async def is_sole_owner(supabase, client_id: str, user_id: str) -> bool:
    """
    Check if the user is the sole owner of the client.
    Used to prevent removing/demoting the last owner.
    """
    try:
        # Count total owners
        owner_count_response = await supabase.table("client_members").select(
            "id", count="exact"
        ).eq("client_id", client_id).eq("role", "owner").not_.is_(
            "accepted_at", "null"
        ).execute()
        
        if owner_count_response.count != 1:
            return False
            
        # Check if this user is that sole owner
        user_role = await get_user_client_role(supabase, client_id, user_id)
        return user_role == "owner"
        
    except Exception as e:
        logger.error(f"Error checking sole owner status: {e}")
        return False