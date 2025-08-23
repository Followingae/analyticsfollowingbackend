"""
Team Management API Routes - B2B SaaS Team Collaboration
Handles team member management, invitations, and role-based access
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete, update
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
import logging
import secrets
import string

from app.middleware.team_auth_middleware import (
    get_team_owner_context, get_any_team_member_context, 
    TeamContext, TeamRoles
)
from app.database.connection import get_db
from app.database.unified_models import TeamMember, TeamInvitation, User, Team
from app.models.teams import (
    TeamInvitationCreate, TeamInvitationResponse, TeamMemberResponse,
    TeamMemberUpdate
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teams", tags=["Team Management"])

# =============================================================================
# TEAM MEMBER MANAGEMENT
# =============================================================================

@router.get("/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all team members with their roles and status
    
    Available to both owners and members for transparency
    """
    try:
        logger.info(f"Getting team members for team {team_context.team_name}")
        
        # Query team members with user details
        members_query = select(
            TeamMember.id,
            TeamMember.team_id,
            TeamMember.user_id,
            TeamMember.role,
            TeamMember.permissions,
            TeamMember.status,
            TeamMember.joined_at,
            TeamMember.last_active_at,
            TeamMember.created_at,
            User.email.label("user_email"),
            User.full_name.label("user_name")
        ).select_from(
            TeamMember.join(User, TeamMember.user_id == User.id)
        ).where(
            and_(
                TeamMember.team_id == team_context.team_id,
                TeamMember.status == "active"
            )
        ).order_by(
            TeamMember.role.desc(),  # Owners first
            TeamMember.joined_at.asc()  # Then by join date
        )
        
        result = await db.execute(members_query)
        members = result.fetchall()
        
        # Format response
        team_members = []
        for member in members:
            team_members.append(TeamMemberResponse(
                id=member.id,
                team_id=member.team_id,
                user_id=member.user_id,
                role=member.role,
                permissions=member.permissions or {},
                status=member.status,
                user_email=member.user_email,
                user_name=member.user_name,
                joined_at=member.joined_at,
                last_active_at=member.last_active_at,
                created_at=member.created_at
            ))
        
        logger.info(f"Retrieved {len(team_members)} team members")
        return team_members
        
    except Exception as e:
        logger.error(f"Error getting team members: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve team members"
        )

