"""
Campaigns Service - Enhanced Campaign Management with Deliverables and Workflow
Complete campaign management with deliverables tracking, performance metrics, and workflow management
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import logging
from datetime import datetime, timezone, timedelta, date

from app.database.unified_models import (
    User, Profile, Campaign, CampaignPost, CampaignProfile,
    CampaignDeliverable, CampaignCollaborator, CampaignMilestone,
    CampaignPerformanceMetrics, CampaignBudgetTracking, CampaignActivityLog
)

logger = logging.getLogger(__name__)

class CampaignsService:
    """Service class for Enhanced Campaign Management functionality"""
    
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
    
    async def _check_campaign_permission(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID, 
        required_permission: str = "view"
    ) -> bool:
        """Check if user has permission to access campaign"""
        try:
            # Check if user owns the campaign
            owner_query = select(Campaign).where(
                and_(Campaign.id == campaign_id, Campaign.user_id == user_id)
            )
            owner_result = await db.execute(owner_query)
            if owner_result.scalar_one_or_none():
                return True
            
            # Check collaboration permissions
            collab_query = select(CampaignCollaborator).where(
                and_(
                    CampaignCollaborator.campaign_id == campaign_id,
                    CampaignCollaborator.collaborator_user_id == user_id,
                    CampaignCollaborator.collaboration_status == 'active'
                )
            )
            collab_result = await db.execute(collab_query)
            collaboration = collab_result.scalar_one_or_none()
            
            if not collaboration:
                return False
                
            # Check specific permissions
            permission_map = {
                "view": True,  # All collaborators can view
                "edit": collaboration.can_create_deliverables or collaboration.collaboration_type in ['owner', 'manager'],
                "approve": collaboration.can_approve_content,
                "analytics": collaboration.can_view_analytics,
                "budget": collaboration.can_manage_budget
            }
            
            return permission_map.get(required_permission, False)
            
        except Exception as e:
            logger.error(f"Error checking campaign permission: {e}")
            return False
    
    async def _log_activity(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        activity_type: str,
        activity_description: str,
        performed_by_user_id: Optional[UUID] = None,
        performed_by_profile_id: Optional[UUID] = None,
        related_deliverable_id: Optional[UUID] = None,
        related_collaborator_id: Optional[UUID] = None,
        related_milestone_id: Optional[UUID] = None,
        related_budget_item_id: Optional[UUID] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        affected_fields: Optional[List[str]] = None
    ):
        """Log activity for audit trail"""
        try:
            activity_log = CampaignActivityLog(
                campaign_id=campaign_id,
                activity_type=activity_type,
                activity_description=activity_description,
                performed_by_user_id=performed_by_user_id,
                performed_by_profile_id=performed_by_profile_id,
                related_deliverable_id=related_deliverable_id,
                related_collaborator_id=related_collaborator_id,
                related_milestone_id=related_milestone_id,
                related_budget_item_id=related_budget_item_id,
                old_values=old_values or {},
                new_values=new_values or {},
                affected_fields=affected_fields or []
            )
            db.add(activity_log)
            # Don't commit here - let the calling method handle it
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
    
    # ===============================================================================
    # CAMPAIGN MANAGEMENT
    # ===============================================================================
    
    async def create_campaign(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new enhanced campaign"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Create new campaign with enhanced fields
            new_campaign = Campaign(
                user_id=database_user_id,
                name=campaign_data['name'],
                description=campaign_data.get('description'),
                logo_url=campaign_data.get('logo_url'),
                
                # Enhanced fields
                campaign_status=campaign_data.get('campaign_status', 'draft'),
                campaign_type=campaign_data.get('campaign_type', 'influencer_marketing'),
                campaign_goals=campaign_data.get('campaign_goals', []),
                kpi_targets=campaign_data.get('kpi_targets', {}),
                target_audience=campaign_data.get('target_audience', {}),
                brand_guidelines=campaign_data.get('brand_guidelines'),
                content_requirements=campaign_data.get('content_requirements', {}),
                approval_workflow=campaign_data.get('approval_workflow', {}),
                
                # Budget
                budget_allocated=campaign_data.get('budget_allocated', 0),
                budget=campaign_data.get('budget'),  # Legacy support
                
                # Performance expectations
                expected_reach=campaign_data.get('expected_reach', 0),
                expected_engagement=campaign_data.get('expected_engagement', 0),
                
                # Timeline
                campaign_start_date=campaign_data.get('campaign_start_date'),
                campaign_end_date=campaign_data.get('campaign_end_date'),
                deliverables_due_date=campaign_data.get('deliverables_due_date'),
                start_date=campaign_data.get('start_date'),  # Legacy support
                end_date=campaign_data.get('end_date')       # Legacy support
            )
            
            db.add(new_campaign)
            await db.commit()
            await db.refresh(new_campaign)
            
            # Log activity
            await self._log_activity(
                db, new_campaign.id, "campaign_created", 
                f"Created campaign '{campaign_data['name']}'",
                performed_by_user_id=database_user_id
            )
            await db.commit()
            
            return {
                "id": str(new_campaign.id),
                "name": new_campaign.name,
                "campaign_status": new_campaign.campaign_status,
                "campaign_type": new_campaign.campaign_type,
                "created_at": new_campaign.created_at
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating campaign: {e}")
            raise
    
    async def get_user_campaigns(
        self, 
        db: AsyncSession, 
        user_id: UUID,
        campaign_status: Optional[str] = None,
        campaign_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get all campaigns for a user with pagination"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Build base query - include owned campaigns and collaborations
            query = select(Campaign).where(
                or_(
                    Campaign.user_id == database_user_id,
                    Campaign.id.in_(
                        select(CampaignCollaborator.campaign_id).where(
                            and_(
                                CampaignCollaborator.collaborator_user_id == database_user_id,
                                CampaignCollaborator.collaboration_status == 'active'
                            )
                        )
                    )
                )
            )
            
            # Add filters
            if campaign_status:
                query = query.where(Campaign.campaign_status == campaign_status)
            if campaign_type:
                query = query.where(Campaign.campaign_type == campaign_type)
            
            # Add sorting
            query = query.order_by(Campaign.created_at.desc())
            
            # Get total count
            count_query = select(func.count(Campaign.id)).where(
                or_(
                    Campaign.user_id == database_user_id,
                    Campaign.id.in_(
                        select(CampaignCollaborator.campaign_id).where(
                            and_(
                                CampaignCollaborator.collaborator_user_id == database_user_id,
                                CampaignCollaborator.collaboration_status == 'active'
                            )
                        )
                    )
                )
            )
            
            if campaign_status:
                count_query = count_query.where(Campaign.campaign_status == campaign_status)
            if campaign_type:
                count_query = count_query.where(Campaign.campaign_type == campaign_type)
            
            total_result = await db.execute(count_query)
            total_items = total_result.scalar() or 0
            
            # Apply pagination
            query = query.offset(offset).limit(page_size)
            
            # Execute query
            result = await db.execute(query)
            campaigns = result.scalars().all()
            
            # Convert to response format with summary data
            campaign_data = []
            for campaign in campaigns:
                # Get summary metrics using database function
                summary_result = await db.execute(
                    text("SELECT get_campaign_summary(:campaign_id)"),
                    {"campaign_id": str(campaign.id)}
                )
                summary = summary_result.scalar() or {}
                
                campaign_dict = {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "description": campaign.description,
                    "campaign_status": campaign.campaign_status,
                    "campaign_type": campaign.campaign_type,
                    "budget_allocated": campaign.budget_allocated,
                    "budget_spent": campaign.budget_spent,
                    "completion_percentage": campaign.completion_percentage,
                    "quality_score": float(campaign.quality_score) if campaign.quality_score else 0,
                    "campaign_start_date": campaign.campaign_start_date,
                    "campaign_end_date": campaign.campaign_end_date,
                    "created_at": campaign.created_at,
                    "updated_at": campaign.updated_at,
                    "summary": summary
                }
                campaign_data.append(campaign_dict)
            
            # Calculate pagination
            total_pages = (total_items + page_size - 1) // page_size
            
            return {
                "campaigns": campaign_data,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_items": total_items,
                    "items_per_page": page_size,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user campaigns: {e}")
            raise
    
    async def get_campaign_details(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get detailed campaign information"""
        try:
            # Check permission
            if not await self._check_campaign_permission(db, user_id, campaign_id, "view"):
                raise ValueError("You don't have permission to view this campaign")
            
            # Get campaign with relationships
            query = select(Campaign).where(Campaign.id == campaign_id).options(
                selectinload(Campaign.deliverables),
                selectinload(Campaign.collaborators),
                selectinload(Campaign.milestones),
                selectinload(Campaign.campaign_posts).selectinload(CampaignPost.post),
                selectinload(Campaign.campaign_profiles).selectinload(CampaignProfile.profile)
            )
            
            result = await db.execute(query)
            campaign = result.scalar_one_or_none()
            
            if not campaign:
                return None
            
            # Get summary metrics
            summary_result = await db.execute(
                text("SELECT get_campaign_summary(:campaign_id)"),
                {"campaign_id": str(campaign_id)}
            )
            summary = summary_result.scalar() or {}
            
            # Convert to response format
            return {
                "id": str(campaign.id),
                "name": campaign.name,
                "description": campaign.description,
                "logo_url": campaign.logo_url,
                "campaign_status": campaign.campaign_status,
                "campaign_type": campaign.campaign_type,
                "campaign_goals": campaign.campaign_goals,
                "kpi_targets": campaign.kpi_targets,
                "target_audience": campaign.target_audience,
                "brand_guidelines": campaign.brand_guidelines,
                "content_requirements": campaign.content_requirements,
                "approval_workflow": campaign.approval_workflow,
                "budget_allocated": campaign.budget_allocated,
                "budget_spent": campaign.budget_spent,
                "expected_reach": campaign.expected_reach,
                "actual_reach": campaign.actual_reach,
                "expected_engagement": campaign.expected_engagement,
                "actual_engagement": campaign.actual_engagement,
                "completion_percentage": campaign.completion_percentage,
                "quality_score": float(campaign.quality_score) if campaign.quality_score else 0,
                "roi_percentage": float(campaign.roi_percentage) if campaign.roi_percentage else 0,
                "campaign_start_date": campaign.campaign_start_date,
                "campaign_end_date": campaign.campaign_end_date,
                "deliverables_due_date": campaign.deliverables_due_date,
                "published_at": campaign.published_at,
                "completed_at": campaign.completed_at,
                "created_at": campaign.created_at,
                "updated_at": campaign.updated_at,
                "summary": summary,
                "deliverables": [
                    {
                        "id": str(deliverable.id),
                        "deliverable_title": deliverable.deliverable_title,
                        "deliverable_type": deliverable.deliverable_type,
                        "approval_status": deliverable.approval_status,
                        "due_date": deliverable.due_date,
                        "submitted_at": deliverable.submitted_at,
                        "quality_rating": deliverable.quality_rating
                    } for deliverable in campaign.deliverables
                ],
                "collaborators": [
                    {
                        "id": str(collab.id),
                        "role": collab.role,
                        "collaboration_type": collab.collaboration_type,
                        "collaboration_status": collab.collaboration_status,
                        "deliverables_assigned": collab.deliverables_assigned,
                        "deliverables_completed": collab.deliverables_completed,
                        "average_quality_rating": float(collab.average_quality_rating) if collab.average_quality_rating else 0
                    } for collab in campaign.collaborators
                ],
                "milestones": [
                    {
                        "id": str(milestone.id),
                        "milestone_title": milestone.milestone_title,
                        "milestone_type": milestone.milestone_type,
                        "milestone_status": milestone.milestone_status,
                        "completion_percentage": milestone.completion_percentage,
                        "target_date": milestone.target_date,
                        "actual_date": milestone.actual_date
                    } for milestone in campaign.milestones
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign details: {e}")
            raise
    
    # ===============================================================================
    # DELIVERABLE MANAGEMENT
    # ===============================================================================
    
    async def create_deliverable(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID,
        deliverable_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new deliverable for a campaign"""
        try:
            # Check permission
            if not await self._check_campaign_permission(db, user_id, campaign_id, "edit"):
                raise ValueError("You don't have permission to create deliverables for this campaign")
            
            # Create deliverable
            deliverable = CampaignDeliverable(
                campaign_id=campaign_id,
                assigned_by_user_id=user_id,
                deliverable_title=deliverable_data['deliverable_title'],
                deliverable_description=deliverable_data.get('deliverable_description'),
                deliverable_type=deliverable_data['deliverable_type'],
                assigned_to_profile_id=deliverable_data.get('assigned_to_profile_id'),
                content_specifications=deliverable_data.get('content_specifications', {}),
                required_hashtags=deliverable_data.get('required_hashtags', []),
                required_mentions=deliverable_data.get('required_mentions', []),
                required_links=deliverable_data.get('required_links', []),
                content_guidelines=deliverable_data.get('content_guidelines'),
                due_date=deliverable_data.get('due_date'),
                approval_deadline=deliverable_data.get('approval_deadline'),
                compensation_amount_usd=deliverable_data.get('compensation_amount_usd', 0)
            )
            
            db.add(deliverable)
            await db.commit()
            await db.refresh(deliverable)
            
            # Update campaign completion percentage
            await db.execute(text("SELECT calculate_campaign_completion(:campaign_id)"), {"campaign_id": str(campaign_id)})
            
            # Log activity
            await self._log_activity(
                db, campaign_id, "deliverable_created", 
                f"Created deliverable '{deliverable_data['deliverable_title']}'",
                performed_by_user_id=user_id,
                related_deliverable_id=deliverable.id
            )
            await db.commit()
            
            return {
                "id": str(deliverable.id),
                "deliverable_title": deliverable.deliverable_title,
                "deliverable_type": deliverable.deliverable_type,
                "approval_status": deliverable.approval_status,
                "due_date": deliverable.due_date,
                "created_at": deliverable.created_at
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating deliverable: {e}")
            raise
    
    async def submit_deliverable(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        deliverable_id: UUID,
        submission_data: Dict[str, Any]
    ) -> bool:
        """Submit content for a deliverable (typically by influencer/creator)"""
        try:
            # Get deliverable
            query = select(CampaignDeliverable).where(CampaignDeliverable.id == deliverable_id)
            result = await db.execute(query)
            deliverable = result.scalar_one_or_none()
            
            if not deliverable:
                raise ValueError("Deliverable not found")
            
            # Check permission (assigned profile or campaign collaborator)
            if not await self._check_campaign_permission(db, user_id, deliverable.campaign_id, "edit"):
                raise ValueError("You don't have permission to submit this deliverable")
            
            # Update deliverable with submission
            deliverable.submitted_content_url = submission_data.get('submitted_content_url')
            deliverable.submitted_content_text = submission_data.get('submitted_content_text')
            deliverable.submitted_media_urls = submission_data.get('submitted_media_urls', [])
            deliverable.submitted_notes = submission_data.get('submitted_notes')
            deliverable.submitted_at = datetime.now(timezone.utc)
            deliverable.approval_status = 'submitted'
            
            await db.commit()
            
            # Update campaign completion percentage
            await db.execute(text("SELECT calculate_campaign_completion(:campaign_id)"), {"campaign_id": str(deliverable.campaign_id)})
            
            # Log activity
            await self._log_activity(
                db, deliverable.campaign_id, "deliverable_submitted", 
                f"Submitted content for deliverable '{deliverable.deliverable_title}'",
                performed_by_user_id=user_id,
                related_deliverable_id=deliverable.id
            )
            await db.commit()
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error submitting deliverable: {e}")
            raise
    
    async def approve_deliverable(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        deliverable_id: UUID,
        approval_data: Dict[str, Any]
    ) -> bool:
        """Approve or reject a submitted deliverable"""
        try:
            # Get deliverable
            query = select(CampaignDeliverable).where(CampaignDeliverable.id == deliverable_id)
            result = await db.execute(query)
            deliverable = result.scalar_one_or_none()
            
            if not deliverable:
                raise ValueError("Deliverable not found")
            
            # Check permission
            if not await self._check_campaign_permission(db, user_id, deliverable.campaign_id, "approve"):
                raise ValueError("You don't have permission to approve deliverables for this campaign")
            
            # Update deliverable approval
            deliverable.approval_status = approval_data['approval_status']  # 'approved', 'rejected', 'revision_requested'
            deliverable.reviewed_by_user_id = user_id
            deliverable.reviewed_at = datetime.now(timezone.utc)
            deliverable.review_notes = approval_data.get('review_notes')
            deliverable.quality_rating = approval_data.get('quality_rating')
            deliverable.client_feedback = approval_data.get('client_feedback')
            
            # If approved and published, update publication details
            if approval_data['approval_status'] == 'published':
                deliverable.published_at = approval_data.get('published_at', datetime.now(timezone.utc))
                deliverable.published_url = approval_data.get('published_url')
                deliverable.published_platform = approval_data.get('published_platform')
            
            await db.commit()
            
            # Update campaign completion percentage
            await db.execute(text("SELECT calculate_campaign_completion(:campaign_id)"), {"campaign_id": str(deliverable.campaign_id)})
            
            # Log activity
            await self._log_activity(
                db, deliverable.campaign_id, "deliverable_approved", 
                f"{'Approved' if approval_data['approval_status'] == 'approved' else 'Updated'} deliverable '{deliverable.deliverable_title}'",
                performed_by_user_id=user_id,
                related_deliverable_id=deliverable.id
            )
            await db.commit()
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error approving deliverable: {e}")
            raise
    
    # ===============================================================================
    # COLLABORATION MANAGEMENT
    # ===============================================================================
    
    async def add_collaborator(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID,
        collaborator_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a collaborator to a campaign"""
        try:
            # Check permission (only campaign owner or managers)
            if not await self._check_campaign_permission(db, user_id, campaign_id, "edit"):
                raise ValueError("You don't have permission to add collaborators to this campaign")
            
            # Create collaboration
            collaboration = CampaignCollaborator(
                campaign_id=campaign_id,
                collaborator_user_id=collaborator_data.get('collaborator_user_id'),
                collaborator_profile_id=collaborator_data.get('collaborator_profile_id'),
                role=collaborator_data['role'],
                collaboration_type=collaborator_data.get('collaboration_type', 'contributor'),
                permissions=collaborator_data.get('permissions', []),
                can_create_deliverables=collaborator_data.get('can_create_deliverables', False),
                can_approve_content=collaborator_data.get('can_approve_content', False),
                can_view_analytics=collaborator_data.get('can_view_analytics', False),
                can_manage_budget=collaborator_data.get('can_manage_budget', False),
                compensation_type=collaborator_data.get('compensation_type', 'fixed'),
                compensation_amount_usd=collaborator_data.get('compensation_amount_usd', 0),
                compensation_terms=collaborator_data.get('compensation_terms', {})
            )
            
            db.add(collaboration)
            await db.commit()
            await db.refresh(collaboration)
            
            # Log activity
            await self._log_activity(
                db, campaign_id, "collaborator_added", 
                f"Added collaborator with role '{collaborator_data['role']}'",
                performed_by_user_id=user_id,
                related_collaborator_id=collaboration.id
            )
            await db.commit()
            
            return {
                "id": str(collaboration.id),
                "role": collaboration.role,
                "collaboration_type": collaboration.collaboration_type,
                "collaboration_status": collaboration.collaboration_status,
                "invited_at": collaboration.invited_at
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error adding collaborator: {e}")
            raise
    
    # ===============================================================================
    # CAMPAIGN ANALYTICS AND PERFORMANCE
    # ===============================================================================
    
    async def get_campaign_analytics(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID,
        date_range: int = 30
    ) -> Dict[str, Any]:
        """Get campaign analytics and performance metrics"""
        try:
            # Check permission
            if not await self._check_campaign_permission(db, user_id, campaign_id, "analytics"):
                raise ValueError("You don't have permission to view analytics for this campaign")
            
            # Get recent metrics
            start_date = date.today() - timedelta(days=date_range)
            
            metrics_query = select(CampaignPerformanceMetrics).where(
                and_(
                    CampaignPerformanceMetrics.campaign_id == campaign_id,
                    CampaignPerformanceMetrics.date_recorded >= start_date
                )
            ).order_by(CampaignPerformanceMetrics.date_recorded.desc())
            
            metrics_result = await db.execute(metrics_query)
            metrics = metrics_result.scalars().all()
            
            # Get campaign summary
            summary_result = await db.execute(
                text("SELECT get_campaign_summary(:campaign_id)"),
                {"campaign_id": str(campaign_id)}
            )
            summary = summary_result.scalar() or {}
            
            # Calculate aggregate metrics
            total_reach = sum(m.unique_reach for m in metrics) if metrics else 0
            total_engagement = sum(m.total_engagement for m in metrics) if metrics else 0
            total_impressions = sum(m.total_impressions for m in metrics) if metrics else 0
            avg_engagement_rate = sum(float(m.engagement_rate) for m in metrics) / len(metrics) if metrics else 0
            total_conversions = sum(m.purchases for m in metrics) if metrics else 0
            total_revenue = sum(float(m.revenue_generated) for m in metrics) if metrics else 0
            
            return {
                "campaign_id": str(campaign_id),
                "summary": summary,
                "aggregate_metrics": {
                    "total_reach": total_reach,
                    "total_engagement": total_engagement,
                    "total_impressions": total_impressions,
                    "average_engagement_rate": avg_engagement_rate,
                    "total_conversions": total_conversions,
                    "total_revenue": total_revenue,
                    "return_on_investment": float(metrics[0].return_on_investment) if metrics else 0
                },
                "daily_metrics": [
                    {
                        "date": m.date_recorded,
                        "reach": m.unique_reach,
                        "impressions": m.total_impressions,
                        "engagement": m.total_engagement,
                        "engagement_rate": float(m.engagement_rate),
                        "clicks": m.clicks_count,
                        "conversions": m.purchases,
                        "revenue": float(m.revenue_generated),
                        "roi": float(m.return_on_investment)
                    } for m in metrics
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign analytics: {e}")
            raise
    
    async def record_performance_metrics(
        self, 
        db: AsyncSession, 
        campaign_id: UUID, 
        metrics_data: Dict[str, Any]
    ) -> bool:
        """Record daily performance metrics for a campaign"""
        try:
            # Create or update performance metrics record
            date_recorded = metrics_data.get('date_recorded', date.today())
            metric_period = metrics_data.get('metric_period', 'daily')
            
            # Check if record already exists
            existing_query = select(CampaignPerformanceMetrics).where(
                and_(
                    CampaignPerformanceMetrics.campaign_id == campaign_id,
                    CampaignPerformanceMetrics.date_recorded == date_recorded,
                    CampaignPerformanceMetrics.metric_period == metric_period
                )
            )
            existing_result = await db.execute(existing_query)
            existing_metrics = existing_result.scalar_one_or_none()
            
            if existing_metrics:
                # Update existing record
                for field, value in metrics_data.items():
                    if hasattr(existing_metrics, field) and field not in ['date_recorded', 'metric_period']:
                        setattr(existing_metrics, field, value)
            else:
                # Create new record
                metrics = CampaignPerformanceMetrics(
                    campaign_id=campaign_id,
                    date_recorded=date_recorded,
                    metric_period=metric_period,
                    **{k: v for k, v in metrics_data.items() if k not in ['date_recorded', 'metric_period']}
                )
                db.add(metrics)
            
            await db.commit()
            
            # Update campaign actual metrics
            await db.execute(
                update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(
                    actual_reach=metrics_data.get('unique_reach', 0),
                    actual_engagement=metrics_data.get('total_engagement', 0)
                )
            )
            await db.commit()
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error recording performance metrics: {e}")
            raise
    
    # ===============================================================================
    # BUDGET MANAGEMENT
    # ===============================================================================
    
    async def create_budget_item(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        campaign_id: UUID,
        budget_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a budget tracking item for a campaign"""
        try:
            # Check permission
            if not await self._check_campaign_permission(db, user_id, campaign_id, "budget"):
                raise ValueError("You don't have permission to manage budget for this campaign")
            
            # Create budget item
            budget_item = CampaignBudgetTracking(
                campaign_id=campaign_id,
                budget_item_name=budget_data['budget_item_name'],
                budget_category=budget_data['budget_category'],
                description=budget_data.get('description'),
                budgeted_amount_usd=budget_data['budgeted_amount_usd'],
                actual_spent_usd=budget_data.get('actual_spent_usd', 0),
                budget_period_start=budget_data.get('budget_period_start'),
                budget_period_end=budget_data.get('budget_period_end'),
                budget_status=budget_data.get('budget_status', 'allocated'),
                related_deliverable_id=budget_data.get('related_deliverable_id'),
                related_collaborator_id=budget_data.get('related_collaborator_id'),
                related_milestone_id=budget_data.get('related_milestone_id'),
                vendor_name=budget_data.get('vendor_name'),
                vendor_contact_info=budget_data.get('vendor_contact_info', {})
            )
            
            db.add(budget_item)
            await db.commit()
            await db.refresh(budget_item)
            
            # Update campaign budget spent (handled by trigger, but we can also call manually)
            await db.execute(text("SELECT update_campaign_budget_spent(:campaign_id)"), {"campaign_id": str(campaign_id)})
            
            # Log activity
            await self._log_activity(
                db, campaign_id, "budget_item_created", 
                f"Created budget item '{budget_data['budget_item_name']}' (${budget_data['budgeted_amount_usd']})",
                performed_by_user_id=user_id,
                related_budget_item_id=budget_item.id
            )
            await db.commit()
            
            return {
                "id": str(budget_item.id),
                "budget_item_name": budget_item.budget_item_name,
                "budget_category": budget_item.budget_category,
                "budgeted_amount_usd": budget_item.budgeted_amount_usd,
                "actual_spent_usd": budget_item.actual_spent_usd,
                "budget_status": budget_item.budget_status,
                "created_at": budget_item.created_at
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating budget item: {e}")
            raise

# Create service instance
campaigns_service = CampaignsService()