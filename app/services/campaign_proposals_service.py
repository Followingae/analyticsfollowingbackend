"""
Campaign Proposals Service - Superadmin → User Proposal Management
Handles proposal creation, influencer selection, approval/rejection workflow,
pricing snapshots from master DB, request-more flow, and financial breakdowns.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal
from sqlalchemy import select, func, and_, desc, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.database.unified_models import (
    CampaignProposal, ProposalInfluencer, Campaign, CampaignCreator, Profile,
    User, InfluencerDatabase,
)

logger = logging.getLogger(__name__)


def _cents_to_dollars(cents: Optional[int]) -> Optional[float]:
    """Convert USD cents to dollars."""
    if cents is None:
        return None
    return round(cents / 100.0, 2)


def _snapshot_pricing(inf: InfluencerDatabase) -> Tuple[Dict, Dict]:
    """Build sell and cost price snapshot dicts from an InfluencerDatabase row."""
    sell = {
        "post": _cents_to_dollars(inf.sell_post_usd_cents),
        "story": _cents_to_dollars(inf.sell_story_usd_cents),
        "reel": _cents_to_dollars(inf.sell_reel_usd_cents),
        "carousel": _cents_to_dollars(inf.sell_carousel_usd_cents),
        "video": _cents_to_dollars(inf.sell_video_usd_cents),
        "bundle": _cents_to_dollars(inf.sell_bundle_usd_cents),
        "monthly": _cents_to_dollars(inf.sell_monthly_usd_cents),
    }
    cost = {
        "post": _cents_to_dollars(inf.cost_post_usd_cents),
        "story": _cents_to_dollars(inf.cost_story_usd_cents),
        "reel": _cents_to_dollars(inf.cost_reel_usd_cents),
        "carousel": _cents_to_dollars(inf.cost_carousel_usd_cents),
        "video": _cents_to_dollars(inf.cost_video_usd_cents),
        "bundle": _cents_to_dollars(inf.cost_bundle_usd_cents),
        "monthly": _cents_to_dollars(inf.cost_monthly_usd_cents),
    }
    return sell, cost


class CampaignProposalsService:
    """Service for managing campaign proposals from superadmin to users"""

    # =============================================================================
    # PROPOSAL CRUD OPERATIONS (Superadmin)
    # =============================================================================

    async def create_proposal(
        self,
        db: AsyncSession,
        user_id: UUID,
        created_by_admin_id: UUID,
        title: str,
        campaign_name: str,
        description: Optional[str] = None,
        proposal_notes: Optional[str] = None,
        total_budget: Optional[float] = None,
        proposal_type: str = 'influencer_list',
        visible_fields: Optional[Dict] = None,
        deadline_at: Optional[datetime] = None,
        cover_image_url: Optional[str] = None,
    ) -> CampaignProposal:
        """Create a new campaign proposal (Superadmin only)."""
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
                status='draft',
                deadline_at=deadline_at,
                cover_image_url=cover_image_url,
            )
            if visible_fields:
                proposal.visible_fields = visible_fields

            db.add(proposal)
            await db.commit()
            await db.refresh(proposal)

            logger.info(f"Created proposal '{title}' for user {user_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create proposal: {e}")
            raise

    async def update_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        **kwargs,
    ) -> CampaignProposal:
        """Update proposal fields (admin only). Only mutable in draft/more_requested."""
        result = await db.execute(
            select(CampaignProposal).where(CampaignProposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # H1: Status guard — cannot mutate approved/rejected/sent proposals
        if proposal.status not in ('draft', 'more_requested'):
            raise ValueError(f"Cannot update proposal in '{proposal.status}' status. Must be 'draft' or 'more_requested'.")

        allowed = {
            'title', 'campaign_name', 'description', 'proposal_notes',
            'visible_fields', 'deadline_at', 'cover_image_url', 'total_budget',
        }
        # H2: Allow clearing nullable fields (val may be None intentionally)
        for key, val in kwargs.items():
            if key in allowed:
                setattr(proposal, key, val)

        await db.commit()
        await db.refresh(proposal)
        return proposal

    # =============================================================================
    # ADD INFLUENCERS FROM MASTER DB (Superadmin)
    # =============================================================================

    async def add_influencers_from_db(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        influencer_db_ids: List[UUID],
        custom_pricing: Optional[Dict[str, Dict]] = None,
        deliverable_assignments: Optional[Dict[UUID, List[Dict]]] = None,
        _commit: bool = True,
    ) -> List[ProposalInfluencer]:
        """
        Add influencers from master DB to proposal with price snapshots.

        Args:
            proposal_id: Target proposal
            influencer_db_ids: List of InfluencerDatabase IDs
            custom_pricing: Optional dict of {influencer_db_id: {post: X, ...}} overrides
            _commit: If False, only flush (caller manages commit). Used for atomicity.
        """
        try:
            # Verify proposal exists
            prop_result = await db.execute(
                select(CampaignProposal).where(CampaignProposal.id == proposal_id)
            )
            proposal = prop_result.scalar_one_or_none()
            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            # Fetch influencer DB entries
            inf_result = await db.execute(
                select(InfluencerDatabase).where(
                    InfluencerDatabase.id.in_(influencer_db_ids)
                )
            )
            influencers = {inf.id: inf for inf in inf_result.scalars().all()}

            # M7: Check for duplicate influencers already in proposal
            existing_result = await db.execute(
                select(ProposalInfluencer.influencer_db_id).where(
                    ProposalInfluencer.proposal_id == proposal_id
                )
            )
            existing_db_ids = {row[0] for row in existing_result.fetchall() if row[0]}

            # Get existing max priority
            max_p = await db.execute(
                select(func.coalesce(func.max(ProposalInfluencer.priority_order), 0))
                .where(ProposalInfluencer.proposal_id == proposal_id)
            )
            next_priority = (max_p.scalar() or 0) + 1

            # Try to match usernames to profiles
            usernames = [inf.username for inf in influencers.values() if inf.username]
            profile_map = {}
            if usernames:
                prof_result = await db.execute(
                    select(Profile).where(Profile.username.in_(usernames))
                )
                profile_map = {p.username: p.id for p in prof_result.scalars().all()}

            created = []
            for db_id in influencer_db_ids:
                inf = influencers.get(db_id)
                if not inf:
                    logger.warning(f"Influencer DB {db_id} not found, skipping")
                    continue

                # M7: Skip duplicates
                if db_id in existing_db_ids:
                    logger.warning(f"Influencer DB {db_id} already in proposal, skipping")
                    continue

                sell_snap, cost_snap = _snapshot_pricing(inf)
                custom = None
                if custom_pricing and str(db_id) in custom_pricing:
                    custom = custom_pricing[str(db_id)]

                # Get assigned deliverables for this influencer
                assigned = []
                if deliverable_assignments and db_id in deliverable_assignments:
                    assigned = deliverable_assignments[db_id]

                pi = ProposalInfluencer(
                    proposal_id=proposal_id,
                    influencer_db_id=db_id,
                    profile_id=profile_map.get(inf.username),
                    sell_price_snapshot=sell_snap,
                    cost_price_snapshot=cost_snap,
                    custom_sell_pricing=custom,
                    assigned_deliverables=assigned,
                    suggested_by_admin=True,
                    priority_order=next_priority,
                )
                db.add(pi)
                created.append(pi)
                next_priority += 1

            await db.flush()

            # Recalculate proposal financials
            await self._recalculate_financials(db, proposal)

            if _commit:
                await db.commit()
            logger.info(f"Added {len(created)} influencers to proposal {proposal_id}")
            return created

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to add influencers from DB: {e}")
            raise

    async def add_influencers_to_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        influencer_data: List[Dict[str, Any]]
    ) -> List[ProposalInfluencer]:
        """Legacy: Add influencers by profile_id."""
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
            logger.info(f"Added {len(proposal_influencers)} influencers to proposal {proposal_id}")
            return proposal_influencers

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to add influencers to proposal: {e}")
            raise

    async def remove_influencer_from_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        influencer_id: UUID,
    ) -> bool:
        """Remove a ProposalInfluencer by its ID. Only in draft/more_requested."""
        # H3: Status guard
        prop_result = await db.execute(
            select(CampaignProposal).where(CampaignProposal.id == proposal_id)
        )
        proposal = prop_result.scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status not in ('draft', 'more_requested'):
            raise ValueError(f"Cannot remove influencer in '{proposal.status}' status.")

        result = await db.execute(
            select(ProposalInfluencer).where(and_(
                ProposalInfluencer.id == influencer_id,
                ProposalInfluencer.proposal_id == proposal_id,
            ))
        )
        pi = result.scalar_one_or_none()
        if not pi:
            raise ValueError("Influencer not found in proposal")

        await db.delete(pi)
        await self._recalculate_financials(db, proposal)
        await db.commit()
        return True

    # =============================================================================
    # SEND / STATUS TRANSITIONS
    # =============================================================================

    async def send_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID
    ) -> CampaignProposal:
        """Send proposal to user (status → sent). Only from draft or more_requested."""
        try:
            result = await db.execute(
                select(CampaignProposal).where(CampaignProposal.id == proposal_id)
            )
            proposal = result.scalar_one_or_none()
            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            if proposal.status not in ('draft', 'more_requested'):
                raise ValueError(f"Cannot send proposal in '{proposal.status}' status. Must be 'draft' or 'more_requested'.")

            proposal.status = 'sent'
            proposal.sent_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(proposal)

            # Send notification
            try:
                from app.services.notification_service import NotificationService
                from sqlalchemy import text as sa_text
                email_result = await db.execute(
                    sa_text("SELECT email FROM users WHERE id = CAST(:uid AS uuid)"),
                    {"uid": str(proposal.user_id)},
                )
                email_row = email_result.fetchone()
                if email_row:
                    await NotificationService.notify_proposal_received(
                        db,
                        user_id=proposal.user_id,
                        user_email=email_row[0],
                        proposal_id=proposal.id,
                        proposal_title=proposal.title,
                        campaign_name=proposal.campaign_name,
                    )
                else:
                    logger.warning(f"No email found for user {proposal.user_id} — proposal notification skipped")
            except Exception as notify_err:
                logger.warning(f"Failed to send proposal notification: {notify_err}")

            logger.info(f"Sent proposal {proposal_id} to user {proposal.user_id}")
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to send proposal: {e}")
            raise

    async def handle_request_more(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        notes: Optional[str] = None,
    ) -> CampaignProposal:
        """Brand requests more influencers (status → more_requested). Only from sent or in_review."""
        try:
            result = await db.execute(
                select(CampaignProposal).where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id,
                ))
            )
            proposal = result.scalar_one_or_none()
            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found or unauthorized")

            if proposal.status not in ('sent', 'in_review'):
                raise ValueError(f"Cannot request more in '{proposal.status}' status. Must be 'sent' or 'in_review'.")

            proposal.status = 'more_requested'
            proposal.request_more_notes = notes
            proposal.request_more_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(proposal)

            # Notify admin
            try:
                from app.services.notification_service import NotificationService
                if proposal.created_by_admin_id:
                    await NotificationService.notify_more_requested(
                        db,
                        admin_id=proposal.created_by_admin_id,
                        proposal_id=proposal.id,
                        proposal_title=proposal.title,
                        brand_notes=notes,
                    )
            except Exception as e:
                logger.warning(f"Failed to send more_requested notification: {e}")

            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to handle request more: {e}")
            raise

    async def add_more_influencers(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        influencer_db_ids: List[UUID],
        custom_pricing: Optional[Dict[str, Dict]] = None,
        deliverable_assignments: Optional[Dict[UUID, List[Dict]]] = None,
    ) -> List[ProposalInfluencer]:
        """Admin adds more influencers after brand request. Status → sent.
        C2: Atomic — uses _commit=False in add_influencers_from_db, single commit here.
        """
        try:
            # C2: Status guard for add-more
            prop_result = await db.execute(
                select(CampaignProposal).where(CampaignProposal.id == proposal_id)
            )
            proposal = prop_result.scalar_one_or_none()
            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")
            if proposal.status not in ('more_requested', 'sent', 'draft'):
                raise ValueError(f"Cannot add more influencers in '{proposal.status}' status.")

            # C2: Pass _commit=False so add_influencers_from_db only flushes
            created = await self.add_influencers_from_db(
                db, proposal_id, influencer_db_ids, custom_pricing,
                deliverable_assignments=deliverable_assignments, _commit=False
            )

            # Update proposal status back to sent
            proposal.status = 'sent'
            proposal.more_added_at = datetime.now(timezone.utc)

            # Single atomic commit
            await db.commit()

            # Notify brand
            try:
                from app.services.notification_service import NotificationService
                from sqlalchemy import text as sa_text
                email_result = await db.execute(
                    sa_text("SELECT email FROM users WHERE id = CAST(:uid AS uuid)"),
                    {"uid": str(proposal.user_id)},
                )
                email_row = email_result.fetchone()
                if email_row:
                    await NotificationService.notify_more_added(
                        db,
                        user_id=proposal.user_id,
                        user_email=email_row[0],
                        proposal_id=proposal.id,
                        proposal_title=proposal.title,
                        count_added=len(created),
                    )
                else:
                    logger.warning(f"No email found for user {proposal.user_id} — more_added notification skipped")
            except Exception as e:
                logger.warning(f"Failed to send more_added notification: {e}")

            return created

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to add more influencers: {e}")
            raise

    # =============================================================================
    # PROPOSAL LISTING
    # =============================================================================

    async def list_user_proposals(
        self,
        db: AsyncSession,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[CampaignProposal], int]:
        """List proposals for a user. Returns (proposals, total_count).
        M2: Brands never see draft proposals (admin hasn't sent yet).
        """
        try:
            base_filter = and_(
                CampaignProposal.user_id == user_id,
                CampaignProposal.status != 'draft',
            )
            query = select(CampaignProposal).where(base_filter)
            count_query = select(func.count(CampaignProposal.id)).where(base_filter)

            if status:
                query = query.where(CampaignProposal.status == status)
                count_query = count_query.where(CampaignProposal.status == status)

            query = query.options(
                selectinload(CampaignProposal.proposal_influencers),
            )
            query = query.order_by(desc(CampaignProposal.created_at))
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            proposals = list(result.scalars().all())

            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            return proposals, total

        except Exception as e:
            logger.error(f"Failed to list proposals: {e}")
            raise

    async def list_all_proposals(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        user_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CampaignProposal], int]:
        """List all proposals (admin). Returns (proposals, total_count)."""
        query = select(CampaignProposal)
        count_query = select(func.count(CampaignProposal.id))

        if status:
            query = query.where(CampaignProposal.status == status)
            count_query = count_query.where(CampaignProposal.status == status)
        if user_id:
            query = query.where(CampaignProposal.user_id == user_id)
            count_query = count_query.where(CampaignProposal.user_id == user_id)

        query = query.options(
            selectinload(CampaignProposal.user),
            selectinload(CampaignProposal.proposal_influencers),
        )
        query = query.order_by(desc(CampaignProposal.created_at))
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        proposals = list(result.scalars().all())

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        return proposals, total

    # =============================================================================
    # PROPOSAL DETAILS
    # =============================================================================

    async def get_proposal_details(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID
    ) -> Optional[CampaignProposal]:
        """Get proposal details with influencers (user view)."""
        try:
            result = await db.execute(
                select(CampaignProposal)
                .where(and_(
                    CampaignProposal.id == proposal_id,
                    CampaignProposal.user_id == user_id
                ))
                .options(
                    selectinload(CampaignProposal.proposal_influencers)
                    .selectinload(ProposalInfluencer.profile),
                    selectinload(CampaignProposal.proposal_influencers)
                    .selectinload(ProposalInfluencer.influencer_db),
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get proposal details: {e}")
            raise

    async def get_admin_proposal_detail(
        self,
        db: AsyncSession,
        proposal_id: UUID,
    ) -> Optional[CampaignProposal]:
        """Get full proposal details (admin view — includes cost pricing)."""
        result = await db.execute(
            select(CampaignProposal)
            .where(CampaignProposal.id == proposal_id)
            .options(
                selectinload(CampaignProposal.user),
                selectinload(CampaignProposal.proposal_influencers)
                .selectinload(ProposalInfluencer.profile),
                selectinload(CampaignProposal.proposal_influencers)
                .selectinload(ProposalInfluencer.influencer_db),
            )
        )
        return result.scalar_one_or_none()

    async def get_brand_visible_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Return proposal data filtered by visible_fields. NEVER returns cost pricing."""
        proposal = await self.get_proposal_details(db, proposal_id, user_id)
        if not proposal:
            return None

        visible = proposal.visible_fields or {}

        # Build influencer list
        influencers = []
        for pi in sorted(proposal.proposal_influencers, key=lambda x: x.priority_order or 0):
            inf_db = pi.influencer_db
            profile = pi.profile

            # Use sell pricing: custom overrides > snapshot
            sell_pricing = pi.custom_sell_pricing or pi.sell_price_snapshot or {}

            # H13: Use explicit None checks instead of or-chaining (avoids falsy value bugs)
            def _pick(db_val, prof_val):
                """Prefer master DB value, fallback to profile. Handles falsy values correctly."""
                return db_val if db_val is not None else prof_val

            inf_data = {
                "id": str(pi.id),
                "influencer_db_id": str(pi.influencer_db_id) if pi.influencer_db_id else None,
                "priority_order": pi.priority_order,
                "selected_by_user": pi.selected_by_user,
                "selected_at": pi.selected_at.isoformat() if pi.selected_at else None,
                # Profile data (prefer master DB, fallback to profile)
                "username": _pick(inf_db.username if inf_db else None, profile.username if profile else None),
                "full_name": _pick(inf_db.full_name if inf_db else None, profile.full_name if profile else None),
                "profile_image_url": _pick(inf_db.profile_image_url if inf_db else None, profile.profile_pic_url if profile else None),
                "is_verified": _pick(inf_db.is_verified if inf_db else None, profile.is_verified if profile else False),
                "followers_count": _pick(inf_db.followers_count if inf_db else None, profile.followers_count if profile else None),
                "following_count": _pick(inf_db.following_count if inf_db else None, profile.following_count if profile else None),
                "posts_count": _pick(inf_db.posts_count if inf_db else None, profile.posts_count if profile else None),
                "biography": _pick(inf_db.biography if inf_db else None, profile.biography if profile else None),
                "categories": inf_db.categories if inf_db else [],
                "tags": inf_db.tags if inf_db else [],
                "tier": inf_db.tier if inf_db else None,
            }

            # Conditionally include engagement
            if visible.get("show_engagement", True):
                inf_data["engagement_rate"] = float(inf_db.engagement_rate) if inf_db and inf_db.engagement_rate else None
                inf_data["avg_likes"] = inf_db.avg_likes if inf_db else None
                inf_data["avg_comments"] = inf_db.avg_comments if inf_db else None
                inf_data["avg_views"] = inf_db.avg_views if inf_db else None

            # Conditionally include sell pricing (NEVER cost)
            if visible.get("show_sell_pricing", True):
                inf_data["sell_pricing"] = sell_pricing
                # Available deliverables = keys with non-null pricing
                inf_data["available_deliverables"] = [
                    k for k, v in sell_pricing.items()
                    if v is not None and k in ("post", "story", "reel", "carousel", "video", "bundle", "monthly")
                ]

            # Deliverable data
            inf_data["selected_deliverables"] = pi.selected_deliverables or []
            inf_data["assigned_deliverables"] = pi.assigned_deliverables or []

            # If assigned deliverables exist, filter available_deliverables to only those types
            if pi.assigned_deliverables:
                assigned_types = [d.get("type") for d in pi.assigned_deliverables if d.get("type")]
                inf_data["available_deliverables"] = [
                    t for t in assigned_types if sell_pricing.get(t) is not None
                ]

            influencers.append(inf_data)

        # Build summary
        summary = self._build_summary(influencers, proposal)

        # M11: Only include total_sell_amount if pricing is visible
        show_pricing = visible.get("show_sell_pricing", True)

        proposal_data = {
            "id": str(proposal.id),
            "title": proposal.title,
            "campaign_name": proposal.campaign_name,
            "description": proposal.description,
            "proposal_notes": proposal.proposal_notes,
            "status": proposal.status,
            "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
            "deadline_at": proposal.deadline_at.isoformat() if proposal.deadline_at else None,
            "cover_image_url": proposal.cover_image_url,
            "visible_fields": proposal.visible_fields,
            "created_at": proposal.created_at.isoformat(),
            "more_added_at": proposal.more_added_at.isoformat() if proposal.more_added_at else None,
            "request_more_at": proposal.request_more_at.isoformat() if proposal.request_more_at else None,
        }
        if show_pricing:
            proposal_data["total_sell_amount"] = float(proposal.total_sell_amount) if proposal.total_sell_amount else None

        return {
            "proposal": proposal_data,
            "influencers": influencers,
            "summary": summary,
        }

    def _build_summary(self, influencers: List[Dict], proposal: CampaignProposal) -> Dict:
        """Build aggregated summary for proposal."""
        total = len(influencers)
        selected = sum(1 for i in influencers if i.get("selected_by_user"))
        total_reach = sum(i.get("followers_count") or 0 for i in influencers)

        engagement_rates = [i["engagement_rate"] for i in influencers if i.get("engagement_rate")]
        avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0

        # Estimate total sell from sell_pricing snapshots
        estimated_sell = 0
        if proposal.total_sell_amount:
            estimated_sell = float(proposal.total_sell_amount)

        # Category breakdown
        cat_counts: Dict[str, int] = {}
        for inf in influencers:
            for cat in (inf.get("categories") or []):
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        category_breakdown = [
            {"name": name, "count": count, "percentage": round(count / total * 100, 1) if total else 0}
            for name, count in sorted(cat_counts.items(), key=lambda x: -x[1])
        ]

        # Tier breakdown
        tier_counts: Dict[str, int] = {}
        for inf in influencers:
            tier = inf.get("tier") or "Unknown"
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        tier_breakdown = [
            {"name": name, "count": count, "percentage": round(count / total * 100, 1) if total else 0}
            for name, count in sorted(tier_counts.items(), key=lambda x: -x[1])
        ]

        return {
            "total_influencers": total,
            "selected_count": selected,
            "total_reach": total_reach,
            "avg_engagement_rate": avg_engagement,
            "estimated_total_sell": estimated_sell,
            "category_breakdown": category_breakdown,
            "tier_breakdown": tier_breakdown,
        }

    # =============================================================================
    # FINANCIALS (Admin Only)
    # =============================================================================

    async def _recalculate_financials(self, db: AsyncSession, proposal: CampaignProposal):
        """Recalculate total_cost, total_sell, margin on proposal from its influencers.
        If assigned_deliverables exist, uses quantity-based pricing.
        Otherwise falls back to representative price (first non-null).
        """
        result = await db.execute(
            select(ProposalInfluencer).where(
                ProposalInfluencer.proposal_id == proposal.id
            )
        )
        pis = result.scalars().all()

        total_sell = Decimal("0")
        total_cost = Decimal("0")

        price_keys = ["post", "reel", "story", "carousel", "video", "bundle", "monthly"]

        for pi in pis:
            sell_snap = pi.custom_sell_pricing or pi.sell_price_snapshot or {}
            cost_snap = pi.cost_price_snapshot or {}
            assigned = pi.assigned_deliverables or []

            if assigned:
                # Quantity-based pricing from admin-defined deliverables
                for item in assigned:
                    d_type = item.get("type", "")
                    qty = item.get("quantity", 1)
                    sell_val = sell_snap.get(d_type)
                    cost_val = cost_snap.get(d_type)
                    if sell_val is not None:
                        total_sell += Decimal(str(sell_val)) * qty
                    if cost_val is not None:
                        total_cost += Decimal(str(cost_val)) * qty
            else:
                # Fallback: representative price (first non-null)
                for key in price_keys:
                    sell_val = sell_snap.get(key)
                    if sell_val is not None:
                        total_sell += Decimal(str(sell_val))
                        break
                for key in price_keys:
                    cost_val = cost_snap.get(key)
                    if cost_val is not None:
                        total_cost += Decimal(str(cost_val))
                        break

        proposal.total_sell_amount = total_sell
        proposal.total_cost_amount = total_cost
        if total_sell > 0:
            proposal.margin_percentage = round(
                ((total_sell - total_cost) / total_sell) * 100, 2
            )
        else:
            proposal.margin_percentage = Decimal("0")

    async def get_proposal_financials(
        self,
        db: AsyncSession,
        proposal_id: UUID,
    ) -> Dict[str, Any]:
        """Get financial breakdown for a proposal (admin only)."""
        result = await db.execute(
            select(CampaignProposal).where(CampaignProposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        return {
            "total_sell": float(proposal.total_sell_amount) if proposal.total_sell_amount else 0,
            "total_cost": float(proposal.total_cost_amount) if proposal.total_cost_amount else 0,
            "margin_percentage": float(proposal.margin_percentage) if proposal.margin_percentage else 0,
            "margin_amount": float((proposal.total_sell_amount or 0) - (proposal.total_cost_amount or 0)),
        }

    # =============================================================================
    # INFLUENCER SELECTION (User Actions)
    # =============================================================================

    async def update_influencer_selection(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        selected_influencer_ids: List[UUID],
        deliverable_selections: Optional[dict] = None,
    ) -> CampaignProposal:
        """User selects/deselects influencers and their deliverables. Uses ProposalInfluencer.id."""
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

            inf_result = await db.execute(
                select(ProposalInfluencer).where(
                    ProposalInfluencer.proposal_id == proposal_id
                )
            )
            proposal_influencers = inf_result.scalars().all()

            valid_deliverables = {"post", "story", "reel", "carousel", "video", "bundle", "monthly"}

            now = datetime.now(timezone.utc)
            for pi in proposal_influencers:
                if pi.id in selected_influencer_ids:
                    pi.selected_by_user = True
                    pi.selected_at = now
                    # Update deliverable selections if provided
                    if deliverable_selections and pi.id in deliverable_selections:
                        pi.selected_deliverables = [
                            d for d in deliverable_selections[pi.id]
                            if d in valid_deliverables
                        ]
                else:
                    pi.selected_by_user = False
                    pi.selected_at = None
                    pi.selected_deliverables = []

            if proposal.status in ('sent', 'more_requested'):
                proposal.status = 'in_review'

            await db.commit()
            await db.refresh(proposal)
            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update influencer selection: {e}")
            raise

    # =============================================================================
    # PROPOSAL APPROVAL/REJECTION (User Actions)
    # =============================================================================

    async def approve_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        selected_influencer_ids: List[UUID],
        notes: Optional[str] = None
    ) -> Campaign:
        """User approves proposal and creates campaign."""
        try:
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

            if proposal.status not in ('sent', 'in_review', 'more_requested'):
                raise ValueError(f"Cannot approve proposal in '{proposal.status}' status.")

            if not selected_influencer_ids:
                raise ValueError("At least one influencer must be selected for approval")

            # Prevent duplicate campaigns from same proposal
            existing_campaign = await db.execute(
                select(Campaign).where(Campaign.proposal_id == proposal_id)
            )
            if existing_campaign.scalar_one_or_none():
                raise ValueError("A campaign has already been created from this proposal")

            campaign = Campaign(
                user_id=user_id,
                name=proposal.campaign_name,
                description=proposal.description,
                brand_name=proposal.campaign_name,
                budget=proposal.total_budget,
                status='active',
                created_by='superadmin',
                proposal_id=proposal_id
            )
            db.add(campaign)

            proposal.status = 'approved'
            proposal.responded_at = datetime.now(timezone.utc)
            if notes:
                proposal.brand_notes = notes

            # H12: Mark selected AND deselect non-selected
            now = datetime.now(timezone.utc)
            for pi in proposal.proposal_influencers:
                if pi.id in selected_influencer_ids:
                    pi.selected_by_user = True
                    pi.selected_at = now
                else:
                    pi.selected_by_user = False
                    pi.selected_at = None

            await db.flush()

            # C3: Create CampaignCreator records with full proposal data
            actual_budget = Decimal("0")
            for pi in proposal.proposal_influencers:
                if pi.id in selected_influencer_ids and pi.profile_id:
                    # Calculate deliverable totals
                    del_total_sell = Decimal("0")
                    del_total_cost = Decimal("0")
                    sell_snap = pi.custom_sell_pricing or pi.sell_price_snapshot or {}
                    cost_snap = pi.cost_price_snapshot or {}
                    assigned = pi.assigned_deliverables or []

                    if assigned:
                        for item in assigned:
                            d_type = item.get("type", "")
                            qty = item.get("quantity", 1)
                            sv = sell_snap.get(d_type)
                            cv = cost_snap.get(d_type)
                            if sv is not None:
                                del_total_sell += Decimal(str(sv)) * qty
                            if cv is not None:
                                del_total_cost += Decimal(str(cv)) * qty
                    else:
                        # Fallback: representative price
                        for key in ["post", "reel", "story", "carousel", "video", "bundle", "monthly"]:
                            sv = sell_snap.get(key)
                            if sv is not None:
                                del_total_sell = Decimal(str(sv))
                                break
                        for key in ["post", "reel", "story", "carousel", "video", "bundle", "monthly"]:
                            cv = cost_snap.get(key)
                            if cv is not None:
                                del_total_cost = Decimal(str(cv))
                                break

                    actual_budget += del_total_sell

                    creator = CampaignCreator(
                        campaign_id=campaign.id,
                        profile_id=pi.profile_id,
                        influencer_db_id=pi.influencer_db_id,
                        assigned_deliverables=pi.assigned_deliverables or [],
                        selected_deliverables=pi.selected_deliverables or [],
                        sell_price_snapshot=pi.sell_price_snapshot or {},
                        cost_price_snapshot=pi.cost_price_snapshot or {},
                        deliverable_total_sell=del_total_sell,
                        deliverable_total_cost=del_total_cost,
                    )
                    db.add(creator)

            # Set campaign budget from actual selected deliverable costs
            if actual_budget > 0:
                campaign.budget = actual_budget

            await db.commit()
            await db.refresh(campaign)

            try:
                from app.services.notification_service import NotificationService
                if proposal.created_by_admin_id:
                    await NotificationService.notify_proposal_approved(
                        db,
                        proposal_id=proposal_id,
                        proposal_title=proposal.title,
                        campaign_name=proposal.campaign_name,
                        admin_id=proposal.created_by_admin_id,
                        selected_count=len(selected_influencer_ids),
                    )
            except Exception as notify_err:
                logger.warning(f"Failed to send approval notification: {notify_err}")

            logger.info(f"Approved proposal {proposal_id}, campaign {campaign.id}")
            return campaign

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to approve proposal: {e}")
            raise

    async def reject_proposal(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> CampaignProposal:
        """User rejects proposal."""
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

            if proposal.status not in ('sent', 'in_review', 'more_requested'):
                raise ValueError(f"Cannot reject proposal in '{proposal.status}' status.")

            proposal.status = 'rejected'
            proposal.responded_at = datetime.now(timezone.utc)
            proposal.rejection_reason = reason

            await db.commit()
            await db.refresh(proposal)

            try:
                from app.services.notification_service import NotificationService
                if proposal.created_by_admin_id:
                    await NotificationService.notify_proposal_rejected(
                        db,
                        proposal_id=proposal_id,
                        proposal_title=proposal.title,
                        campaign_name=proposal.campaign_name,
                        admin_id=proposal.created_by_admin_id,
                        reason=reason,
                    )
            except Exception as notify_err:
                logger.warning(f"Failed to send rejection notification: {notify_err}")

            return proposal

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to reject proposal: {e}")
            raise

    # =============================================================================
    # PROPOSAL STATISTICS
    # =============================================================================

    async def count_pending_proposals(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """Count pending proposals for a user."""
        try:
            result = await db.execute(
                select(func.count(CampaignProposal.id))
                .where(and_(
                    CampaignProposal.user_id == user_id,
                    CampaignProposal.status.in_(['sent', 'in_review', 'more_requested'])
                ))
            )
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count pending proposals: {e}")
            return 0

    async def get_admin_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get admin dashboard stats."""
        total = await db.execute(select(func.count(CampaignProposal.id)))
        active = await db.execute(
            select(func.count(CampaignProposal.id)).where(
                CampaignProposal.status.in_(['sent', 'in_review', 'more_requested'])
            )
        )
        approved = await db.execute(
            select(func.count(CampaignProposal.id)).where(
                CampaignProposal.status == 'approved'
            )
        )
        margin_result = await db.execute(
            select(
                func.sum(CampaignProposal.total_sell_amount),
                func.sum(CampaignProposal.total_cost_amount),
                func.avg(CampaignProposal.margin_percentage),
            ).where(CampaignProposal.total_sell_amount.isnot(None))
        )
        margin_row = margin_result.fetchone()

        total_count = total.scalar() or 0
        approved_count = approved.scalar() or 0

        return {
            "total_proposals": total_count,
            "active_proposals": active.scalar() or 0,
            "approved_proposals": approved_count,
            "approval_rate": round(approved_count / total_count * 100, 1) if total_count else 0,
            "total_margin": float(margin_row[0] or 0) - float(margin_row[1] or 0) if margin_row else 0,
            "avg_margin_percentage": float(margin_row[2] or 0) if margin_row else 0,
        }


    # =============================================================================
    # AI SELECTION SNAPSHOT
    # =============================================================================

    async def generate_selection_snapshot(
        self,
        db: AsyncSession,
        proposal_id: UUID,
        user_id: UUID,
        selected_influencer_ids: List[UUID],
    ) -> Dict[str, Any]:
        """Generate AI-powered insights about the brand's current selection."""
        # Verify proposal belongs to user
        result = await db.execute(
            select(CampaignProposal).where(and_(
                CampaignProposal.id == proposal_id,
                CampaignProposal.user_id == user_id,
            ))
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError("Proposal not found or unauthorized")

        if not selected_influencer_ids:
            return {
                "headline": "Select creators to see AI-powered insights",
                "insights": [],
                "recommendations": [],
                "scores": {},
            }

        # Fetch proposal influencers with their profiles AND influencer_db records
        pi_result = await db.execute(
            select(ProposalInfluencer)
            .where(and_(
                ProposalInfluencer.proposal_id == proposal_id,
                ProposalInfluencer.id.in_(selected_influencer_ids),
            ))
            .options(
                selectinload(ProposalInfluencer.profile),
                selectinload(ProposalInfluencer.influencer_db),
            )
        )
        selected_pis = pi_result.scalars().all()

        if not selected_pis:
            return {
                "headline": "AI insights will be available once creator profiles are fully analyzed",
                "insights": [],
                "recommendations": ["Creator profiles are being processed"],
                "scores": {},
            }

        # Aggregate AI data across selected proposal influencers
        # Uses Profile data when available, falls back to InfluencerDatabase
        total_followers = 0
        category_counts: Dict[str, float] = {}
        gender_totals: Dict[str, float] = {"female": 0, "male": 0}
        age_totals: Dict[str, float] = {}
        country_totals: Dict[str, float] = {}
        sentiment_scores = []
        authenticity_scores = []
        engagement_rates = []
        profiles_with_ai = 0

        for pi in selected_pis:
            profile = pi.profile
            inf_db = pi.influencer_db

            # Followers: Profile → InfluencerDatabase
            followers = 0
            if profile and profile.followers_count:
                followers = profile.followers_count
            elif inf_db and inf_db.followers_count:
                followers = inf_db.followers_count
            total_followers += followers
            weight = max(followers, 1)

            # Categories: Profile ai_content_distribution → InfluencerDatabase ai_content_categories / categories
            content_dist = getattr(profile, 'ai_content_distribution', None) if profile else None
            if content_dist and isinstance(content_dist, dict):
                profiles_with_ai += 1
                for cat_name, pct in content_dist.items():
                    if cat_name and cat_name != "general":
                        category_counts[cat_name] = category_counts.get(cat_name, 0) + (pct * 100)
            elif inf_db:
                # Fallback to InfluencerDatabase categories
                db_cats = inf_db.ai_content_categories or inf_db.categories or []
                if db_cats:
                    profiles_with_ai += 1
                    equal_pct = 100.0 / len(db_cats) if db_cats else 0
                    for cat_name in db_cats:
                        if cat_name:
                            category_counts[cat_name] = category_counts.get(cat_name, 0) + equal_pct

            # Audience insights (demographics) — only from Profile (no DB fallback)
            audience = getattr(profile, 'ai_audience_insights', None) if profile else None
            if audience and isinstance(audience, dict):
                demo = audience.get("demographic_insights", {})
                if isinstance(demo, dict):
                    gender = demo.get("estimated_gender_split", {})
                    if isinstance(gender, dict):
                        for g, v in gender.items():
                            g_lower = g.lower()
                            if g_lower in gender_totals:
                                gender_totals[g_lower] += (v or 0) * weight

                    ages = demo.get("estimated_age_groups", {})
                    if isinstance(ages, dict):
                        for age_group, pct in ages.items():
                            age_totals[age_group] = age_totals.get(age_group, 0) + (pct or 0) * weight

                geo = audience.get("geographic_analysis", {})
                if isinstance(geo, dict):
                    countries = geo.get("country_distribution", {})
                    if isinstance(countries, dict):
                        for country, pct in countries.items():
                            country_totals[country] = country_totals.get(country, 0) + (pct or 0) * weight

            # Sentiment: Profile → InfluencerDatabase
            sent_score = getattr(profile, 'ai_avg_sentiment_score', None) if profile else None
            if sent_score is None and inf_db:
                sent_score = inf_db.ai_sentiment_score
            if sent_score is not None:
                sentiment_scores.append(float(sent_score))

            # Authenticity: Profile ai_audience_quality → InfluencerDatabase ai_audience_quality_score
            auth_score = None
            if profile:
                quality = getattr(profile, 'ai_audience_quality', None)
                if quality and isinstance(quality, dict):
                    auth_score = quality.get("authenticity_score")
            if auth_score is None and inf_db and inf_db.ai_audience_quality_score is not None:
                # Normalize 0-1 scale to 0-100
                auth_score = float(inf_db.ai_audience_quality_score) * 100
            if auth_score is not None:
                authenticity_scores.append(float(auth_score))

            # Engagement: Profile → InfluencerDatabase
            eng = getattr(profile, 'engagement_rate', None) if profile else None
            if eng is None and inf_db and inf_db.engagement_rate is not None:
                eng = inf_db.engagement_rate
            if eng is not None:
                engagement_rates.append(float(eng))

        # Derive insights
        # Top category
        top_category = "General"
        if category_counts:
            top_category = max(category_counts, key=category_counts.get)

        # Dominant gender
        total_gender = sum(gender_totals.values())
        dominant_gender = "Mixed"
        gender_pct = 50
        if total_gender > 0:
            if gender_totals["female"] > gender_totals["male"]:
                dominant_gender = "Female"
                gender_pct = round(gender_totals["female"] / total_gender * 100)
            else:
                dominant_gender = "Male"
                gender_pct = round(gender_totals["male"] / total_gender * 100)

        # Top age group — map raw keys to human-readable labels
        age_label_map = {
            "gen_z": "18–24 (Gen Z)",
            "gen-z": "18–24 (Gen Z)",
            "millennial": "25–40 (Millennials)",
            "millennials": "25–40 (Millennials)",
            "gen_x": "41–56 (Gen X)",
            "gen-x": "41–56 (Gen X)",
            "boomer": "57+ (Boomers)",
            "boomers": "57+ (Boomers)",
        }
        top_age = "18–34"
        if age_totals:
            raw_key = max(age_totals, key=age_totals.get)
            top_age = age_label_map.get(raw_key, raw_key)

        # Top country
        top_country = "Global"
        if country_totals:
            top_country = max(country_totals, key=country_totals.get)

        # Scores
        avg_authenticity = round(sum(authenticity_scores) / len(authenticity_scores), 1) if authenticity_scores else 0
        avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores), 2) if sentiment_scores else 0
        avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0

        # Build headline
        sentiment_word = "positive" if avg_sentiment > 0.3 else "neutral" if avg_sentiment > -0.1 else "mixed"
        headline_parts = []
        if top_category != "General":
            headline_parts.append(f"Strong {top_category} focus")
        if dominant_gender != "Mixed" and gender_pct > 55:
            headline_parts.append(f"{dominant_gender} {top_age} audiences")
        if top_country != "Global":
            headline_parts.append(f"primarily in {top_country}")

        headline = " with ".join(headline_parts) if headline_parts else f"Diverse creator selection with {len(selected_pis)} creators"

        # Build insights
        insights = []
        if category_counts:
            sorted_cats = sorted(category_counts.items(), key=lambda x: -x[1])[:5]
            insights.append({
                "type": "categories",
                "title": "Content Categories",
                "data": [{"name": c, "value": round(v, 1)} for c, v in sorted_cats],
            })

        if total_gender > 0:
            insights.append({
                "type": "demographics",
                "title": "Audience Demographics",
                "data": {
                    "gender": {"female": round(gender_totals["female"] / total_gender * 100), "male": round(gender_totals["male"] / total_gender * 100)},
                    "top_age_group": top_age,
                    "top_country": top_country,
                },
            })

        insights.append({
            "type": "reach",
            "title": "Combined Reach",
            "data": {"total_followers": total_followers, "avg_engagement": avg_engagement},
        })

        # Build recommendations — contextual and actionable
        recommendations = []

        # Category diversity
        num_categories = len(category_counts)
        if num_categories == 1:
            recommendations.append("Consider adding creators from other content categories for broader reach")
        elif num_categories >= 4:
            recommendations.append(f"Great content diversity across {num_categories} categories — strong for broad campaigns")

        # Authenticity concerns
        if avg_authenticity > 0 and avg_authenticity < 60:
            recommendations.append("Some selected creators have lower authenticity scores — review audience quality carefully")
        elif avg_authenticity >= 80:
            recommendations.append("High audience authenticity across your selection — strong real-follower base")

        # Gender skew
        if dominant_gender != "Mixed" and gender_pct > 80:
            recommendations.append(f"Selection heavily skews {dominant_gender} ({gender_pct}%) — ensure alignment with campaign target")
        elif dominant_gender != "Mixed" and gender_pct > 60:
            recommendations.append(f"Audience leans {dominant_gender} ({gender_pct}%) — well-suited for gender-targeted campaigns")

        # Engagement quality
        if avg_engagement >= 5:
            recommendations.append("Outstanding engagement rates — your selection has highly active audiences")
        elif avg_engagement >= 3:
            recommendations.append("Excellent average engagement rate across your selection")
        elif avg_engagement >= 1:
            recommendations.append("Solid engagement rates — consider prioritizing high-engagement creators")
        elif avg_engagement > 0:
            recommendations.append("Lower engagement rates detected — consider swapping in more engaging creators")

        # Follower tier mix
        if len(selected_pis) >= 3:
            follower_counts = [
                (pi.profile.followers_count if pi.profile and pi.profile.followers_count else
                 pi.influencer_db.followers_count if pi.influencer_db and pi.influencer_db.followers_count else 0)
                for pi in selected_pis
            ]
            follower_counts = [f for f in follower_counts if f > 0]
            if follower_counts:
                max_f = max(follower_counts)
                min_f = min(follower_counts)
                if max_f > 0 and min_f > 0 and max_f / min_f > 50:
                    recommendations.append("Good mix of macro and micro creators — combines reach with niche engagement")

        # Geographic concentration
        if country_totals:
            total_geo = sum(country_totals.values())
            if total_geo > 0:
                top_geo_pct = max(country_totals.values()) / total_geo * 100
                if top_geo_pct > 80:
                    recommendations.append(f"Audience concentrated in {top_country} ({round(top_geo_pct)}%) — ideal for local campaigns")
                elif len(country_totals) >= 3 and top_geo_pct < 50:
                    recommendations.append("Audience spread across multiple regions — great for international reach")

        # Sentiment
        if avg_sentiment > 0.5:
            recommendations.append("Very positive content sentiment — audiences respond well to these creators")
        elif avg_sentiment < -0.1:
            recommendations.append("Mixed content sentiment detected — review content tone alignment with brand values")

        # Fallback
        if not recommendations:
            recommendations.append("Your selection looks well-balanced across key metrics")

        # Cap at 3 most relevant
        recommendations = recommendations[:3]

        return {
            "headline": headline,
            "insights": insights,
            "recommendations": recommendations,
            "scores": {
                "authenticity": avg_authenticity,
                "sentiment": avg_sentiment,
                "avg_engagement": avg_engagement,
                "total_reach": total_followers,
                "creators_with_ai_data": profiles_with_ai,
                "total_selected": len(selected_pis),
            },
        }


# Global service instance
campaign_proposals_service = CampaignProposalsService()