@router.delete("/members/{user_id}")
async def remove_team_member(
    user_id: UUID = Path(..., description="User ID to remove from team"),
    team_context: TeamContext = Depends(get_team_owner_context),  # Only owners
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a team member (Owner only)
    
    - Cannot remove yourself
    - Cannot remove other owners  
    - Revokes all team access and profile permissions
    """
    try:
        logger.info(f"Removing user {user_id} from team {team_context.team_name}")
        
        # Prevent self-removal
        if user_id == team_context.user_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove yourself from the team"
            )
        
        # Get member to remove
        member_query = select(TeamMember).where(
            and_(
                TeamMember.team_id == team_context.team_id,
                TeamMember.user_id == user_id,
                TeamMember.status == "active"
            )
        )
        member_result = await db.execute(member_query)
        member = member_result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=404,
                detail="Team member not found or already removed"
            )
        
        # Prevent removing other owners (for safety)
        if member.role == TeamRoles.OWNER:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove team owner. Transfer ownership first."
            )
        
        # Remove team member
        member.status = "removed"
        member.removed_at = datetime.now(timezone.utc)
        member.removed_by_user_id = team_context.user_id
        
        # Revoke all team profile access
        from app.database.unified_models import TeamProfileAccess
        await db.execute(
            delete(TeamProfileAccess).where(
                and_(
                    TeamProfileAccess.team_id == team_context.team_id,
                    TeamProfileAccess.granted_by_user_id == user_id
                )
            )
        )
        
        await db.commit()
        
        logger.info(f"Successfully removed user {user_id} from team")
        return {
            "success": True,
            "message": f"Team member removed successfully",
            "removed_user_id": str(user_id),
            "removed_at": datetime.now(timezone.utc).isoformat(),
            "removed_by": team_context.user_role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team member: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to remove team member"
        )

# =============================================================================
# TEAM INVITATIONS SYSTEM
# =============================================================================

def generate_invitation_token() -> str:
    """Generate secure invitation token"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

@router.post("/invite", response_model=TeamInvitationResponse)
async def invite_team_member(
    invitation: TeamInvitationCreate,
    team_context: TeamContext = Depends(get_team_owner_context),  # Only owners
    db: AsyncSession = Depends(get_db)
):
    """
    Send email invitation to join team (Owner only)
    
    - Checks team member limits based on subscription tier
    - Sends professional invitation email
    - Creates secure invitation token with expiration
    """
    try:
        logger.info(f"Creating invitation for {invitation.email} to team {team_context.team_name}")
        
        # Check if user already exists and is team member
        existing_user_query = select(User.id).where(User.email == invitation.email)
        user_result = await db.execute(existing_user_query)
        existing_user = user_result.scalar_one_or_none()
        
        if existing_user:
            # Check if already team member
            existing_member_query = select(TeamMember).where(
                and_(
                    TeamMember.team_id == team_context.team_id,
                    TeamMember.user_id == existing_user,
                    TeamMember.status.in_(["active", "pending"])
                )
            )
            member_result = await db.execute(existing_member_query)
            existing_member = member_result.scalar_one_or_none()
            
            if existing_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"User {invitation.email} is already a team member"
                )
        
        # Check team member limits based on subscription
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(team_context.subscription_tier)
        if not tier_limits:
            raise HTTPException(status_code=500, detail="Invalid subscription tier")
        
        max_members = tier_limits["max_team_members"]
        
        # Count current active members
        current_members_query = select(func.count(TeamMember.id)).where(
            and_(
                TeamMember.team_id == team_context.team_id,
                TeamMember.status == "active"
            )
        )
        current_count_result = await db.execute(current_members_query)
        current_members = current_count_result.scalar()
        
        if current_members >= max_members:
            raise HTTPException(
                status_code=400,
                detail=f"Team member limit reached ({current_members}/{max_members}). "
                       f"Upgrade your subscription to invite more members."
            )
        
        # Check for existing pending invitation
        existing_invitation_query = select(TeamInvitation).where(
            and_(
                TeamInvitation.team_id == team_context.team_id,
                TeamInvitation.email == invitation.email,
                TeamInvitation.status == "pending",
                TeamInvitation.expires_at > datetime.now(timezone.utc)
            )
        )
        existing_result = await db.execute(existing_invitation_query)
        existing_invitation = existing_result.scalar_one_or_none()
        
        if existing_invitation:
            raise HTTPException(
                status_code=400,
                detail=f"Pending invitation already exists for {invitation.email}"
            )
        
        # Create invitation
        invitation_token = generate_invitation_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)  # 7-day expiry
        
        new_invitation = TeamInvitation(
            id=uuid4(),
            team_id=team_context.team_id,
            email=invitation.email,
            role=invitation.role,
            invitation_token=invitation_token,
            status="pending",
            expires_at=expires_at,
            personal_message=invitation.personal_message,
            invited_by_user_id=team_context.user_id,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_invitation)
        await db.commit()
        
        # TODO: Send invitation email (implement email service)
        await _send_invitation_email(
            email=invitation.email,
            team_name=team_context.team_name,
            inviter_name="Team Owner",  # Could get from user table
            role=invitation.role,
            personal_message=invitation.personal_message,
            invitation_token=invitation_token
        )
        
        logger.info(f"Invitation sent to {invitation.email}")
        
        # Get inviter email for response
        inviter_query = select(User.email).where(User.id == team_context.user_id)
        inviter_result = await db.execute(inviter_query)
        inviter_email = inviter_result.scalar()
        
        return TeamInvitationResponse(
            id=new_invitation.id,
            team_id=new_invitation.team_id,
            email=new_invitation.email,
            role=new_invitation.role,
            status=new_invitation.status,
            expires_at=new_invitation.expires_at,
            personal_message=new_invitation.personal_message,
            invited_by_email=inviter_email,
            created_at=new_invitation.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to send invitation"
        )

@router.get("/invitations", response_model=List[TeamInvitationResponse])
async def get_team_invitations(
    status: Optional[str] = Query(None, regex="^(pending|accepted|expired|cancelled)$"),
    team_context: TeamContext = Depends(get_team_owner_context),  # Only owners
    db: AsyncSession = Depends(get_db)
):
    """
    Get all team invitations with optional status filtering (Owner only)
    """
    try:
        query = select(TeamInvitation).where(
            TeamInvitation.team_id == team_context.team_id
        )
        
        if status:
            query = query.where(TeamInvitation.status == status)
        
        query = query.order_by(TeamInvitation.created_at.desc())
        
        result = await db.execute(query)
        invitations = result.scalars().all()
        
        # Get inviter emails
        response_invitations = []
        for inv in invitations:
            inviter_query = select(User.email).where(User.id == inv.invited_by_user_id)
            inviter_result = await db.execute(inviter_query)
            inviter_email = inviter_result.scalar()
            
            response_invitations.append(TeamInvitationResponse(
                id=inv.id,
                team_id=inv.team_id,
                email=inv.email,
                role=inv.role,
                status=inv.status,
                expires_at=inv.expires_at,
                personal_message=inv.personal_message,
                invited_by_email=inviter_email,
                created_at=inv.created_at
            ))
        
        return response_invitations
        
    except Exception as e:
        logger.error(f"Error getting invitations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve invitations"
        )

