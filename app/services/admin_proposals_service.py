"""
Admin-Brand Proposals Service - Admin creates proposals for Brands
Admin creates and manages proposals that are sent to brands for approval
No influencers are involved in this platform
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import logging
from datetime import datetime, timezone, timedelta, date

from app.database.unified_models import (
    User, AdminBrandProposal, ProposalVersion, ProposalCommunication, 
    ProposalAnalytics, ProposalTemplate
)
from app.database.connection import get_session

logger = logging.getLogger(__name__)

class AdminProposalsService:
    """Service class for Admin-Brand Proposals functionality"""
    
    async def _get_database_user_id(self, db: AsyncSession, supabase_user_id: UUID) -> UUID:
        """Convert Supabase user ID to database user ID"""
        result = await db.execute(
            text("SELECT id FROM users WHERE id::text = :user_id OR supabase_user_id::text = :user_id"), 
            {"user_id": str(supabase_user_id)}
        )
        user_row = result.fetchone()
        if not user_row:
            raise ValueError(f"User {supabase_user_id} not found in database")
        return user_row[0]
    
    async def _check_admin_permission(self, db: AsyncSession, user_id: UUID) -> bool:
        """Check if user has admin permissions"""
        result = await db.execute(
            text("""
                SELECT 1 FROM auth.users 
                WHERE id = :user_id 
                AND (raw_user_meta_data->>'role' = 'admin' 
                     OR raw_user_meta_data->>'role' = 'superadmin')
            """),
            {"user_id": str(user_id)}
        )
        return result.fetchone() is not None
    
    async def _check_proposal_access(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        proposal_id: UUID
    ) -> bool:
        """Check if user can access proposal (admin who created it or brand it was sent to)"""
        result = await db.execute(
            select(AdminBrandProposal).where(
                and_(
                    AdminBrandProposal.id == proposal_id,
                    or_(
                        AdminBrandProposal.created_by_admin_id == user_id,
                        AdminBrandProposal.brand_user_id == user_id
                    )
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    # =========================================================================
    # PROPOSAL CREATION AND MANAGEMENT
    # =========================================================================
    
    async def create_proposal(
        self,
        admin_user_id: UUID,
        brand_user_id: UUID,
        proposal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Admin creates a new proposal for a brand"""
        async with get_session() as db:
            try:
                # Verify admin permissions
                if not await self._check_admin_permission(db, admin_user_id):
                    raise ValueError("User does not have admin permissions")
                
                # Get database user IDs
                admin_id = await self._get_database_user_id(db, admin_user_id)
                brand_id = await self._get_database_user_id(db, brand_user_id)
                
                # Create proposal
                proposal = AdminBrandProposal(
                    brand_user_id=brand_id,
                    created_by_admin_id=admin_id,
                    proposal_title=proposal_data["proposal_title"],
                    proposal_description=proposal_data["proposal_description"],
                    executive_summary=proposal_data.get("executive_summary"),
                    service_type=proposal_data.get("service_type", "influencer_marketing"),
                    service_description=proposal_data["service_description"],
                    deliverables=proposal_data.get("deliverables", []),
                    proposed_start_date=proposal_data.get("proposed_start_date"),
                    proposed_end_date=proposal_data.get("proposed_end_date"),
                    estimated_duration_days=proposal_data.get("estimated_duration_days"),
                    proposed_budget_usd=proposal_data["proposed_budget_usd"],
                    budget_breakdown=proposal_data.get("budget_breakdown", {}),
                    payment_terms=proposal_data.get("payment_terms", "net_30"),
                    campaign_objectives=proposal_data.get("campaign_objectives", []),
                    target_audience_description=proposal_data.get("target_audience_description"),
                    expected_deliverables=proposal_data.get("expected_deliverables", []),
                    success_metrics=proposal_data.get("success_metrics", []),
                    expected_results=proposal_data.get("expected_results"),
                    priority_level=proposal_data.get("priority_level", "medium"),
                    admin_notes=proposal_data.get("admin_notes"),
                    tags=proposal_data.get("tags", [])
                )
                
                db.add(proposal)
                await db.commit()
                await db.refresh(proposal)
                
                # Create initial version
                await self._create_proposal_version(
                    db, proposal.id, admin_id, 1, "Initial proposal creation", proposal_data
                )
                
                logger.info(f"Admin {admin_id} created proposal {proposal.id} for brand {brand_id}")
                
                return {
                    "id": proposal.id,
                    "proposal_title": proposal.proposal_title,
                    "status": proposal.status,
                    "created_at": proposal.created_at,
                    "proposed_budget_usd": proposal.proposed_budget_usd
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error creating proposal: {e}")
                raise
    
    async def update_proposal(
        self,
        admin_user_id: UUID,
        proposal_id: UUID,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Admin updates an existing proposal"""
        async with get_session() as db:
            try:
                # Verify admin permissions and access
                admin_id = await self._get_database_user_id(db, admin_user_id)
                if not await self._check_admin_permission(db, admin_id):
                    raise ValueError("User does not have admin permissions")
                
                # Get current proposal
                result = await db.execute(
                    select(AdminBrandProposal).where(
                        and_(
                            AdminBrandProposal.id == proposal_id,
                            AdminBrandProposal.created_by_admin_id == admin_id
                        )
                    )
                )
                proposal = result.scalar_one_or_none()
                if not proposal:
                    raise ValueError("Proposal not found or access denied")
                
                # Store old data for version tracking
                old_data = {
                    "proposal_title": proposal.proposal_title,
                    "proposal_description": proposal.proposal_description,
                    "proposed_budget_usd": proposal.proposed_budget_usd,
                    "service_description": proposal.service_description
                }
                
                # Update proposal fields
                for field, value in update_data.items():
                    if hasattr(proposal, field):
                        setattr(proposal, field, value)
                
                proposal.updated_at = datetime.now(timezone.utc)
                
                await db.commit()
                await db.refresh(proposal)
                
                # Create new version if significant changes
                if any(key in update_data for key in ["proposal_title", "proposal_description", "proposed_budget_usd", "service_description"]):
                    version_number = await self._get_next_version_number(db, proposal_id)
                    changes = [f"Updated {key}" for key in update_data.keys()]
                    await self._create_proposal_version(
                        db, proposal_id, admin_id, version_number, f"Updated proposal: {', '.join(changes)}", update_data
                    )
                
                logger.info(f"Admin {admin_id} updated proposal {proposal_id}")
                
                return {
                    "id": proposal.id,
                    "proposal_title": proposal.proposal_title,
                    "status": proposal.status,
                    "updated_at": proposal.updated_at
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error updating proposal {proposal_id}: {e}")
                raise
    
    async def send_proposal_to_brand(
        self,
        admin_user_id: UUID,
        proposal_id: UUID,
        send_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send proposal to brand with notification"""
        async with get_session() as db:
            try:
                admin_id = await self._get_database_user_id(db, admin_user_id)
                if not await self._check_admin_permission(db, admin_id):
                    raise ValueError("User does not have admin permissions")
                
                # Update proposal status to sent
                result = await db.execute(
                    update(AdminBrandProposal)
                    .where(
                        and_(
                            AdminBrandProposal.id == proposal_id,
                            AdminBrandProposal.created_by_admin_id == admin_id
                        )
                    )
                    .values(
                        status='sent',
                        sent_at=datetime.now(timezone.utc),
                        brand_response_due_date=send_options.get('response_due_date') if send_options else None,
                        updated_at=datetime.now(timezone.utc)
                    )
                )
                
                if result.rowcount == 0:
                    raise ValueError("Proposal not found or access denied")
                
                # Log communication
                await self._log_communication(
                    db, proposal_id, admin_id, False, "proposal_sent",
                    "Proposal Sent", "Proposal has been sent to brand for review"
                )
                
                await db.commit()
                
                logger.info(f"Admin {admin_id} sent proposal {proposal_id} to brand")
                
                return {
                    "proposal_id": proposal_id,
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc),
                    "message": "Proposal successfully sent to brand"
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error sending proposal {proposal_id}: {e}")
                raise
    
    # =========================================================================
    # BRAND RESPONSE HANDLING
    # =========================================================================
    
    async def submit_brand_response(
        self,
        brand_user_id: UUID,
        proposal_id: UUID,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Brand submits response to proposal"""
        async with get_session() as db:
            try:
                brand_id = await self._get_database_user_id(db, brand_user_id)
                
                # Get proposal and verify access
                result = await db.execute(
                    select(AdminBrandProposal).where(
                        and_(
                            AdminBrandProposal.id == proposal_id,
                            AdminBrandProposal.brand_user_id == brand_id
                        )
                    )
                )
                proposal = result.scalar_one_or_none()
                if not proposal:
                    raise ValueError("Proposal not found or access denied")
                
                # Update proposal with brand response
                proposal.brand_decision = response_data["decision"]  # approved, rejected, counter_proposal, needs_clarification
                proposal.brand_feedback = response_data.get("feedback")
                proposal.brand_counter_proposal = response_data.get("counter_proposal", {})
                proposal.responded_at = datetime.now(timezone.utc)
                proposal.updated_at = datetime.now(timezone.utc)
                
                # Update status based on decision
                if response_data["decision"] == "approved":
                    proposal.status = "approved"
                    proposal.closed_at = datetime.now(timezone.utc)
                elif response_data["decision"] == "rejected":
                    proposal.status = "rejected"
                    proposal.closed_at = datetime.now(timezone.utc)
                elif response_data["decision"] == "counter_proposal":
                    proposal.status = "negotiation"
                else:
                    proposal.status = "under_review"
                
                # Log communication
                await self._log_communication(
                    db, proposal_id, None, True, "brand_response",
                    f"Brand Response: {response_data['decision'].title()}",
                    response_data.get("feedback", "Brand has responded to the proposal")
                )
                
                await db.commit()
                
                logger.info(f"Brand {brand_id} responded to proposal {proposal_id}: {response_data['decision']}")
                
                return {
                    "proposal_id": proposal_id,
                    "decision": response_data["decision"],
                    "status": proposal.status,
                    "responded_at": proposal.responded_at,
                    "message": "Response submitted successfully"
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error submitting brand response for proposal {proposal_id}: {e}")
                raise
    
    # =========================================================================
    # PROPOSAL RETRIEVAL
    # =========================================================================
    
    async def get_proposals_for_admin(
        self,
        admin_user_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get all proposals created by admin with filtering"""
        async with get_session() as db:
            try:
                admin_id = await self._get_database_user_id(db, admin_user_id)
                if not await self._check_admin_permission(db, admin_id):
                    raise ValueError("User does not have admin permissions")
                
                query = select(AdminBrandProposal).where(
                    AdminBrandProposal.created_by_admin_id == admin_id
                )
                
                # Apply filters
                if filters:
                    if "status" in filters:
                        query = query.where(AdminBrandProposal.status == filters["status"])
                    if "service_type" in filters:
                        query = query.where(AdminBrandProposal.service_type == filters["service_type"])
                    if "priority_level" in filters:
                        query = query.where(AdminBrandProposal.priority_level == filters["priority_level"])
                    if "min_budget" in filters:
                        query = query.where(AdminBrandProposal.proposed_budget_usd >= filters["min_budget"])
                    if "max_budget" in filters:
                        query = query.where(AdminBrandProposal.proposed_budget_usd <= filters["max_budget"])
                
                # Add ordering, limit, and offset
                query = query.order_by(AdminBrandProposal.created_at.desc()).limit(limit).offset(offset)
                
                result = await db.execute(query)
                proposals = result.scalars().all()
                
                proposals_data = []
                for proposal in proposals:
                    # Get brand user info
                    brand_result = await db.execute(
                        select(User).where(User.id == proposal.brand_user_id)
                    )
                    brand_user = brand_result.scalar_one_or_none()
                    
                    proposals_data.append({
                        "id": proposal.id,
                        "proposal_title": proposal.proposal_title,
                        "brand_user": {
                            "id": brand_user.id if brand_user else None,
                            "email": brand_user.email if brand_user else None,
                            "name": brand_user.display_name if brand_user else None
                        },
                        "service_type": proposal.service_type,
                        "proposed_budget_usd": proposal.proposed_budget_usd,
                        "status": proposal.status,
                        "priority_level": proposal.priority_level,
                        "created_at": proposal.created_at,
                        "sent_at": proposal.sent_at,
                        "responded_at": proposal.responded_at,
                        "brand_decision": proposal.brand_decision,
                        "next_follow_up_date": proposal.next_follow_up_date
                    })
                
                # Get total count for pagination
                count_result = await db.execute(
                    select(func.count(AdminBrandProposal.id)).where(
                        AdminBrandProposal.created_by_admin_id == admin_id
                    )
                )
                total_count = count_result.scalar()
                
                return {
                    "proposals": proposals_data,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
                
            except Exception as e:
                logger.error(f"Error getting proposals for admin {admin_user_id}: {e}")
                raise
    
    async def get_proposals_for_brand(
        self,
        brand_user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get all proposals sent to a brand"""
        async with get_session() as db:
            try:
                brand_id = await self._get_database_user_id(db, brand_user_id)
                
                query = (
                    select(AdminBrandProposal)
                    .where(AdminBrandProposal.brand_user_id == brand_id)
                    .order_by(AdminBrandProposal.sent_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                
                result = await db.execute(query)
                proposals = result.scalars().all()
                
                proposals_data = []
                for proposal in proposals:
                    proposals_data.append({
                        "id": proposal.id,
                        "proposal_title": proposal.proposal_title,
                        "proposal_description": proposal.proposal_description,
                        "executive_summary": proposal.executive_summary,
                        "service_type": proposal.service_type,
                        "service_description": proposal.service_description,
                        "deliverables": proposal.deliverables,
                        "proposed_budget_usd": proposal.proposed_budget_usd,
                        "budget_breakdown": proposal.budget_breakdown,
                        "payment_terms": proposal.payment_terms,
                        "proposed_start_date": proposal.proposed_start_date,
                        "proposed_end_date": proposal.proposed_end_date,
                        "expected_results": proposal.expected_results,
                        "success_metrics": proposal.success_metrics,
                        "status": proposal.status,
                        "sent_at": proposal.sent_at,
                        "brand_response_due_date": proposal.brand_response_due_date,
                        "responded_at": proposal.responded_at,
                        "brand_decision": proposal.brand_decision,
                        "brand_feedback": proposal.brand_feedback
                    })
                
                # Mark as viewed if not already
                await db.execute(
                    update(AdminBrandProposal)
                    .where(
                        and_(
                            AdminBrandProposal.brand_user_id == brand_id,
                            AdminBrandProposal.brand_viewed_at.is_(None)
                        )
                    )
                    .values(brand_viewed_at=datetime.now(timezone.utc))
                )
                await db.commit()
                
                return {
                    "proposals": proposals_data,
                    "total_count": len(proposals_data)
                }
                
            except Exception as e:
                logger.error(f"Error getting proposals for brand {brand_user_id}: {e}")
                raise
    
    # =========================================================================
    # ANALYTICS AND REPORTING
    # =========================================================================
    
    async def get_proposal_metrics(self, proposal_id: UUID) -> Dict[str, Any]:
        """Get comprehensive metrics for a specific proposal"""
        async with get_session() as db:
            try:
                # Use the database function
                result = await db.execute(
                    text("SELECT get_admin_proposal_metrics(:proposal_id)"),
                    {"proposal_id": str(proposal_id)}
                )
                metrics = result.scalar()
                
                return metrics if metrics else {}
                
            except Exception as e:
                logger.error(f"Error getting metrics for proposal {proposal_id}: {e}")
                return {}
    
    async def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get overall proposal pipeline summary"""
        async with get_session() as db:
            try:
                # Use the database function
                result = await db.execute(text("SELECT get_proposal_pipeline_summary()"))
                summary = result.scalar()
                
                return summary if summary else {}
                
            except Exception as e:
                logger.error(f"Error getting pipeline summary: {e}")
                return {}
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _create_proposal_version(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        admin_id: UUID,
        version_number: int,
        description: str,
        changes_data: Dict[str, Any]
    ) -> None:
        """Create a new proposal version"""
        version = ProposalVersion(
            proposal_id=proposal_id,
            version_number=version_number,
            version_description=description,
            created_by_admin_id=admin_id,
            proposal_data=changes_data,
            changes_made=list(changes_data.keys()),
            is_current_version=(version_number == 1)
        )
        db.add(version)
    
    async def _get_next_version_number(self, db: AsyncSession, proposal_id: UUID) -> int:
        """Get the next version number for a proposal"""
        result = await db.execute(
            select(func.max(ProposalVersion.version_number))
            .where(ProposalVersion.proposal_id == proposal_id)
        )
        max_version = result.scalar() or 0
        return max_version + 1
    
    async def _log_communication(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        sender_admin_id: Optional[UUID],
        sender_is_brand: bool,
        comm_type: str,
        subject: str,
        content: str
    ) -> None:
        """Log a communication record"""
        communication = ProposalCommunication(
            proposal_id=proposal_id,
            sender_admin_id=sender_admin_id,
            sender_is_brand=sender_is_brand,
            communication_type=comm_type,
            subject=subject,
            message_content=content
        )
        db.add(communication)


# Global service instance
admin_proposals_service = AdminProposalsService()