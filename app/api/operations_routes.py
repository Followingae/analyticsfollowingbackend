"""
Campaign Operations OS API Routes
Main routes for campaign management system
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from uuid import UUID
import logging

from app.database.connection import get_db
from app.database.operations_models import (
    Campaign, Workstream, Deliverable, Concept,
    Event, ProductionBatch, Assignment, Payout, ActivityLog
)
from app.models.operations_models import (
    CampaignCreate, CampaignUpdate, CampaignResponse, CampaignOverview,
    WorkstreamCreate, WorkstreamUpdate, WorkstreamResponse, WorkstreamListResponse,
    DeliverableCreate, DeliverableUpdate, DeliverableResponse, DeliverableListResponse,
    ConceptCreate, ConceptUpdate, ConceptApproval, ConceptResponse, ConceptListResponse,
    EventCreate, EventResponse, EventListResponse,
    OperationsAccess, OperationsPermissions,
    BulkDeliverableOperation, ProductionBatch as ProductionBatchModel,
    PayoutRequest, PayoutResponse, CampaignSettings,
    ActivityEntry, ActivityListResponse
)
from app.middleware.operations_auth import (
    get_operations_access, require_superadmin, require_operations_access,
    require_permission, filter_response_by_role, add_access_metadata,
    filter_activities_by_visibility, check_campaign_access,
    OperationsPermissionError
)

router = APIRouter(tags=["Operations OS"])
logger = logging.getLogger(__name__)


# ============= PERMISSIONS CHECK =============
@router.get("/permissions")
async def get_user_permissions(
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> OperationsAccess:
    """Check user's operations permissions"""
    return operations_access


