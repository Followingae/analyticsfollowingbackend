"""
Team Management Service - Professional B2B SaaS Team Collaboration
Handles team creation, member management, invitations, and subscription limits
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text, update
from sqlalchemy.orm import selectinload

from app.database.connection import get_session
from app.database.unified_models import (
    Team, TeamMember, TeamInvitation, EmailUnlock, 
    MonthlyUsageTracking, TopupOrder, ProposalAccessGrant
)
from app.models.teams import (
    TeamCreate, TeamUpdate, TeamResponse,
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse,
    TeamInvitationCreate, TeamInvitationResponse,
    UsageTrackingResponse, TopupOrderCreate, TopupOrderResponse
)
from app.core.exceptions import ValidationError, PermissionError
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class TeamManagementService:
    """
    Professional team management service for B2B SaaS platform
    Industry-standard team collaboration with role-based access control
    """
    
    def __init__(self):
        self.subscription_limits = {
            "free": {
                "max_team_members": 1,
                "monthly_profile_limit": 5,
                "monthly_email_limit": 0,
                "monthly_posts_limit": 0,
                "price_per_month": 0,
                "topup_discount": 0.0
            },
            "standard": {
                "max_team_members": 2,
                "monthly_profile_limit": 500,
                "monthly_email_limit": 250,
                "monthly_posts_limit": 125,
                "price_per_month": 199,
                "topup_discount": 0.0
            },
            "premium": {
                "max_team_members": 5,
                "monthly_profile_limit": 2000,
                "monthly_email_limit": 800,
                "monthly_posts_limit": 300,
                "price_per_month": 499,
                "topup_discount": 0.2  # 20% discount on topups
            }
        }
    
    # =========================================================================
    # TEAM MANAGEMENT
    # =========================================================================
    
    async def create_team(
        self, 
        owner_user_id: UUID, 
        team_data: TeamCreate, 
        subscription_tier: str = "free"
    ) -> TeamResponse:
        """Create a new team with the user as owner"""
        try:
            async with get_session() as session:
                # Get subscription limits
                limits = self.subscription_limits.get(subscription_tier, self.subscription_limits["free"])
                
                # Create team
                team = Team(
                    id=uuid4(),
                    name=team_data.name,
                    company_name=team_data.company_name,
                    subscription_tier=subscription_tier,
                    max_team_members=limits["max_team_members"],
                    monthly_profile_limit=limits["monthly_profile_limit"],
                    monthly_email_limit=limits["monthly_email_limit"],
                    monthly_posts_limit=limits["monthly_posts_limit"],
                    billing_cycle_start=date.today().replace(day=1),
                    billing_cycle_end=(date.today().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                    settings=team_data.settings or {},
                    created_by=owner_user_id
                )
                session.add(team)
                await session.flush()
                
                # Add owner as team member
                team_member = TeamMember(
                    id=uuid4(),
                    team_id=team.id,
                    user_id=owner_user_id,
                    role="owner",
                    permissions={
                        "can_invite_members": True,
                        "can_manage_team": True,
                        "can_view_billing": True,
                        "can_export_data": True,
                        "can_manage_campaigns": True,
                        "can_manage_lists": True
                    },
                    invited_by=owner_user_id,
                    invitation_accepted_at=datetime.now()
                )
                session.add(team_member)
                
                # Create initial usage tracking
                usage_tracking = MonthlyUsageTracking(
                    id=uuid4(),
                    team_id=team.id,
                    user_id=owner_user_id,
                    billing_month=date.today().replace(day=1)
                )
                session.add(usage_tracking)
                
                await session.commit()
                
                return TeamResponse(
                    id=team.id,
                    name=team.name,
                    company_name=team.company_name,
                    subscription_tier=team.subscription_tier,
                    subscription_status=team.subscription_status,
                    max_team_members=team.max_team_members,
                    monthly_profile_limit=team.monthly_profile_limit,
                    monthly_email_limit=team.monthly_email_limit,
                    monthly_posts_limit=team.monthly_posts_limit,
                    profiles_used_this_month=team.profiles_used_this_month,
                    emails_used_this_month=team.emails_used_this_month,
                    posts_used_this_month=team.posts_used_this_month,
                    member_count=1,
                    created_at=team.created_at
                )
                
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            raise ValidationError(f"Failed to create team: {str(e)}")
    
    async def get_team(self, team_id: UUID, user_id: UUID) -> Optional[TeamResponse]:
        """Get team details if user is a member"""
        try:
            async with get_session() as session:
                # Verify user is team member
                member_query = select(TeamMember).where(
                    and_(
                        TeamMember.team_id == team_id,
                        TeamMember.user_id == user_id,
                        TeamMember.status == "active"
                    )
                )
                member_result = await session.execute(member_query)
                member = member_result.scalar_one_or_none()
                
                if not member:
                    raise PermissionError("User is not a member of this team")
                
                # Get team with member count
                team_query = select(
                    Team,
                    func.count(TeamMember.id).label("member_count")
                ).select_from(
                    Team.join(TeamMember, Team.id == TeamMember.team_id)
                ).where(
                    and_(
                        Team.id == team_id,
                        TeamMember.status == "active"
                    )
                ).group_by(Team.id)
                
                result = await session.execute(team_query)
                team_row = result.first()
                
                if not team_row:
                    return None
                
                team, member_count = team_row
                
                return TeamResponse(
                    id=team.id,
                    name=team.name,
                    company_name=team.company_name,
                    subscription_tier=team.subscription_tier,
                    subscription_status=team.subscription_status,
                    subscription_expires_at=team.subscription_expires_at,
                    max_team_members=team.max_team_members,
                    monthly_profile_limit=team.monthly_profile_limit,
                    monthly_email_limit=team.monthly_email_limit,
                    monthly_posts_limit=team.monthly_posts_limit,
                    profiles_used_this_month=team.profiles_used_this_month,
                    emails_used_this_month=team.emails_used_this_month,
                    posts_used_this_month=team.posts_used_this_month,
                    member_count=member_count,
                    created_at=team.created_at,
                    updated_at=team.updated_at
                )
                
        except Exception as e:
            logger.error(f"Error getting team {team_id}: {e}")
            return None
    
    # =========================================================================
    # TEAM MEMBER MANAGEMENT
    # =========================================================================
    
    async def invite_team_member(
        self, 
        team_id: UUID, 
        inviter_user_id: UUID, 
        invitation_data: TeamInvitationCreate
    ) -> TeamInvitationResponse:
        """Send team member invitation"""
        try:
            async with get_session() as session:
                # Check if inviter has permission
                inviter_query = select(TeamMember).where(
                    and_(
                        TeamMember.team_id == team_id,
                        TeamMember.user_id == inviter_user_id,
                        TeamMember.role.in_(["owner", "admin"]),
                        TeamMember.status == "active"
                    )
                )
                inviter = await session.execute(inviter_query)
                if not inviter.scalar_one_or_none():
                    raise PermissionError("User does not have permission to invite team members")
                
                # Check team member limits
                team_query = select(Team).where(Team.id == team_id)
                team_result = await session.execute(team_query)
                team = team_result.scalar_one_or_none()
                
                if not team:
                    raise ValidationError("Team not found")
                
                current_members_query = select(func.count(TeamMember.id)).where(
                    and_(TeamMember.team_id == team_id, TeamMember.status == "active")
                )
                current_members_result = await session.execute(current_members_query)
                current_members = current_members_result.scalar()
                
                if current_members >= team.max_team_members:
                    raise ValidationError(
                        f"Team has reached maximum member limit ({team.max_team_members}). "
                        f"Upgrade subscription to add more members."
                    )
                
                # Check for existing invitation
                existing_invitation_query = select(TeamInvitation).where(
                    and_(
                        TeamInvitation.team_id == team_id,
                        TeamInvitation.email == invitation_data.email,
                        TeamInvitation.status == "pending"
                    )
                )
                existing = await session.execute(existing_invitation_query)
                if existing.scalar_one_or_none():
                    raise ValidationError("Invitation already sent to this email")
                
                # Create invitation
                invitation_token = str(uuid4())
                expires_at = datetime.now() + timedelta(days=7)  # 7 days to accept
                
                invitation = TeamInvitation(
                    id=uuid4(),
                    team_id=team_id,
                    email=invitation_data.email,
                    role=invitation_data.role,
                    invited_by=inviter_user_id,
                    invitation_token=invitation_token,
                    expires_at=expires_at,
                    personal_message=invitation_data.personal_message
                )
                session.add(invitation)
                await session.commit()
                
                # Send invitation email (async)
                await email_service.send_team_invitation(
                    recipient_email=invitation_data.email,
                    team_name=team.name,
                    inviter_name="Team Admin",  # Would get from user profile
                    invitation_link=f"https://app.analyticsfollowing.com/invite/{invitation_token}",
                    personal_message=invitation_data.personal_message
                )
                
                return TeamInvitationResponse(
                    id=invitation.id,
                    team_id=invitation.team_id,
                    email=invitation.email,
                    role=invitation.role,
                    status=invitation.status,
                    expires_at=invitation.expires_at,
                    created_at=invitation.created_at
                )
                
        except Exception as e:
            logger.error(f"Error inviting team member: {e}")
            raise ValidationError(f"Failed to send invitation: {str(e)}")
    
    async def accept_team_invitation(
        self, 
        invitation_token: str, 
        accepting_user_id: UUID
    ) -> TeamMemberResponse:
        """Accept team invitation and add user as team member"""
        try:
            async with get_session() as session:
                # Get invitation
                invitation_query = select(TeamInvitation).where(
                    and_(
                        TeamInvitation.invitation_token == invitation_token,
                        TeamInvitation.status == "pending",
                        TeamInvitation.expires_at > datetime.now()
                    )
                )
                invitation_result = await session.execute(invitation_query)
                invitation = invitation_result.scalar_one_or_none()
                
                if not invitation:
                    raise ValidationError("Invalid or expired invitation")
                
                # Check if user is already a team member
                existing_member_query = select(TeamMember).where(
                    and_(
                        TeamMember.team_id == invitation.team_id,
                        TeamMember.user_id == accepting_user_id
                    )
                )
                existing = await session.execute(existing_member_query)
                if existing.scalar_one_or_none():
                    raise ValidationError("User is already a team member")
                
                # Create team member
                permissions = self._get_role_permissions(invitation.role)
                team_member = TeamMember(
                    id=uuid4(),
                    team_id=invitation.team_id,
                    user_id=accepting_user_id,
                    role=invitation.role,
                    permissions=permissions,
                    invited_by=invitation.invited_by,
                    invitation_accepted_at=datetime.now()
                )
                session.add(team_member)
                
                # Create usage tracking for new member
                usage_tracking = MonthlyUsageTracking(
                    id=uuid4(),
                    team_id=invitation.team_id,
                    user_id=accepting_user_id,
                    billing_month=date.today().replace(day=1)
                )
                session.add(usage_tracking)
                
                # Update invitation status
                invitation.status = "accepted"
                invitation.accepted_at = datetime.now()
                invitation.accepted_by = accepting_user_id
                
                await session.commit()
                
                return TeamMemberResponse(
                    id=team_member.id,
                    team_id=team_member.team_id,
                    user_id=team_member.user_id,
                    role=team_member.role,
                    permissions=team_member.permissions,
                    status=team_member.status,
                    joined_at=team_member.joined_at,
                    created_at=team_member.created_at
                )
                
        except Exception as e:
            logger.error(f"Error accepting invitation: {e}")
            raise ValidationError(f"Failed to accept invitation: {str(e)}")
    
    def _get_role_permissions(self, role: str) -> Dict[str, bool]:
        """Get default permissions for team role"""
        permissions = {
            "owner": {
                "can_invite_members": True,
                "can_remove_members": True,
                "can_manage_team": True,
                "can_view_billing": True,
                "can_purchase_topups": True,
                "can_export_data": True,
                "can_manage_campaigns": True,
                "can_manage_lists": True,
                "can_view_usage": True
            },
            "admin": {
                "can_invite_members": True,
                "can_remove_members": True,
                "can_manage_team": False,
                "can_view_billing": True,
                "can_purchase_topups": True,
                "can_export_data": True,
                "can_manage_campaigns": True,
                "can_manage_lists": True,
                "can_view_usage": True
            },
            "manager": {
                "can_invite_members": False,
                "can_remove_members": False,
                "can_manage_team": False,
                "can_view_billing": False,
                "can_purchase_topups": False,
                "can_export_data": True,
                "can_manage_campaigns": True,
                "can_manage_lists": True,
                "can_view_usage": True
            },
            "member": {
                "can_invite_members": False,
                "can_remove_members": False,
                "can_manage_team": False,
                "can_view_billing": False,
                "can_purchase_topups": False,
                "can_export_data": False,
                "can_manage_campaigns": False,
                "can_manage_lists": False,
                "can_view_usage": False
            }
        }
        return permissions.get(role, permissions["member"])
    
    # =========================================================================
    # USAGE TRACKING & LIMITS
    # =========================================================================
    
    async def check_usage_limits(
        self, 
        team_id: UUID, 
        action_type: str, 
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Check if team can perform action within subscription limits"""
        try:
            async with get_session() as session:
                # Get team limits
                team_query = select(Team).where(Team.id == team_id)
                team_result = await session.execute(team_query)
                team = team_result.scalar_one_or_none()
                
                if not team:
                    return {"allowed": False, "reason": "Team not found"}
                
                # Get current month usage
                current_month = date.today().replace(day=1)
                
                # Check specific limits
                if action_type == "profile_analysis":
                    if team.profiles_used_this_month + quantity > team.monthly_profile_limit:
                        return {
                            "allowed": False,
                            "reason": "Monthly profile analysis limit exceeded",
                            "current_usage": team.profiles_used_this_month,
                            "limit": team.monthly_profile_limit,
                            "available": team.monthly_profile_limit - team.profiles_used_this_month
                        }
                
                elif action_type == "email_unlock":
                    if team.emails_used_this_month + quantity > team.monthly_email_limit:
                        return {
                            "allowed": False,
                            "reason": "Monthly email unlock limit exceeded",
                            "current_usage": team.emails_used_this_month,
                            "limit": team.monthly_email_limit,
                            "available": team.monthly_email_limit - team.emails_used_this_month
                        }
                
                elif action_type == "post_analytics":
                    if team.posts_used_this_month + quantity > team.monthly_posts_limit:
                        return {
                            "allowed": False,
                            "reason": "Monthly post analytics limit exceeded",
                            "current_usage": team.posts_used_this_month,
                            "limit": team.monthly_posts_limit,
                            "available": team.monthly_posts_limit - team.posts_used_this_month
                        }
                
                return {"allowed": True}
                
        except Exception as e:
            logger.error(f"Error checking usage limits: {e}")
            return {"allowed": False, "reason": "Error checking limits"}
    
    async def record_usage(
        self, 
        team_id: UUID, 
        user_id: UUID, 
        action_type: str, 
        quantity: int = 1
    ) -> bool:
        """Record usage for team and update counters"""
        try:
            async with get_session() as session:
                current_month = date.today().replace(day=1)
                
                # Update or create usage tracking
                usage_query = select(MonthlyUsageTracking).where(
                    and_(
                        MonthlyUsageTracking.team_id == team_id,
                        MonthlyUsageTracking.user_id == user_id,
                        MonthlyUsageTracking.billing_month == current_month
                    )
                )
                usage_result = await session.execute(usage_query)
                usage = usage_result.scalar_one_or_none()
                
                if not usage:
                    usage = MonthlyUsageTracking(
                        id=uuid4(),
                        team_id=team_id,
                        user_id=user_id,
                        billing_month=current_month
                    )
                    session.add(usage)
                
                # Update usage counters
                if action_type == "profile_analysis":
                    usage.profiles_analyzed += quantity
                elif action_type == "email_unlock":
                    usage.emails_unlocked += quantity
                elif action_type == "post_analytics":
                    usage.posts_analyzed += quantity
                
                usage.updated_at = datetime.now()
                
                # Trigger will automatically update team-level counters
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error recording usage: {e}")
            return False


# Global service instance
team_management_service = TeamManagementService()