"""
Campaign Proposals Service - Superadmin → User Proposal Management
Handles proposal creation, influencer selection, approval/rejection workflow
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.database.unified_models import (
    CampaignProposal, ProposalInfluencer, Campaign, Profile, User
)

logger = logging.getLogger(__name__)


class CampaignProposalsService:
    """Service for managing campaign proposals from superadmin to users"""

    # =============================================================================
    # PROPOSAL CRUD OPERATIONS (Superadmin)
    # =============================================================================

    async def create_proposal(
        self,
        db: AsyncSession,
        user_id: UUID,  # Target user
        created_by_admin_id: UUID,  # Superadmin creating proposal
        title: str,
        campaign_name: str,
        description: Optional[str] = None,
        proposal_notes: Optional[str] = None,
        total_budget: Optional[float] = None,
        proposal_type: str = 'influencer_list'
    ) -> CampaignProposal:
        """
        Create a new campaign proposal (Superadmin only)

        Args:
            db: Database session
            user_id: Target user receiving the proposal
            created_by_admin_id: Superadmin creating the proposal
            title: Proposal title
            campaign_name: Proposed campaign name
            description: Proposal description
            proposal_notes: Notes from superadmin to user
            total_budget: Total proposed budget
            proposal_type: influencer_list or campaign_package

        Returns:
            Created CampaignProposal object
        """
        try:
            proposal = CampaignProposal(
                user_id=user_id,
                created_by_admin_id=created_by_admin_id,
                title=title,
                campaign_name=campaign_name,
                description=description,
                proposal_notes=proposal_notes,
                total_budget=total_budget,
                proposal_type=proposal_type,
                status='draft'
            )

            db.add(proposal)
            await db.commit()
            await db.refresh(proposal)

            logger.info(f"✅ Created proposal '{title}' for user {user_id} by admin {created_by_admin_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to create proposal: {e}")
            raise

    async def add_influencers_to_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        influencer_data: List[Dict[str, Any]]
    ) -> List[ProposalInfluencer]:
        """
        Add suggested influencers to a proposal

        Args:
            db: Database session
            proposal_id: Proposal ID
            influencer_data: List of dicts with profile_id, estimated_cost

        Returns:
            List of created ProposalInfluencer objects
        """
        try:
            proposal_influencers = []

            for data in influencer_data:
                proposal_influencer = ProposalInfluencer(
                    proposal_id=proposal_id,
                    profile_id=data['profile_id'],
                    estimated_cost=data.get('estimated_cost'),
                    suggested_by_admin=True,
                    selected_by_user=False
                )
                db.add(proposal_influencer)
                proposal_influencers.append(proposal_influencer)

            await db.commit()

            logger.info(f"✅ Added {len(proposal_influencers)} influencers to proposal {proposal_id}")
            return proposal_influencers

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to add influencers to proposal: {e}")
            raise

    async def send_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID
    ) -> CampaignProposal:
        """
        Send proposal to user (change status to 'sent')

        Args:
            db: Database session
            proposal_id: Proposal ID

        Returns:
            Updated CampaignProposal object
        """
        try:
            result = await db.execute(
                select(CampaignProposal).where(CampaignProposal.id == proposal_id)
            )
            proposal = result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            proposal.status = 'sent'
            proposal.sent_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(proposal)

            logger.info(f"✅ Sent proposal {proposal_id} to user {proposal.user_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to send proposal: {e}")
            raise

    # =============================================================================
    # PROPOSAL LISTING (User View)
    # =============================================================================

    async def list_user_proposals(
        self,
        db: AsyncSession,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CampaignProposal]:
        """
        List proposals for a user

        Args:
            db: Database session
            user_id: User ID
            status: Optional status filter
            limit: Results limit
            offset: Pagination offset

        Returns:
            List of CampaignProposal objects
        """
        try:
            query = select(CampaignProposal).where(
                CampaignProposal.user_id == user_id
            )

            if status:
                query = query.where(CampaignProposal.status == status)

            query = query.order_by(desc(CampaignProposal.created_at))
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            proposals = result.scalars().all()

            logger.info(f"✅ Retrieved {len(proposals)} proposals for user {user_id}")
            return proposals

        except Exception as e:
            logger.error(f"❌ Failed to list proposals: {e}")
            raise

    async def get_proposal_details(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID
    ) -> Optional[CampaignProposal]:
        """
        Get proposal details with suggested influencers

        Args:
            db: Database session
            proposal_id: Proposal ID
            user_id: User requesting the proposal

        Returns:
            CampaignProposal object with influencers loaded
        """
        try:
            result = await db.execute(
                select(CampaignProposal)
                .where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id
                ))
                .options(
                    selectinload(CampaignProposal.proposal_influencers)
                    .selectinload(ProposalInfluencer.profile)
                )
            )
            proposal = result.scalar_one_or_none()

            if proposal:
                logger.info(f"✅ Retrieved proposal {proposal_id} for user {user_id}")
            else:
                logger.warning(f"⚠️ Proposal {proposal_id} not found or unauthorized for user {user_id}")

            return proposal

        except Exception as e:
            logger.error(f"❌ Failed to get proposal details: {e}")
            raise

    # =============================================================================
    # INFLUENCER SELECTION (User Actions)
    # =============================================================================

    async def update_influencer_selection(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        selected_profile_ids: List[UUID]
    ) -> CampaignProposal:
        """
        User selects/deselects influencers from proposal

        Args:
            db: Database session
            proposal_id: Proposal ID
            user_id: User making the selection
            selected_profile_ids: List of profile IDs user selected

        Returns:
            Updated CampaignProposal object
        """
        try:
            # Verify ownership
            result = await db.execute(
                select(CampaignProposal).where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id
                ))
            )
            proposal = result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found or unauthorized")

            # Get all proposal influencers
            result = await db.execute(
                select(ProposalInfluencer).where(
                    ProposalInfluencer.proposal_id == proposal_id
                )
            )
            proposal_influencers = result.scalars().all()

            # Update selection status
            for pi in proposal_influencers:
                if pi.profile_id in selected_profile_ids:
                    pi.selected_by_user = True
                    pi.selected_at = datetime.now(timezone.utc)
                else:
                    pi.selected_by_user = False
                    pi.selected_at = None

            # Update proposal status to 'in_review'
            if proposal.status == 'sent':
                proposal.status = 'in_review'

            await db.commit()
            await db.refresh(proposal)

            logger.info(f"✅ Updated influencer selection for proposal {proposal_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to update influencer selection: {e}")
            raise

    # =============================================================================
    # PROPOSAL APPROVAL/REJECTION (User Actions)
    # =============================================================================

    async def approve_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        selected_profile_ids: List[UUID],
        notes: Optional[str] = None
    ) -> Campaign:
        """
        User approves proposal and creates campaign

        Args:
            db: Database session
            proposal_id: Proposal ID
            user_id: User approving the proposal
            selected_profile_ids: Final selected profile IDs
            notes: Optional notes from user

        Returns:
            Created Campaign object
        """
        try:
            # Get proposal
            result = await db.execute(
                select(CampaignProposal)
                .where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id
                ))
                .options(selectinload(CampaignProposal.proposal_influencers))
            )
            proposal = result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found or unauthorized")

            # Create campaign from proposal
            campaign = Campaign(
                user_id=user_id,
                name=proposal.campaign_name,
                description=proposal.description,
                brand_name=proposal.campaign_name,  # Can be customized
                budget=proposal.total_budget,
                status='active',
                created_by='superadmin',
                proposal_id=proposal_id
            )

            db.add(campaign)

            # Update proposal status
            proposal.status = 'approved'
            proposal.responded_at = datetime.now(timezone.utc)

            # Update final influencer selections
            for pi in proposal.proposal_influencers:
                if pi.profile_id in selected_profile_ids:
                    pi.selected_by_user = True
                    pi.selected_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(campaign)

            logger.info(f"✅ Approved proposal {proposal_id} and created campaign {campaign.id}")
            return campaign

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to approve proposal: {e}")
            raise

    async def reject_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> CampaignProposal:
        """
        User rejects proposal

        Args:
            db: Database session
            proposal_id: Proposal ID
            user_id: User rejecting the proposal
            reason: Optional rejection reason

        Returns:
            Updated CampaignProposal object
        """
        try:
            result = await db.execute(
                select(CampaignProposal).where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id
                ))
            )
            proposal = result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found or unauthorized")

            proposal.status = 'rejected'
            proposal.responded_at = datetime.now(timezone.utc)
            proposal.rejection_reason = reason

            await db.commit()
            await db.refresh(proposal)

            logger.info(f"✅ Rejected proposal {proposal_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Failed to reject proposal: {e}")
            raise

    # =============================================================================
    # PROPOSAL STATISTICS
    # =============================================================================

    async def count_pending_proposals(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """
        Count pending proposals for a user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Count of proposals with status 'sent' or 'in_review'
        """
        try:
            result = await db.execute(
                select(func.count(CampaignProposal.id))
                .where(and_(
                    CampaignProposal.user_id == user_id,
                    CampaignProposal.status.in_(['sent', 'in_review'])
                ))
            )
            count = result.scalar()

            return count or 0

        except Exception as e:
            logger.error(f"❌ Failed to count pending proposals: {e}")
            return 0


# Global service instance
campaign_proposals_service = CampaignProposalsService()