# ============= CAMPAIGNS =============
@router.get("/campaigns")
async def list_campaigns(
    brand: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> Dict[str, Any]:
    """List all campaigns user has access to"""
    try:
        # Build query
        query = select(Campaign)

        # Superadmins see all, others see only their team's campaigns
        if operations_access.role not in ['super_admin', 'superadmin']:
            if operations_access.team_id:
                query = query.where(Campaign.team_id == UUID(operations_access.team_id))
            else:
                # No team, no campaigns
                return {
                    "campaigns": [],
                    "total": 0,
                    "page": page,
                    "has_more": False,
                    "_access": {
                        "user_role": operations_access.role,
                        "can_create_campaign": False,
                        "can_view_all_campaigns": False
                    }
                }

        # Apply filters
        if brand:
            query = query.where(Campaign.brand_name.ilike(f"%{brand}%"))
        if status:
            query = query.where(Campaign.status == status)
        if search:
            query = query.where(
                or_(
                    Campaign.campaign_name.ilike(f"%{search}%"),
                    Campaign.description.ilike(f"%{search}%")
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        query = query.order_by(desc(Campaign.created_at))

        result = await db.execute(query)
        campaigns = result.scalars().all()

        # Build response
        campaign_list = []
        for campaign in campaigns:
            # Get counts
            deliverables_count = await db.execute(
                select(func.count()).select_from(Deliverable)
                .where(Deliverable.campaign_id == campaign.id)
            )
            total_deliverables = deliverables_count.scalar()

            completed_count = await db.execute(
                select(func.count()).select_from(Deliverable)
                .where(and_(
                    Deliverable.campaign_id == campaign.id,
                    Deliverable.status == 'POSTED'
                ))
            )
            completed_deliverables = completed_count.scalar()

            campaign_data = {
                "id": str(campaign.id),
                "brand_id": str(campaign.brand_id),
                "brand_name": campaign.brand_name,
                "campaign_name": campaign.campaign_name,
                "start_date": campaign.start_date.isoformat(),
                "end_date": campaign.end_date.isoformat(),
                "status": campaign.status.value,
                "total_deliverables": total_deliverables,
                "completed_deliverables": completed_deliverables,
                "pending_approvals": 0,  # TODO: Calculate
                "overdue_posts": 0,  # TODO: Calculate
                "upcoming_shoots": 0,  # TODO: Calculate
                "created_at": campaign.created_at.isoformat(),
                "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else campaign.created_at.isoformat()
            }

            # Add metadata for superadmins
            if operations_access.role in ['super_admin', 'superadmin']:
                campaign_data["metadata"] = {
                    "total_workstreams": len(campaign.workstreams),
                    "total_events": len(campaign.events),
                    "total_budget": sum(w.budget_allocated or 0 for w in campaign.workstreams)
                }

            campaign_list.append(filter_response_by_role(campaign_data, operations_access.role))

        return {
            "campaigns": campaign_list,
            "total": total,
            "page": page,
            "has_more": (offset + limit) < total,
            "_access": {
                "user_role": operations_access.role,
                "can_create_campaign": operations_access.operations_access.create_workstreams,
                "can_view_all_campaigns": operations_access.role in ['super_admin', 'superadmin']
            }
        }

    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> Dict[str, Any]:
    """Get campaign details"""
    try:
        # Check campaign access
        if not check_campaign_access(str(campaign_id), operations_access, "viewer"):
            raise OperationsPermissionError(
                detail="You don't have access to this campaign",
                user_role=operations_access.role
            )

        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        response = {
            "id": str(campaign.id),
            "brand_id": str(campaign.brand_id),
            "brand_name": campaign.brand_name,
            "campaign_name": campaign.campaign_name,
            "description": campaign.description,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
            "status": campaign.status.value,
            "created_at": campaign.created_at.isoformat(),
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else campaign.created_at.isoformat(),
            "created_by": str(campaign.created_by),
            "team_id": str(campaign.team_id),
            "_access": {
                "user_role": operations_access.role,
                "is_owner": str(campaign.created_by) == operations_access.user_id,
                "can_edit": operations_access.operations_access.create_workstreams,
                "can_delete": operations_access.operations_access.bulk_operations
            }
        }

        # Add settings for superadmins only
        if operations_access.role in ['super_admin', 'superadmin']:
            response["settings"] = campaign.settings or {}

        return filter_response_by_role(response, operations_access.role)

    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/overview")
async def get_campaign_overview(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> CampaignOverview:
    """Get campaign overview dashboard data"""
    try:
        # Check campaign access
        if not check_campaign_access(str(campaign_id), operations_access, "viewer"):
            raise OperationsPermissionError(
                detail="You don't have access to this campaign",
                user_role=operations_access.role
            )

        # Get campaign
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Calculate summary
        deliverables = await db.execute(
            select(Deliverable).where(Deliverable.campaign_id == campaign_id)
        )
        all_deliverables = deliverables.scalars().all()

        summary = {
            "total_workstreams": len(campaign.workstreams),
            "total_deliverables": len(all_deliverables),
            "completed_deliverables": sum(1 for d in all_deliverables if d.status == 'POSTED'),
            "in_production": sum(1 for d in all_deliverables if d.status in ['IN_PRODUCTION', 'EDITING']),
            "pending_approval": sum(1 for d in all_deliverables if d.status == 'AWAITING_APPROVAL'),
            "overdue": sum(1 for d in all_deliverables if d.due_date and d.due_date < date.today() and d.status != 'POSTED'),
            "completion_percentage": (sum(1 for d in all_deliverables if d.status == 'POSTED') / max(len(all_deliverables), 1)) * 100
        }

        # This week's items
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Get shoots this week
        shoots_query = await db.execute(
            select(ProductionBatch)
            .where(and_(
                ProductionBatch.campaign_id == campaign_id,
                ProductionBatch.date >= week_start,
                ProductionBatch.date <= week_end
            ))
        )
        shoots = shoots_query.scalars().all()

        this_week = {
            "shoots": [
                {
                    "date": shoot.date.isoformat(),
                    "location": shoot.location,
                    "deliverables_count": len(shoot.deliverables),
                    "workstream_id": str(shoot.workstream_id),
                    "workstream_name": "Production"  # TODO: Get actual name
                }
                for shoot in shoots
            ],
            "deadlines": [],  # TODO: Calculate deadlines
            "events": []  # TODO: Get events
        }

        # Blockers
        blockers = {}
        if operations_access.role in ['super_admin', 'superadmin']:
            blockers = {
                "missing_scripts": sum(1 for d in all_deliverables if not d.concept_id),
                "pending_approvals": summary["pending_approval"],
                "missing_frameio": sum(1 for d in all_deliverables if not d.assets),
                "overdue_deliverables": summary["overdue"],
                "missing_assignments": sum(1 for d in all_deliverables if not d.assignment_id)
            }
        else:
            # Client view
            blockers = {
                "pending_your_approval": summary["pending_approval"]
            }

        # Recent activity
        activities_query = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.campaign_id == campaign_id)
            .order_by(desc(ActivityLog.timestamp))
            .limit(10)
        )
        activities = activities_query.scalars().all()

        recent_activity = []
        for activity in activities:
            # Filter based on visibility
            if not operations_access.role in ['super_admin', 'superadmin'] and not activity.is_client_visible:
                continue

            recent_activity.append({
                "id": str(activity.id),
                "type": activity.type,
                "action": activity.action,
                "actor_id": str(activity.actor_id),
                "actor_name": activity.actor_name,
                "actor_role": activity.actor_role,
                "target_type": "deliverable" if activity.deliverable_id else "workstream" if activity.workstream_id else "campaign",
                "target_id": str(activity.deliverable_id or activity.workstream_id or activity.campaign_id),
                "target_name": "",  # TODO: Get actual name
                "timestamp": activity.timestamp.isoformat(),
                "is_client_visible": activity.is_client_visible
            })

        # Quick stats
        quick_stats = {
            "creators_engaged": 0,  # TODO: Calculate
            "content_pieces": len(all_deliverables)
        }

        if operations_access.role in ['super_admin', 'superadmin']:
            quick_stats["total_budget"] = sum(w.budget_allocated or 0 for w in campaign.workstreams)
            quick_stats["spent_budget"] = sum(w.budget_spent or 0 for w in campaign.workstreams)

        return CampaignOverview(
            campaign_id=str(campaign_id),
            summary=summary,
            this_week=this_week,
            blockers=blockers,
            recent_activity=recent_activity,
            quick_stats=quick_stats,
            _access={
                "user_role": operations_access.role,
                "view_mode": "superadmin" if operations_access.role in ['super_admin', 'superadmin'] else "client"
            }
        )

    except Exception as e:
        logger.error(f"Error getting campaign overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns", dependencies=[Depends(require_superadmin)])
async def create_campaign(
    campaign: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> CampaignResponse:
    """Create new campaign (SUPERADMIN ONLY)"""
    try:
        new_campaign = Campaign(
            brand_id=UUID(campaign.brand_id),
            brand_name=campaign.brand_name,
            campaign_name=campaign.campaign_name,
            description=campaign.description,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            status=campaign.status,
            created_by=UUID(operations_access.user_id),
            team_id=UUID(operations_access.team_id) if operations_access.team_id else None,
            settings={}
        )

        db.add(new_campaign)
        await db.commit()
        await db.refresh(new_campaign)

        # Log activity
        activity = ActivityLog(
            campaign_id=new_campaign.id,
            type="campaign_created",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"Created campaign '{campaign.campaign_name}'",
            details={},
            is_client_visible=True
        )
        db.add(activity)
        await db.commit()

        return CampaignResponse(
            id=str(new_campaign.id),
            brand_id=str(new_campaign.brand_id),
            brand_name=new_campaign.brand_name,
            campaign_name=new_campaign.campaign_name,
            description=new_campaign.description,
            start_date=new_campaign.start_date,
            end_date=new_campaign.end_date,
            status=new_campaign.status.value,
            total_deliverables=0,
            completed_deliverables=0,
            pending_approvals=0,
            overdue_posts=0,
            upcoming_shoots=0,
            created_at=new_campaign.created_at,
            updated_at=new_campaign.updated_at or new_campaign.created_at,
            _access={
                "user_role": operations_access.role,
                "created_by_role": operations_access.role
            }
        )

    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============= WORKSTREAMS =============
# Continued in next part...