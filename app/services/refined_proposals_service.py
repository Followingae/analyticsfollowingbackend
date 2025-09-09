"""
Refined B2B Proposals Service - Superadmin creates proposals for brands
Complete implementation of B2B proposal workflow with influencer pricing
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, text, insert
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import logging
from datetime import datetime, timezone, timedelta, date
import secrets
import string

from app.database.connection import get_session
from app.models.auth import UserInDB

logger = logging.getLogger(__name__)

class RefinedProposalsService:
    """Service for B2B Proposals - Superadmin → Brand workflow"""
    
    # =========================================================================
    # INFLUENCER PRICING MANAGEMENT (SUPERADMIN ONLY)
    # =========================================================================
    
    async def create_influencer_pricing(
        self,
        admin_user_id: UUID,
        profile_id: UUID,
        pricing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create or update pricing for an influencer (SUPERADMIN ONLY)"""
        async with get_session() as db:
            try:
                # Verify admin permissions
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can manage influencer pricing")
                
                # Check if pricing already exists
                existing_pricing = await db.execute(
                    text("SELECT id FROM influencer_pricing WHERE profile_id = :profile_id"),
                    {"profile_id": str(profile_id)}
                )
                existing = existing_pricing.fetchone()
                
                if existing:
                    # Update existing pricing
                    await db.execute(
                        text("""
                            UPDATE influencer_pricing SET
                                story_price_usd_cents = :story_price,
                                post_price_usd_cents = :post_price,
                                reel_price_usd_cents = :reel_price,
                                ugc_video_price_usd_cents = :ugc_price,
                                story_series_price_usd_cents = :story_series_price,
                                carousel_post_price_usd_cents = :carousel_price,
                                igtv_price_usd_cents = :igtv_price,
                                pricing_tier = :pricing_tier,
                                negotiable = :negotiable,
                                minimum_campaign_value_usd_cents = :min_value,
                                package_pricing = :package_pricing::jsonb,
                                volume_discounts = :volume_discounts::jsonb,
                                pricing_effective_date = :effective_date,
                                pricing_expires_date = :expires_date,
                                last_updated_by_admin_id = :admin_id,
                                updated_at = now()
                            WHERE profile_id = :profile_id
                        """),
                        {
                            "profile_id": str(profile_id),
                            "story_price": pricing_data.get("story_price_usd_cents"),
                            "post_price": pricing_data.get("post_price_usd_cents"),
                            "reel_price": pricing_data.get("reel_price_usd_cents"),
                            "ugc_price": pricing_data.get("ugc_video_price_usd_cents"),
                            "story_series_price": pricing_data.get("story_series_price_usd_cents"),
                            "carousel_price": pricing_data.get("carousel_post_price_usd_cents"),
                            "igtv_price": pricing_data.get("igtv_price_usd_cents"),
                            "pricing_tier": pricing_data.get("pricing_tier", "standard"),
                            "negotiable": pricing_data.get("negotiable", True),
                            "min_value": pricing_data.get("minimum_campaign_value_usd_cents"),
                            "package_pricing": pricing_data.get("package_pricing", {}),
                            "volume_discounts": pricing_data.get("volume_discounts", []),
                            "effective_date": pricing_data.get("pricing_effective_date", date.today()),
                            "expires_date": pricing_data.get("pricing_expires_date"),
                            "admin_id": str(admin_user_id)
                        }
                    )
                    
                    logger.info(f"Updated pricing for influencer {profile_id} by admin {admin_user_id}")
                    action = "updated"
                    
                else:
                    # Create new pricing
                    pricing_id = await db.execute(
                        text("""
                            INSERT INTO influencer_pricing (
                                profile_id, story_price_usd_cents, post_price_usd_cents, 
                                reel_price_usd_cents, ugc_video_price_usd_cents, 
                                story_series_price_usd_cents, carousel_post_price_usd_cents,
                                igtv_price_usd_cents, pricing_tier, negotiable,
                                minimum_campaign_value_usd_cents, package_pricing,
                                volume_discounts, pricing_effective_date, pricing_expires_date,
                                last_updated_by_admin_id
                            ) VALUES (
                                :profile_id, :story_price, :post_price, :reel_price,
                                :ugc_price, :story_series_price, :carousel_price, 
                                :igtv_price, :pricing_tier, :negotiable, :min_value,
                                :package_pricing::jsonb, :volume_discounts::jsonb,
                                :effective_date, :expires_date, :admin_id
                            ) RETURNING id
                        """),
                        {
                            "profile_id": str(profile_id),
                            "story_price": pricing_data.get("story_price_usd_cents"),
                            "post_price": pricing_data.get("post_price_usd_cents"),
                            "reel_price": pricing_data.get("reel_price_usd_cents"),
                            "ugc_price": pricing_data.get("ugc_video_price_usd_cents"),
                            "story_series_price": pricing_data.get("story_series_price_usd_cents"),
                            "carousel_price": pricing_data.get("carousel_post_price_usd_cents"),
                            "igtv_price": pricing_data.get("igtv_price_usd_cents"),
                            "pricing_tier": pricing_data.get("pricing_tier", "standard"),
                            "negotiable": pricing_data.get("negotiable", True),
                            "min_value": pricing_data.get("minimum_campaign_value_usd_cents"),
                            "package_pricing": pricing_data.get("package_pricing", {}),
                            "volume_discounts": pricing_data.get("volume_discounts", []),
                            "effective_date": pricing_data.get("pricing_effective_date", date.today()),
                            "expires_date": pricing_data.get("pricing_expires_date"),
                            "admin_id": str(admin_user_id)
                        }
                    )
                    
                    logger.info(f"Created pricing for influencer {profile_id} by admin {admin_user_id}")
                    action = "created"
                
                await db.commit()
                
                return {
                    "success": True,
                    "action": action,
                    "profile_id": str(profile_id),
                    "pricing_tier": pricing_data.get("pricing_tier", "standard")
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error managing influencer pricing: {e}")
                raise
    
    async def get_influencer_pricing(
        self,
        admin_user_id: UUID,
        profile_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get pricing for an influencer (SUPERADMIN ONLY)"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can view influencer pricing")
                
                result = await db.execute(
                    text("""
                        SELECT ip.*, p.username, p.full_name, p.followers_count
                        FROM influencer_pricing ip
                        JOIN profiles p ON ip.profile_id = p.id
                        WHERE ip.profile_id = :profile_id
                        AND (ip.pricing_expires_date IS NULL OR ip.pricing_expires_date >= CURRENT_DATE)
                    """),
                    {"profile_id": str(profile_id)}
                )
                
                pricing = result.fetchone()
                if not pricing:
                    return None
                
                return {
                    "profile_id": str(pricing.profile_id),
                    "username": pricing.username,
                    "full_name": pricing.full_name,
                    "followers_count": pricing.followers_count,
                    "pricing": {
                        "story_price_usd_cents": pricing.story_price_usd_cents,
                        "post_price_usd_cents": pricing.post_price_usd_cents,
                        "reel_price_usd_cents": pricing.reel_price_usd_cents,
                        "ugc_video_price_usd_cents": pricing.ugc_video_price_usd_cents,
                        "story_series_price_usd_cents": pricing.story_series_price_usd_cents,
                        "carousel_post_price_usd_cents": pricing.carousel_post_price_usd_cents,
                        "igtv_price_usd_cents": pricing.igtv_price_usd_cents,
                        "pricing_tier": pricing.pricing_tier,
                        "negotiable": pricing.negotiable,
                        "minimum_campaign_value_usd_cents": pricing.minimum_campaign_value_usd_cents,
                        "package_pricing": pricing.package_pricing,
                        "volume_discounts": pricing.volume_discounts,
                        "pricing_effective_date": pricing.pricing_effective_date.isoformat() if pricing.pricing_effective_date else None,
                        "pricing_expires_date": pricing.pricing_expires_date.isoformat() if pricing.pricing_expires_date else None
                    },
                    "last_updated_at": pricing.updated_at.isoformat() if pricing.updated_at else None
                }
                
            except Exception as e:
                logger.error(f"Error getting influencer pricing: {e}")
                raise
    
    async def calculate_influencer_cost(
        self,
        admin_user_id: UUID,
        profile_id: UUID,
        deliverables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate cost for influencer based on deliverables"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can calculate pricing")
                
                # Use database function for calculation
                deliverables_json = deliverables
                result = await db.execute(
                    text("SELECT calculate_influencer_proposal_pricing(:profile_id, :deliverables)"),
                    {
                        "profile_id": str(profile_id),
                        "deliverables": deliverables_json
                    }
                )
                
                calculation = result.scalar()
                return calculation if calculation else {"error": "Unable to calculate pricing"}
                
            except Exception as e:
                logger.error(f"Error calculating influencer cost: {e}")
                raise
    
    # =========================================================================
    # DYNAMIC INVITE CAMPAIGNS
    # =========================================================================
    
    async def create_invite_campaign(
        self,
        admin_user_id: UUID,
        campaign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create dynamic invite campaign for influencer applications"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can create invite campaigns")
                
                # Generate unique invite slug
                invite_slug = self._generate_invite_slug()
                
                # Create invite campaign
                campaign_id = await db.execute(
                    text("""
                        INSERT INTO invite_campaigns (
                            created_by_admin_id, campaign_name, campaign_description,
                            campaign_brief, cover_image_url, deliverables,
                            content_requirements, campaign_type, barter_offering,
                            barter_value_description, eligible_follower_range,
                            eligible_categories, eligible_locations, eligible_demographics,
                            max_applications, application_deadline, auto_approve_threshold,
                            invite_link_slug, requires_approval, is_private, invite_code
                        ) VALUES (
                            :admin_id, :name, :description, :brief, :cover_image,
                            :deliverables::jsonb, :content_requirements::jsonb,
                            :campaign_type, :barter_offering, :barter_value,
                            :follower_range::jsonb, :categories::jsonb, :locations::jsonb,
                            :demographics::jsonb, :max_applications, :deadline,
                            :auto_approve, :slug, :requires_approval, :is_private, :invite_code
                        ) RETURNING id
                    """),
                    {
                        "admin_id": str(admin_user_id),
                        "name": campaign_data["campaign_name"],
                        "description": campaign_data["campaign_description"],
                        "brief": campaign_data.get("campaign_brief"),
                        "cover_image": campaign_data.get("cover_image_url"),
                        "deliverables": campaign_data["deliverables"],
                        "content_requirements": campaign_data.get("content_requirements", {}),
                        "campaign_type": campaign_data.get("campaign_type", "paid"),
                        "barter_offering": campaign_data.get("barter_offering"),
                        "barter_value": campaign_data.get("barter_value_description"),
                        "follower_range": campaign_data.get("eligible_follower_range", {}),
                        "categories": campaign_data.get("eligible_categories", []),
                        "locations": campaign_data.get("eligible_locations", []),
                        "demographics": campaign_data.get("eligible_demographics", {}),
                        "max_applications": campaign_data.get("max_applications", 1000),
                        "deadline": campaign_data.get("application_deadline"),
                        "auto_approve": campaign_data.get("auto_approve_threshold", 0),
                        "slug": invite_slug,
                        "requires_approval": campaign_data.get("requires_approval", True),
                        "is_private": campaign_data.get("is_private", False),
                        "invite_code": campaign_data.get("invite_code")
                    }
                )
                
                new_id = campaign_id.scalar()
                await db.commit()
                
                logger.info(f"Created invite campaign {new_id} by admin {admin_user_id}")
                
                return {
                    "id": str(new_id),
                    "invite_slug": invite_slug,
                    "invite_url": f"/invite/{invite_slug}",
                    "campaign_name": campaign_data["campaign_name"],
                    "status": "draft"
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error creating invite campaign: {e}")
                raise
    
    async def publish_invite_campaign(
        self,
        admin_user_id: UUID,
        campaign_id: UUID
    ) -> Dict[str, Any]:
        """Publish invite campaign to make it live"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can publish campaigns")
                
                # Update campaign status
                result = await db.execute(
                    text("""
                        UPDATE invite_campaigns 
                        SET status = 'active', published_at = now(), updated_at = now()
                        WHERE id = :campaign_id AND created_by_admin_id = :admin_id
                        RETURNING invite_link_slug
                    """),
                    {"campaign_id": str(campaign_id), "admin_id": str(admin_user_id)}
                )
                
                campaign = result.fetchone()
                if not campaign:
                    raise ValueError("Campaign not found or access denied")
                
                await db.commit()
                
                return {
                    "id": str(campaign_id),
                    "status": "active",
                    "invite_url": f"/invite/{campaign.invite_link_slug}",
                    "published_at": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error publishing campaign: {e}")
                raise
    
    async def get_invite_campaign_applications(
        self,
        admin_user_id: UUID,
        campaign_id: UUID,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get applications for invite campaign"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can view applications")
                
                # Build query with optional status filter
                where_clause = "WHERE ia.invite_campaign_id = :campaign_id"
                params = {"campaign_id": str(campaign_id), "limit": limit, "offset": offset}
                
                if status_filter:
                    where_clause += " AND ia.application_status = :status"
                    params["status"] = status_filter
                
                # Get applications with profile matching
                result = await db.execute(
                    text(f"""
                        SELECT 
                            ia.*,
                            p.username as existing_username,
                            p.followers_count as existing_followers,
                            p.is_verified as existing_verified
                        FROM influencer_applications ia
                        LEFT JOIN profiles p ON ia.matched_profile_id = p.id
                        {where_clause}
                        ORDER BY ia.applied_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    params
                )
                
                applications = result.fetchall()
                
                # Get total count
                count_result = await db.execute(
                    text(f"""
                        SELECT COUNT(*) FROM influencer_applications ia {where_clause.replace('LIMIT :limit OFFSET :offset', '')}
                    """),
                    {k: v for k, v in params.items() if k not in ['limit', 'offset']}
                )
                total_count = count_result.scalar()
                
                applications_data = []
                for app in applications:
                    applications_data.append({
                        "id": str(app.id),
                        "instagram_username": app.instagram_username,
                        "full_name": app.full_name,
                        "email": app.email,
                        "phone_number": app.phone_number,
                        "followers_count": app.followers_count,
                        "engagement_rate": app.engagement_rate,
                        "primary_content_categories": app.primary_content_categories,
                        "location_city": app.location_city,
                        "location_country": app.location_country,
                        "pricing": {
                            "story_price_usd_cents": app.proposed_story_price_usd_cents,
                            "post_price_usd_cents": app.proposed_post_price_usd_cents,
                            "reel_price_usd_cents": app.proposed_reel_price_usd_cents,
                            "package_price_usd_cents": app.proposed_package_price_usd_cents
                        },
                        "application_message": app.application_message,
                        "portfolio_links": app.portfolio_links,
                        "application_status": app.application_status,
                        "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                        "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
                        "admin_notes": app.admin_notes,
                        "existing_profile": {
                            "matched": app.matched_profile_id is not None,
                            "username": app.existing_username,
                            "followers": app.existing_followers,
                            "verified": app.existing_verified
                        } if app.matched_profile_id else None
                    })
                
                return {
                    "applications": applications_data,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
                
            except Exception as e:
                logger.error(f"Error getting campaign applications: {e}")
                raise
    
    async def approve_campaign_application(
        self,
        admin_user_id: UUID,
        application_id: UUID,
        admin_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Approve influencer application"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can approve applications")
                
                # Update application status
                result = await db.execute(
                    text("""
                        UPDATE influencer_applications 
                        SET 
                            application_status = 'approved',
                            admin_notes = COALESCE(:admin_notes, admin_notes),
                            reviewed_by_admin_id = :admin_id,
                            reviewed_at = now(),
                            updated_at = now()
                        WHERE id = :application_id
                        RETURNING instagram_username, invite_campaign_id
                    """),
                    {
                        "application_id": str(application_id),
                        "admin_id": str(admin_user_id),
                        "admin_notes": admin_notes
                    }
                )
                
                application = result.fetchone()
                if not application:
                    raise ValueError("Application not found")
                
                await db.commit()
                
                logger.info(f"Approved application {application_id} for {application.instagram_username}")
                
                return {
                    "application_id": str(application_id),
                    "status": "approved",
                    "username": application.instagram_username,
                    "approved_by": str(admin_user_id),
                    "approved_at": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error approving application: {e}")
                raise
    
    # =========================================================================
    # BRAND PROPOSAL CREATION & MANAGEMENT
    # =========================================================================
    
    async def create_brand_proposal(
        self,
        admin_user_id: UUID,
        proposal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create proposal for brand users"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can create proposals")
                
                # Create brand proposal
                proposal_id = await db.execute(
                    text("""
                        INSERT INTO brand_proposals_v2 (
                            created_by_admin_id, assigned_brand_users, brand_company_name,
                            proposal_title, proposal_description, campaign_brief, cover_image_url,
                            campaign_type, campaign_goals, target_demographics,
                            proposed_start_date, proposed_end_date, content_deadline,
                            brand_response_deadline, deliverables, content_requirements,
                            brand_guidelines, hashtags_required, mentions_required,
                            total_campaign_budget_usd_cents, budget_breakdown, payment_terms,
                            priority_level, expected_total_reach, expected_total_engagement,
                            success_metrics, admin_notes
                        ) VALUES (
                            :admin_id, :brand_users::jsonb, :company_name, :title,
                            :description, :brief, :cover_image, :campaign_type,
                            :campaign_goals::jsonb, :demographics::jsonb, :start_date,
                            :end_date, :content_deadline, :response_deadline,
                            :deliverables::jsonb, :content_requirements::jsonb,
                            :brand_guidelines, :hashtags::jsonb, :mentions::jsonb,
                            :total_budget, :budget_breakdown::jsonb, :payment_terms,
                            :priority, :expected_reach, :expected_engagement,
                            :success_metrics::jsonb, :admin_notes
                        ) RETURNING id
                    """),
                    {
                        "admin_id": str(admin_user_id),
                        "brand_users": proposal_data["assigned_brand_users"],
                        "company_name": proposal_data["brand_company_name"],
                        "title": proposal_data["proposal_title"],
                        "description": proposal_data["proposal_description"],
                        "brief": proposal_data.get("campaign_brief"),
                        "cover_image": proposal_data.get("cover_image_url"),
                        "campaign_type": proposal_data.get("campaign_type", "sponsored_content"),
                        "campaign_goals": proposal_data.get("campaign_goals", []),
                        "demographics": proposal_data.get("target_demographics", {}),
                        "start_date": proposal_data.get("proposed_start_date"),
                        "end_date": proposal_data.get("proposed_end_date"),
                        "content_deadline": proposal_data.get("content_deadline"),
                        "response_deadline": proposal_data.get("brand_response_deadline"),
                        "deliverables": proposal_data["deliverables"],
                        "content_requirements": proposal_data.get("content_requirements", {}),
                        "brand_guidelines": proposal_data.get("brand_guidelines"),
                        "hashtags": proposal_data.get("hashtags_required", []),
                        "mentions": proposal_data.get("mentions_required", []),
                        "total_budget": proposal_data["total_campaign_budget_usd_cents"],
                        "budget_breakdown": proposal_data.get("budget_breakdown", {}),
                        "payment_terms": proposal_data.get("payment_terms", "net_30"),
                        "priority": proposal_data.get("priority_level", "medium"),
                        "expected_reach": proposal_data.get("expected_total_reach"),
                        "expected_engagement": proposal_data.get("expected_total_engagement"),
                        "success_metrics": proposal_data.get("success_metrics", {}),
                        "admin_notes": proposal_data.get("admin_notes")
                    }
                )
                
                new_proposal_id = proposal_id.scalar()
                await db.commit()
                
                logger.info(f"Created proposal {new_proposal_id} by admin {admin_user_id}")
                
                return {
                    "id": str(new_proposal_id),
                    "proposal_title": proposal_data["proposal_title"],
                    "status": "draft",
                    "assigned_brand_users": proposal_data["assigned_brand_users"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error creating brand proposal: {e}")
                raise
    
    async def add_influencers_to_proposal(
        self,
        admin_user_id: UUID,
        proposal_id: UUID,
        influencers_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add influencers to proposal with pricing"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can manage proposals")
                
                added_influencers = []
                
                for influencer_data in influencers_data:
                    # Determine source (database profile or application)
                    profile_id = influencer_data.get("profile_id")
                    application_id = influencer_data.get("application_id")
                    
                    if not profile_id and not application_id:
                        raise ValueError("Must specify either profile_id or application_id")
                    
                    # Get pricing (either from database or custom)
                    pricing_source = "custom"
                    original_pricing = {}
                    
                    if profile_id:
                        # Try to get database pricing
                        db_pricing = await self.get_influencer_pricing(admin_user_id, UUID(profile_id))
                        if db_pricing:
                            original_pricing = db_pricing["pricing"]
                            pricing_source = "database"
                    
                    # Insert influencer into proposal
                    influencer_id = await db.execute(
                        text("""
                            INSERT INTO proposal_influencers (
                                proposal_id, profile_id, application_id, instagram_username,
                                full_name, followers_count, engagement_rate, profile_image_url,
                                story_price_usd_cents, post_price_usd_cents, reel_price_usd_cents,
                                total_influencer_budget_usd_cents, pricing_source,
                                original_database_pricing, admin_price_adjustments,
                                price_adjustment_reason, assigned_deliverables,
                                deliverable_specifications, expected_reach, expected_engagement,
                                performance_kpis, admin_selection_notes, added_by_admin_id
                            ) VALUES (
                                :proposal_id, :profile_id, :application_id, :username,
                                :full_name, :followers, :engagement_rate, :profile_image,
                                :story_price, :post_price, :reel_price, :total_budget,
                                :pricing_source, :original_pricing::jsonb, :price_adjustments::jsonb,
                                :adjustment_reason, :deliverables::jsonb, :specifications::jsonb,
                                :expected_reach, :expected_engagement, :kpis::jsonb,
                                :selection_notes, :admin_id
                            ) RETURNING id
                        """),
                        {
                            "proposal_id": str(proposal_id),
                            "profile_id": profile_id,
                            "application_id": application_id,
                            "username": influencer_data["instagram_username"],
                            "full_name": influencer_data.get("full_name"),
                            "followers": influencer_data.get("followers_count", 0),
                            "engagement_rate": influencer_data.get("engagement_rate", 0.0),
                            "profile_image": influencer_data.get("profile_image_url"),
                            "story_price": influencer_data.get("story_price_usd_cents"),
                            "post_price": influencer_data.get("post_price_usd_cents"),
                            "reel_price": influencer_data.get("reel_price_usd_cents"),
                            "total_budget": influencer_data["total_influencer_budget_usd_cents"],
                            "pricing_source": pricing_source,
                            "original_pricing": original_pricing,
                            "price_adjustments": influencer_data.get("admin_price_adjustments", {}),
                            "adjustment_reason": influencer_data.get("price_adjustment_reason"),
                            "deliverables": influencer_data["assigned_deliverables"],
                            "specifications": influencer_data.get("deliverable_specifications", {}),
                            "expected_reach": influencer_data.get("expected_reach"),
                            "expected_engagement": influencer_data.get("expected_engagement"),
                            "kpis": influencer_data.get("performance_kpis", {}),
                            "selection_notes": influencer_data.get("admin_selection_notes"),
                            "admin_id": str(admin_user_id)
                        }
                    )
                    
                    new_id = influencer_id.scalar()
                    added_influencers.append({
                        "id": str(new_id),
                        "username": influencer_data["instagram_username"],
                        "total_budget_usd_cents": influencer_data["total_influencer_budget_usd_cents"],
                        "pricing_source": pricing_source
                    })
                
                await db.commit()
                
                logger.info(f"Added {len(added_influencers)} influencers to proposal {proposal_id}")
                
                return {
                    "proposal_id": str(proposal_id),
                    "added_influencers": added_influencers,
                    "total_added": len(added_influencers)
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error adding influencers to proposal: {e}")
                raise
    
    async def send_proposal_to_brands(
        self,
        admin_user_id: UUID,
        proposal_id: UUID,
        send_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send proposal to assigned brand users"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can send proposals")
                
                # Update proposal status
                result = await db.execute(
                    text("""
                        UPDATE brand_proposals_v2 
                        SET 
                            status = 'sent',
                            sent_to_brands_at = now(),
                            updated_at = now()
                        WHERE id = :proposal_id AND created_by_admin_id = :admin_id
                        RETURNING proposal_title, assigned_brand_users
                    """),
                    {"proposal_id": str(proposal_id), "admin_id": str(admin_user_id)}
                )
                
                proposal = result.fetchone()
                if not proposal:
                    raise ValueError("Proposal not found or access denied")
                
                # Log communication
                await db.execute(
                    text("""
                        INSERT INTO proposal_communications_v2 (
                            proposal_id, sender_type, sender_user_id,
                            recipient_user_ids, communication_type, subject,
                            message_content, is_system_message, system_message_type
                        ) VALUES (
                            :proposal_id, 'admin', :admin_id, :recipients::jsonb,
                            'system_notification', :subject, :message, true, 'proposal_sent'
                        )
                    """),
                    {
                        "proposal_id": str(proposal_id),
                        "admin_id": str(admin_user_id),
                        "recipients": proposal.assigned_brand_users,
                        "subject": f"New Proposal: {proposal.proposal_title}",
                        "message": "A new proposal has been sent for your review."
                    }
                )
                
                await db.commit()
                
                logger.info(f"Sent proposal {proposal_id} to brands")
                
                return {
                    "proposal_id": str(proposal_id),
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "recipients": proposal.assigned_brand_users,
                    "proposal_title": proposal.proposal_title
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error sending proposal: {e}")
                raise
    
    # =========================================================================
    # PROPOSAL RETRIEVAL FOR SUPERADMIN
    # =========================================================================
    
    async def get_admin_proposals(
        self,
        admin_user_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get all proposals created by admin"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can view admin proposals")
                
                # Build query with filters
                where_conditions = ["bp.created_by_admin_id = :admin_id"]
                params = {"admin_id": str(admin_user_id), "limit": limit, "offset": offset}
                
                if filters:
                    if "status" in filters:
                        where_conditions.append("bp.status = :status")
                        params["status"] = filters["status"]
                    
                    if "priority_level" in filters:
                        where_conditions.append("bp.priority_level = :priority")
                        params["priority"] = filters["priority_level"]
                    
                    if "campaign_type" in filters:
                        where_conditions.append("bp.campaign_type = :campaign_type")
                        params["campaign_type"] = filters["campaign_type"]
                
                where_clause = " AND ".join(where_conditions)
                
                # Get proposals with influencer counts
                result = await db.execute(
                    text(f"""
                        SELECT 
                            bp.*,
                            COALESCE(pi_count.influencer_count, 0) as influencer_count,
                            COALESCE(pi_count.total_influencer_budget, 0) as total_influencer_budget
                        FROM brand_proposals_v2 bp
                        LEFT JOIN (
                            SELECT 
                                proposal_id,
                                COUNT(*) as influencer_count,
                                SUM(total_influencer_budget_usd_cents) as total_influencer_budget
                            FROM proposal_influencers
                            WHERE selection_status = 'selected'
                            GROUP BY proposal_id
                        ) pi_count ON bp.id = pi_count.proposal_id
                        WHERE {where_clause}
                        ORDER BY bp.created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    params
                )
                
                proposals = result.fetchall()
                
                proposals_data = []
                for proposal in proposals:
                    proposals_data.append({
                        "id": str(proposal.id),
                        "proposal_title": proposal.proposal_title,
                        "brand_company_name": proposal.brand_company_name,
                        "assigned_brand_users": proposal.assigned_brand_users,
                        "campaign_type": proposal.campaign_type,
                        "status": proposal.status,
                        "priority_level": proposal.priority_level,
                        "total_campaign_budget_usd_cents": proposal.total_campaign_budget_usd_cents,
                        "influencer_count": proposal.influencer_count,
                        "total_influencer_budget": proposal.total_influencer_budget,
                        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
                        "sent_to_brands_at": proposal.sent_to_brands_at.isoformat() if proposal.sent_to_brands_at else None,
                        "brand_response": proposal.brand_response,
                        "brand_responded_at": proposal.brand_responded_at.isoformat() if proposal.brand_responded_at else None
                    })
                
                # Get total count
                count_result = await db.execute(
                    text(f"SELECT COUNT(*) FROM brand_proposals_v2 bp WHERE {where_clause}"),
                    {k: v for k, v in params.items() if k not in ['limit', 'offset']}
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
                logger.error(f"Error getting admin proposals: {e}")
                raise
    
    async def get_proposal_details_with_influencers(
        self,
        admin_user_id: UUID,
        proposal_id: UUID
    ) -> Dict[str, Any]:
        """Get complete proposal details with influencers"""
        async with get_session() as db:
            try:
                if not await self._check_superadmin_permission(db, admin_user_id):
                    raise ValueError("Only superadmin can view proposal details")
                
                # Use database function for comprehensive data
                result = await db.execute(
                    text("SELECT get_proposal_with_influencers_summary(:proposal_id)"),
                    {"proposal_id": str(proposal_id)}
                )
                
                summary = result.scalar()
                
                if not summary:
                    raise ValueError("Proposal not found")
                
                return summary
                
            except Exception as e:
                logger.error(f"Error getting proposal details: {e}")
                raise
    
    # =========================================================================
    # BRAND USER PROPOSAL VIEWING
    # =========================================================================
    
    async def get_brand_user_proposals(
        self,
        brand_user_id: UUID,
        status_filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get proposals assigned to brand user"""
        async with get_session() as db:
            try:
                # Build query
                where_conditions = ["assigned_brand_users::jsonb ? :user_id"]
                params = {"user_id": str(brand_user_id), "limit": limit, "offset": offset}
                
                if status_filter:
                    where_conditions.append("status = :status")
                    params["status"] = status_filter
                
                where_clause = " AND ".join(where_conditions)
                
                # Get proposals for brand user
                result = await db.execute(
                    text(f"""
                        SELECT 
                            bp.*,
                            COALESCE(pi_count.influencer_count, 0) as influencer_count,
                            COALESCE(pi_count.total_budget, 0) as calculated_budget
                        FROM brand_proposals_v2 bp
                        LEFT JOIN (
                            SELECT 
                                proposal_id,
                                COUNT(*) as influencer_count,
                                SUM(total_influencer_budget_usd_cents) as total_budget
                            FROM proposal_influencers
                            WHERE selection_status = 'selected'
                            GROUP BY proposal_id
                        ) pi_count ON bp.id = pi_count.proposal_id
                        WHERE {where_clause}
                        ORDER BY bp.sent_to_brands_at DESC, bp.created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    params
                )
                
                proposals = result.fetchall()
                
                # Mark as viewed (update last_viewed_at)
                proposal_ids = [str(p.id) for p in proposals]
                if proposal_ids:
                    await db.execute(
                        text("""
                            UPDATE brand_proposals_v2 
                            SET last_viewed_at = now()
                            WHERE id = ANY(:proposal_ids::uuid[])
                            AND (first_viewed_at IS NULL OR last_viewed_at < now() - INTERVAL '1 hour')
                        """),
                        {"proposal_ids": proposal_ids}
                    )
                    
                    # Set first_viewed_at for new proposals
                    await db.execute(
                        text("""
                            UPDATE brand_proposals_v2 
                            SET first_viewed_at = now()
                            WHERE id = ANY(:proposal_ids::uuid[])
                            AND first_viewed_at IS NULL
                        """),
                        {"proposal_ids": proposal_ids}
                    )
                
                proposals_data = []
                for proposal in proposals:
                    proposals_data.append({
                        "id": str(proposal.id),
                        "proposal_title": proposal.proposal_title,
                        "proposal_description": proposal.proposal_description,
                        "campaign_brief": proposal.campaign_brief,
                        "cover_image_url": proposal.cover_image_url,
                        "campaign_type": proposal.campaign_type,
                        "campaign_goals": proposal.campaign_goals,
                        "deliverables": proposal.deliverables,
                        "content_requirements": proposal.content_requirements,
                        "brand_guidelines": proposal.brand_guidelines,
                        "hashtags_required": proposal.hashtags_required,
                        "mentions_required": proposal.mentions_required,
                        "total_campaign_budget_usd_cents": proposal.total_campaign_budget_usd_cents,
                        "calculated_budget": proposal.calculated_budget,
                        "proposed_start_date": proposal.proposed_start_date.isoformat() if proposal.proposed_start_date else None,
                        "proposed_end_date": proposal.proposed_end_date.isoformat() if proposal.proposed_end_date else None,
                        "content_deadline": proposal.content_deadline.isoformat() if proposal.content_deadline else None,
                        "brand_response_deadline": proposal.brand_response_deadline.isoformat() if proposal.brand_response_deadline else None,
                        "status": proposal.status,
                        "priority_level": proposal.priority_level,
                        "influencer_count": proposal.influencer_count,
                        "expected_total_reach": proposal.expected_total_reach,
                        "expected_total_engagement": proposal.expected_total_engagement,
                        "success_metrics": proposal.success_metrics,
                        "sent_to_brands_at": proposal.sent_to_brands_at.isoformat() if proposal.sent_to_brands_at else None,
                        "brand_response": proposal.brand_response,
                        "brand_feedback": proposal.brand_feedback,
                        "brand_responded_at": proposal.brand_responded_at.isoformat() if proposal.brand_responded_at else None
                    })
                
                await db.commit()
                
                return {
                    "proposals": proposals_data,
                    "total_count": len(proposals_data),
                    "limit": limit,
                    "offset": offset
                }
                
            except Exception as e:
                logger.error(f"Error getting brand proposals: {e}")
                raise
    
    async def get_brand_proposal_influencers(
        self,
        brand_user_id: UUID,
        proposal_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get influencers for a specific proposal (brand user view)"""
        async with get_session() as db:
            try:
                # Verify brand user has access to this proposal
                access_check = await db.execute(
                    text("""
                        SELECT 1 FROM brand_proposals_v2 
                        WHERE id = :proposal_id 
                        AND assigned_brand_users::jsonb ? :user_id
                    """),
                    {"proposal_id": str(proposal_id), "user_id": str(brand_user_id)}
                )
                
                if not access_check.fetchone():
                    raise ValueError("Proposal not found or access denied")
                
                # Get influencers for the proposal (without sensitive pricing info)
                result = await db.execute(
                    text("""
                        SELECT 
                            pi.id, pi.instagram_username, pi.full_name,
                            pi.followers_count, pi.engagement_rate, pi.profile_image_url,
                            pi.assigned_deliverables, pi.deliverable_specifications,
                            pi.expected_reach, pi.expected_engagement,
                            pi.performance_kpis, pi.selection_status, pi.brand_approval_status,
                            -- Only show total budget, not detailed pricing breakdown
                            pi.total_influencer_budget_usd_cents,
                            p.username as profile_username, p.is_verified,
                            p.profile_pic_url as profile_pic_from_db
                        FROM proposal_influencers pi
                        LEFT JOIN profiles p ON pi.profile_id = p.id
                        WHERE pi.proposal_id = :proposal_id
                        AND pi.selection_status = 'selected'
                        ORDER BY pi.followers_count DESC, pi.added_at ASC
                    """),
                    {"proposal_id": str(proposal_id)}
                )
                
                influencers = result.fetchall()
                
                influencers_data = []
                for inf in influencers:
                    influencers_data.append({
                        "id": str(inf.id),
                        "instagram_username": inf.instagram_username,
                        "full_name": inf.full_name,
                        "followers_count": inf.followers_count,
                        "engagement_rate": inf.engagement_rate,
                        "profile_image_url": inf.profile_image_url or inf.profile_pic_from_db,
                        "is_verified": inf.is_verified,
                        "assigned_deliverables": inf.assigned_deliverables,
                        "deliverable_specifications": inf.deliverable_specifications,
                        "expected_reach": inf.expected_reach,
                        "expected_engagement": inf.expected_engagement,
                        "performance_kpis": inf.performance_kpis,
                        "total_budget_usd_cents": inf.total_influencer_budget_usd_cents,
                        "brand_approval_status": inf.brand_approval_status
                    })
                
                return influencers_data
                
            except Exception as e:
                logger.error(f"Error getting proposal influencers: {e}")
                raise
    
    async def submit_brand_response(
        self,
        brand_user_id: UUID,
        proposal_id: UUID,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Brand user submits response to proposal"""
        async with get_session() as db:
            try:
                # Verify access and update response
                result = await db.execute(
                    text("""
                        UPDATE brand_proposals_v2 
                        SET 
                            brand_response = :response,
                            brand_feedback = :feedback,
                            brand_requested_changes = :changes::jsonb,
                            brand_responded_at = now(),
                            status = CASE 
                                WHEN :response = 'approved' THEN 'approved'
                                WHEN :response = 'rejected' THEN 'rejected' 
                                ELSE 'negotiation'
                            END,
                            updated_at = now()
                        WHERE id = :proposal_id 
                        AND assigned_brand_users::jsonb ? :user_id
                        RETURNING proposal_title, created_by_admin_id
                    """),
                    {
                        "proposal_id": str(proposal_id),
                        "user_id": str(brand_user_id),
                        "response": response_data["response"],
                        "feedback": response_data.get("feedback"),
                        "changes": response_data.get("requested_changes", [])
                    }
                )
                
                proposal = result.fetchone()
                if not proposal:
                    raise ValueError("Proposal not found or access denied")
                
                # Log communication
                await db.execute(
                    text("""
                        INSERT INTO proposal_communications_v2 (
                            proposal_id, sender_type, sender_user_id,
                            recipient_user_ids, communication_type, subject,
                            message_content, is_system_message, system_message_type
                        ) VALUES (
                            :proposal_id, 'brand', :user_id, :admin_id::jsonb,
                            'response', :subject, :message, true, 'brand_response'
                        )
                    """),
                    {
                        "proposal_id": str(proposal_id),
                        "user_id": str(brand_user_id),
                        "admin_id": [str(proposal.created_by_admin_id)],
                        "subject": f"Response to: {proposal.proposal_title}",
                        "message": f"Brand has responded: {response_data['response']}. {response_data.get('feedback', '')}"
                    }
                )
                
                await db.commit()
                
                logger.info(f"Brand {brand_user_id} responded to proposal {proposal_id}: {response_data['response']}")
                
                return {
                    "proposal_id": str(proposal_id),
                    "response": response_data["response"],
                    "responded_at": datetime.now(timezone.utc).isoformat(),
                    "message": "Response submitted successfully"
                }
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error submitting brand response: {e}")
                raise
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _check_superadmin_permission(self, db: AsyncSession, user_id: UUID) -> bool:
        """Check if user has superadmin permissions"""
        try:
            result = await db.execute(
                text("""
                    SELECT 1 FROM users 
                    WHERE id = :user_id 
                    AND role IN ('admin', 'superadmin', 'super_admin')
                """),
                {"user_id": str(user_id)}
            )
            return result.fetchone() is not None
        except Exception:
            return False
    
    def _generate_invite_slug(self) -> str:
        """Generate unique invite slug for campaigns"""
        # Generate a random slug with letters and numbers
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(12))


# Global service instance
refined_proposals_service = RefinedProposalsService()