# src/routers/client_members.py
# API routes for client member management (invite, remove, update roles)
# Implements role-based access control for multi-user client access
# RELEVANT FILES: ../schemas.py, ../deps.py, ../database.py, ../auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import logging
from uuid import UUID, uuid4

from ..database import get_supabase
from ..deps import get_current_user
from ..schemas import (
    BaseResponse,
    ClientMemberInvite,
    ClientMemberUpdate,
    ClientMemberResponse,
    ClientRole,
    PaginatedResponse,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(prefix="/api/clients", tags=["client-members"])


@router.get("/{client_id}/members", response_model=List[ClientMemberResponse])
async def list_client_members(
    client_id: str,
    include_pending: bool = False,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """
    List all members of a client.
    Only accessible to current members of the client.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client ID format"
        )

    try:
        # Build query to get members with user details
        query = supabase.table("client_members").select(
            """
            id,
            client_id,
            user_id,
            role,
            created_at,
            invited_by,
            invited_at,
            accepted_at,
            auth.users!user_id(email, raw_user_meta_data)
            """
        ).eq("client_id", str(client_uuid))
        
        # Filter by acceptance status
        if not include_pending:
            query = query.not_.is_("accepted_at", "null")
        
        # Execute query
        response = await query.execute()
        
        if not response.data:
            return []
        
        # Transform response to include user details and status flags
        members = []
        for member in response.data:
            user_data = member.get("auth", {}).get("users", {}) if member.get("auth") else {}
            user_email = user_data.get("email", "")
            user_meta = user_data.get("raw_user_meta_data", {}) or {}
            user_name = user_meta.get("name", user_meta.get("full_name", ""))
            
            member_response = ClientMemberResponse(
                id=member["id"],
                client_id=member["client_id"],
                user_id=member["user_id"],
                role=member["role"],
                created_at=member["created_at"],
                invited_by=member.get("invited_by"),
                invited_at=member.get("invited_at"),
                accepted_at=member.get("accepted_at"),
                user_email=user_email,
                user_name=user_name,
                is_pending=member.get("accepted_at") is None,
                is_current_user=member["user_id"] == current_user["sub"],
                updated_at=None  # Not tracked in current schema
            )
            members.append(member_response)
        
        return members
        
    except Exception as e:
        logger.error(f"Error listing client members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list client members"
        )


@router.post("/{client_id}/members", response_model=BaseResponse)
async def invite_client_member(
    client_id: str,
    invite: ClientMemberInvite,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """
    Invite a user to join a client with a specific role.
    Only accessible to owners and admins.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client ID format"
        )

    try:
        # Check if user to invite exists
        user_response = await supabase.auth.admin.list_users()
        target_user = None
        for user in user_response.users:
            if user.email == invite.user_email:
                target_user = user
                break
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User with this email not found"
            )
        
        # Check if user is already a member
        existing_response = await supabase.table("client_members").select("id").eq(
            "client_id", str(client_uuid)
        ).eq("user_id", target_user.id).execute()
        
        if existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this client"
            )
        
        # Insert invitation
        invitation_data = {
            "id": str(uuid4()),
            "client_id": str(client_uuid),
            "user_id": target_user.id,
            "role": invite.role.value,
            "invited_by": current_user["sub"],
            "invited_at": "now()",
            "accepted_at": None,  # Pending acceptance
        }
        
        response = await supabase.table("client_members").insert(invitation_data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create invitation"
            )
        
        logger.info(f"User {current_user['sub']} invited {invite.user_email} to client {client_id} as {invite.role}")
        
        return BaseResponse(
            success=True,
            message=f"Invitation sent to {invite.user_email}",
            data={"invitation_id": response.data[0]["id"]}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inviting client member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite member"
        )


@router.post("/{client_id}/members/accept", response_model=BaseResponse)
async def accept_client_invitation(
    client_id: str,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """
    Accept a pending invitation to join a client.
    Only the invited user can accept their own invitation.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client ID format"
        )

    try:
        # Find pending invitation for current user
        invitation_response = await supabase.table("client_members").select("*").eq(
            "client_id", str(client_uuid)
        ).eq("user_id", current_user["sub"]).is_("accepted_at", "null").execute()
        
        if not invitation_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending invitation found"
            )
        
        invitation = invitation_response.data[0]
        
        # Accept invitation by setting accepted_at timestamp
        update_response = await supabase.table("client_members").update({
            "accepted_at": "now()"
        }).eq("id", invitation["id"]).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to accept invitation"
            )
        
        logger.info(f"User {current_user['sub']} accepted invitation to client {client_id}")
        
        return BaseResponse(
            success=True,
            message="Invitation accepted successfully",
            data={"role": invitation["role"]}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept invitation"
        )


@router.put("/{client_id}/members/{user_id}", response_model=BaseResponse)
async def update_client_member_role(
    client_id: str,
    user_id: str,
    update: ClientMemberUpdate,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """
    Update a client member's role.
    Only accessible to owners and admins.
    Owners cannot be demoted if they are the sole owner.
    """
    try:
        client_uuid = UUID(client_id)
        target_user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client ID or user ID format"
        )

    try:
        # Get current member data
        member_response = await supabase.table("client_members").select("*").eq(
            "client_id", str(client_uuid)
        ).eq("user_id", str(target_user_uuid)).not_.is_("accepted_at", "null").execute()
        
        if not member_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        current_member = member_response.data[0]
        
        # Special handling for owner role changes
        if current_member["role"] == "owner" and update.role != ClientRole.OWNER:
            # Check if this is the sole owner
            owner_count_response = await supabase.table("client_members").select(
                "id", count="exact"
            ).eq("client_id", str(client_uuid)).eq("role", "owner").not_.is_(
                "accepted_at", "null"
            ).execute()
            
            if owner_count_response.count == 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change role of sole owner. Promote another member to owner first."
                )
        
        # Update member role
        update_response = await supabase.table("client_members").update({
            "role": update.role.value
        }).eq("id", current_member["id"]).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update member role"
            )
        
        logger.info(f"User {current_user['sub']} updated {user_id} role to {update.role} in client {client_id}")
        
        return BaseResponse(
            success=True,
            message=f"Member role updated to {update.role}",
            data={"new_role": update.role}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member role"
        )


@router.delete("/{client_id}/members/{user_id}", response_model=BaseResponse)
async def remove_client_member(
    client_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """
    Remove a member from a client.
    Owners and admins can remove members.
    Users can remove themselves.
    Sole owners cannot be removed.
    """
    try:
        client_uuid = UUID(client_id)
        target_user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client ID or user ID format"
        )

    try:
        # Get member to remove
        member_response = await supabase.table("client_members").select("*").eq(
            "client_id", str(client_uuid)
        ).eq("user_id", str(target_user_uuid)).execute()
        
        if not member_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        target_member = member_response.data[0]
        
        # Check if trying to remove sole owner
        if target_member["role"] == "owner":
            owner_count_response = await supabase.table("client_members").select(
                "id", count="exact"
            ).eq("client_id", str(client_uuid)).eq("role", "owner").not_.is_(
                "accepted_at", "null"
            ).execute()
            
            if owner_count_response.count == 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove sole owner. Transfer ownership first."
                )
        
        # Remove member
        delete_response = await supabase.table("client_members").delete().eq(
            "id", target_member["id"]
        ).execute()
        
        if not delete_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove member"
            )
        
        logger.info(f"User {current_user['sub']} removed {user_id} from client {client_id}")
        
        return BaseResponse(
            success=True,
            message="Member removed successfully",
            data={}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member"
        )