from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_invitations(
    user=Depends(get_current_user),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List invitations - admins see all, others see their own"""
    query = supabase.table("invitations").select(
        """
        *,
        tenant:tenant_id(id, name),
        role:role_id(id, name),
        inviter:invited_by(id, email, full_name)
        """
    )

    # If not super admin, filter to own invitations or tenant invitations
    if user.get("role_id") != 1:
        # Get user's tenant IDs where they're admin
        user_tenants_res = (
            supabase.table("tenant_users")
            .select("tenant_id")
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .execute()
        )
        tenant_ids = [t["tenant_id"] for t in user_tenants_res.data]

        # Show invitations sent by user or for their tenants
        if tenant_ids:
            query = query.or_(f"invited_by.eq.{user['id']},tenant_id.in.({','.join(tenant_ids)})")
        else:
            query = query.eq("invited_by", user["id"])

    if tenant_id:
        query = query.eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)

    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)

    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_invitation(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Send an invitation to join a tenant
    Requires: email, tenant_id, role_id
    Optional: expires_at, metadata
    """
    email = payload.get("email")
    tenant_id = payload.get("tenant_id")
    role_id = payload.get("role_id", 4)  # Default to Contractor

    if not email or not tenant_id:
        raise HTTPException(400, "email and tenant_id are required")

    # Check permission
    if user.get("role_id") != 1:  # Not super admin
        # Check if user is admin of this tenant
        admin_check = (
            supabase.table("tenant_users")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user["id"])
            .eq("role_id", 2)
            .limit(1)
            .execute()
        )

        if not admin_check.data:
            raise HTTPException(403, "Only tenant admins can send invitations")

    # Check if user already exists with this email
    existing_user = (
        supabase.table("profiles")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if existing_user.data:
        raise HTTPException(
            400,
            "User with this email already exists. Use tenant assignment instead."
        )

    # Check if invitation already exists and is pending
    existing_invite = (
        supabase.table("invitations")
        .select("id, status")
        .eq("email", email)
        .eq("tenant_id", tenant_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )

    if existing_invite.data:
        raise HTTPException(400, "Pending invitation already exists for this email")

    # Create invitation
    invitation_data = {
        "email": email,
        "tenant_id": tenant_id,
        "role_id": role_id,
        "invited_by": user["id"],
        "status": "pending",
        "metadata": payload.get("metadata", {}),
    }

    # Set expiration if provided
    if payload.get("expires_at"):
        invitation_data["expires_at"] = payload["expires_at"]

    res = supabase.table("invitations").insert(invitation_data).execute()
    invitation = ensure_response(res)

    # TODO: Send invitation email via Supabase Auth or email service
    # For now, return the invitation with token
    return invitation


@router.get("/{invitation_id}")
async def get_invitation(
    invitation_id: str,
    user=Depends(get_current_user),
):
    """Get invitation details"""
    res = (
        supabase.table("invitations")
        .select(
            """
            *,
            tenant:tenant_id(id, name),
            role:role_id(id, name),
            inviter:invited_by(id, email, full_name)
            """
        )
        .eq("id", invitation_id)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Invitation not found")

    invitation = data[0] if isinstance(data, list) else data

    # Check permission
    if user.get("role_id") != 1:  # Not super admin
        if (
            invitation["invited_by"] != user["id"]
            and invitation["email"] != user.get("email")
        ):
            raise HTTPException(403, "Access denied")

    return invitation


@router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    user=Depends(get_current_user),
):
    """Accept an invitation and join the tenant"""
    # Get invitation
    invite_res = (
        supabase.table("invitations")
        .select("*")
        .eq("id", invitation_id)
        .limit(1)
        .execute()
    )

    invite_data = ensure_response(invite_res)
    if not invite_data:
        raise HTTPException(404, "Invitation not found")

    invitation = invite_data[0] if isinstance(invite_data, list) else invite_data

    # Verify user email matches invitation
    if invitation["email"] != user.get("email"):
        raise HTTPException(403, "This invitation is for a different email")

    # Check status
    if invitation["status"] != "pending":
        raise HTTPException(400, f"Invitation is {invitation['status']}")

    # Check expiration
    if invitation["expires_at"]:
        expires_at = datetime.fromisoformat(invitation["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.now(expires_at.tzinfo):
            # Update status to expired
            supabase.table("invitations").update({"status": "expired"}).eq(
                "id", invitation_id
            ).execute()
            raise HTTPException(400, "Invitation has expired")

    # Create tenant_user relationship
    tenant_user_data = {
        "tenant_id": invitation["tenant_id"],
        "user_id": user["id"],
        "role_id": invitation["role_id"],
        "invited_by": invitation["invited_by"],
        "status": "active",
    }

    try:
        supabase.table("tenant_users").insert(tenant_user_data).execute()

        # Update invitation status
        supabase.table("invitations").update(
            {"status": "accepted", "accepted_at": datetime.utcnow().isoformat(), "accepted_by": user["id"]}
        ).eq("id", invitation_id).execute()

        return {"message": "Invitation accepted successfully", "tenant_id": invitation["tenant_id"]}

    except Exception as e:
        raise HTTPException(500, f"Failed to accept invitation: {str(e)}")


@router.post("/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: str,
    user=Depends(get_current_user),
):
    """Resend an invitation email"""
    # Get invitation
    invite_res = (
        supabase.table("invitations")
        .select("*")
        .eq("id", invitation_id)
        .limit(1)
        .execute()
    )

    invite_data = ensure_response(invite_res)
    if not invite_data:
        raise HTTPException(404, "Invitation not found")

    invitation = invite_data[0] if isinstance(invite_data, list) else invite_data

    # Check permission
    if user.get("role_id") != 1 and invitation["invited_by"] != user["id"]:
        raise HTTPException(403, "Only the inviter can resend")

    if invitation["status"] != "pending":
        raise HTTPException(400, "Can only resend pending invitations")

    # Extend expiration
    new_expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    supabase.table("invitations").update({"expires_at": new_expires_at}).eq(
        "id", invitation_id
    ).execute()

    # TODO: Resend email
    return {"message": "Invitation resent", "expires_at": new_expires_at}


@router.delete("/{invitation_id}")
async def cancel_invitation(
    invitation_id: str,
    user=Depends(get_current_user),
):
    """Cancel a pending invitation"""
    # Get invitation
    invite_res = (
        supabase.table("invitations")
        .select("*")
        .eq("id", invitation_id)
        .limit(1)
        .execute()
    )

    invite_data = ensure_response(invite_res)
    if not invite_data:
        raise HTTPException(404, "Invitation not found")

    invitation = invite_data[0] if isinstance(invite_data, list) else invite_data

    # Check permission
    if user.get("role_id") != 1 and invitation["invited_by"] != user["id"]:
        raise HTTPException(403, "Only the inviter can cancel")

    # Update status to cancelled
    supabase.table("invitations").update({"status": "cancelled"}).eq(
        "id", invitation_id
    ).execute()

    return {"message": "Invitation cancelled"}


@router.get("/token/{token}")
async def get_invitation_by_token(
    token: str,
):
    """Get invitation by token (public endpoint for acceptance page)"""
    res = (
        supabase.table("invitations")
        .select(
            """
            *,
            tenant:tenant_id(id, name),
            role:role_id(id, name)
            """
        )
        .eq("token", token)
        .limit(1)
        .execute()
    )

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Invitation not found")

    invitation = data[0] if isinstance(data, list) else data

    # Don't return if already used or expired
    if invitation["status"] != "pending":
        raise HTTPException(400, f"Invitation is {invitation['status']}")

    # Check expiration
    if invitation["expires_at"]:
        expires_at = datetime.fromisoformat(invitation["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.now(expires_at.tzinfo):
            raise HTTPException(400, "Invitation has expired")

    return invitation