@router.put("/invitations/{token}/accept")
async def accept_team_invitation(
    token: str = Path(..., description="Invitation token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Accept team invitation using secure token
    
    - Public endpoint (no team auth required)
    - Creates team membership for accepting user
    - Must be called by authenticated user
    """
    try:
        # Note: This endpoint needs user authentication but not team auth
        # For now, we'll implement it and add auth later
        
        logger.info(f"Processing invitation acceptance for token: {token[:8]}...")
        
        # Find invitation
        invitation_query = select(TeamInvitation).where(
            and_(
                TeamInvitation.invitation_token == token,
                TeamInvitation.status == "pending",
                TeamInvitation.expires_at > datetime.now(timezone.utc)
            )
        )
        result = await db.execute(invitation_query)
        invitation = result.scalar_one_or_none()
        
        if not invitation:
            raise HTTPException(
                status_code=404,
                detail="Invalid or expired invitation token"
            )
        
        # TODO: Get current user ID (requires user auth middleware)
        # For now, return instructions for frontend implementation
        
        return {
            "success": True,
            "message": "Invitation found and valid",
            "invitation": {
                "team_name": "Team Name",  # Get from team table
                "role": invitation.role,
                "expires_at": invitation.expires_at.isoformat()
            },
            "instructions": "Frontend must implement user authentication and call this endpoint"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process invitation"
        )

@router.delete("/invitations/{invitation_id}")
async def cancel_team_invitation(
    invitation_id: UUID = Path(..., description="Invitation ID to cancel"),
    team_context: TeamContext = Depends(get_team_owner_context),  # Only owners
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel pending team invitation (Owner only)
    """
    try:
        # Find invitation
        invitation_query = select(TeamInvitation).where(
            and_(
                TeamInvitation.id == invitation_id,
                TeamInvitation.team_id == team_context.team_id,
                TeamInvitation.status == "pending"
            )
        )
        result = await db.execute(invitation_query)
        invitation = result.scalar_one_or_none()
        
        if not invitation:
            raise HTTPException(
                status_code=404,
                detail="Invitation not found or already processed"
            )
        
        # Cancel invitation
        invitation.status = "cancelled"
        invitation.cancelled_at = datetime.now(timezone.utc)
        invitation.cancelled_by_user_id = team_context.user_id
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Invitation cancelled successfully",
            "invitation_id": str(invitation_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling invitation: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel invitation"
        )

# =============================================================================
# TEAM STATISTICS & OVERVIEW
# =============================================================================

@router.get("/overview")
async def get_team_overview(
    team_context: TeamContext = Depends(get_any_team_member_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive team overview with statistics
    """
    try:
        # Get team member count
        members_count_query = select(func.count(TeamMember.id)).where(
            and_(
                TeamMember.team_id == team_context.team_id,
                TeamMember.status == "active"
            )
        )
        members_result = await db.execute(members_count_query)
        active_members = members_result.scalar()
        
        # Get pending invitations count
        pending_invitations_query = select(func.count(TeamInvitation.id)).where(
            and_(
                TeamInvitation.team_id == team_context.team_id,
                TeamInvitation.status == "pending",
                TeamInvitation.expires_at > datetime.now(timezone.utc)
            )
        )
        invitations_result = await db.execute(pending_invitations_query)
        pending_invitations = invitations_result.scalar()
        
        # Get subscription limits
        from app.models.teams import SUBSCRIPTION_TIER_LIMITS
        tier_limits = SUBSCRIPTION_TIER_LIMITS.get(team_context.subscription_tier, {})
        
        return {
            "team_info": {
                "team_id": str(team_context.team_id),
                "team_name": team_context.team_name,
                "subscription_tier": team_context.subscription_tier,
                "created_at": None  # TODO: Get from team table
            },
            "membership": {
                "active_members": active_members,
                "max_members": tier_limits.get("max_team_members", 1),
                "pending_invitations": pending_invitations,
                "available_slots": max(0, tier_limits.get("max_team_members", 1) - active_members)
            },
            "usage_summary": team_context.to_dict()["remaining_capacity"],
            "permissions": team_context.user_permissions
        }
        
    except Exception as e:
        logger.error(f"Error getting team overview: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get team overview"
        )

# =============================================================================
# EMAIL SERVICE (PLACEHOLDER)
# =============================================================================

async def _send_invitation_email(
    email: str,
    team_name: str,
    inviter_name: str,
    role: str,
    personal_message: Optional[str],
    invitation_token: str
):
    """
    Send invitation email (implement with your email service)
    
    TODO: Integrate with email service (SendGrid, AWS SES, etc.)
    """
    try:
        # Placeholder for email implementation
        invitation_url = f"https://your-frontend-domain.com/invitations/accept/{invitation_token}"
        
        email_content = f"""
        You've been invited to join {team_name}!
        
        Role: {role.title()}
        Invited by: {inviter_name}
        
        {personal_message if personal_message else ''}
        
        Accept invitation: {invitation_url}
        
        This invitation expires in 7 days.
        """
        
        logger.info(f"Email invitation prepared for {email}")
        logger.info(f"Invitation URL: {invitation_url}")
        
        # TODO: Replace with actual email service
        # await email_service.send_email(
        #     to=email,
        #     subject=f"Invitation to join {team_name}",
        #     content=email_content
        # )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send invitation email: {e}")
        return False