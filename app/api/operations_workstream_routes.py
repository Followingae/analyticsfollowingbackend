"""
Campaign Operations OS - Workstream & Deliverables Routes
Routes for workstream and deliverables management
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
import logging
import json

from app.database.connection import get_db
from app.database.operations_models import (
    Campaign, Workstream, Deliverable, Concept,
    Assignment, ProductionBatch, ActivityLog
)
from app.models.operations_models import (
    WorkstreamCreate, WorkstreamUpdate, WorkstreamResponse, WorkstreamListResponse,
    DeliverableCreate, DeliverableUpdate, DeliverableResponse, DeliverableListResponse,
    BulkDeliverableOperation, DeliverableStatus, AssetInfo, PostingProof,
    OperationsAccess
)
from app.middleware.operations_auth import (
    get_operations_access, require_superadmin, require_operations_access,
    filter_response_by_role, check_campaign_access,
    OperationsPermissionError
)

router = APIRouter(tags=["Operations - Workstreams"])
logger = logging.getLogger(__name__)


# ============= WORKSTREAMS =============
@router.get("/campaigns/{campaign_id}/workstreams")
async def list_workstreams(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> WorkstreamListResponse:
    """List all workstreams for a campaign"""
    try:
        # Check campaign access
        if not check_campaign_access(str(campaign_id), operations_access, "viewer"):
            raise OperationsPermissionError(
                detail="You don't have access to this campaign",
                user_role=operations_access.role
            )

        result = await db.execute(
            select(Workstream)
            .where(Workstream.campaign_id == campaign_id)
            .order_by(Workstream.created_at)
        )
        workstreams = result.scalars().all()

        workstream_list = []
        for workstream in workstreams:
            # Get deliverables count and stats
            deliverables_result = await db.execute(
                select(Deliverable).where(Deliverable.workstream_id == workstream.id)
            )
            deliverables = deliverables_result.scalars().all()

            completed = sum(1 for d in deliverables if d.status == DeliverableStatus.POSTED)
            pending_approvals = sum(1 for d in deliverables if d.status == DeliverableStatus.AWAITING_APPROVAL)

            # Find next milestone
            next_milestone = None
            upcoming_dates = []

            # Check for upcoming shoots
            shoots_result = await db.execute(
                select(ProductionBatch)
                .where(and_(
                    ProductionBatch.workstream_id == workstream.id,
                    ProductionBatch.date >= date.today()
                ))
                .order_by(ProductionBatch.date)
                .limit(1)
            )
            next_shoot = shoots_result.scalar_one_or_none()
            if next_shoot:
                upcoming_dates.append({
                    "type": "shoot",
                    "date": next_shoot.date,
                    "description": f"Shoot at {next_shoot.location}"
                })

            # Check for upcoming deadlines
            for d in deliverables:
                if d.due_date and d.due_date >= date.today() and d.status != DeliverableStatus.POSTED:
                    upcoming_dates.append({
                        "type": "deadline",
                        "date": d.due_date,
                        "description": f"'{d.title}' due"
                    })

            if upcoming_dates:
                next_milestone = min(upcoming_dates, key=lambda x: x['date'])

            workstream_data = {
                "id": str(workstream.id),
                "campaign_id": str(workstream.campaign_id),
                "type": workstream.type,
                "name": workstream.name,
                "description": workstream.description,
                "status": workstream.status.value,
                "deliverables_count": len(deliverables),
                "completion_percentage": (completed / max(len(deliverables), 1)) * 100,
                "pending_approvals": pending_approvals,
                "next_milestone": next_milestone,
                "created_at": workstream.created_at.isoformat(),
                "updated_at": workstream.updated_at.isoformat() if workstream.updated_at else workstream.created_at.isoformat(),
                "created_by": str(workstream.created_by)
            }

            # Add superadmin-only fields
            if operations_access.role in ['super_admin', 'superadmin']:
                workstream_data["budget_allocated"] = workstream.budget_allocated
                workstream_data["budget_spent"] = workstream.budget_spent
                workstream_data["internal_notes"] = workstream.internal_notes

            workstream_list.append(filter_response_by_role(workstream_data, operations_access.role))

        return WorkstreamListResponse(
            workstreams=workstream_list,
            _access={
                "user_role": operations_access.role,
                "can_create": operations_access.operations_access.create_workstreams,
                "can_edit": operations_access.operations_access.create_workstreams,
                "can_delete": operations_access.operations_access.bulk_operations
            }
        )

    except Exception as e:
        logger.error(f"Error listing workstreams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/workstreams", dependencies=[Depends(require_superadmin)])
async def create_workstream(
    campaign_id: UUID,
    workstream: WorkstreamCreate,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> WorkstreamResponse:
    """Create new workstream (SUPERADMIN ONLY)"""
    try:
        # Verify campaign exists
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        new_workstream = Workstream(
            campaign_id=campaign_id,
            type=workstream.type.value,
            name=workstream.name,
            description=workstream.description,
            status=workstream.status,
            budget_allocated=workstream.budget_allocated,
            internal_notes=workstream.internal_notes,
            created_by=UUID(operations_access.user_id)
        )

        db.add(new_workstream)
        await db.commit()
        await db.refresh(new_workstream)

        # Log activity
        activity = ActivityLog(
            campaign_id=campaign_id,
            workstream_id=new_workstream.id,
            type="workstream_created",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"Created workstream '{workstream.name}'",
            details={"type": workstream.type.value},
            is_client_visible=True
        )
        db.add(activity)
        await db.commit()

        return WorkstreamResponse(
            id=str(new_workstream.id),
            campaign_id=str(new_workstream.campaign_id),
            type=new_workstream.type,
            name=new_workstream.name,
            description=new_workstream.description,
            status=new_workstream.status.value,
            deliverables_count=0,
            completion_percentage=0.0,
            pending_approvals=0,
            budget_allocated=new_workstream.budget_allocated,
            budget_spent=0,
            internal_notes=new_workstream.internal_notes,
            created_at=new_workstream.created_at,
            updated_at=new_workstream.updated_at or new_workstream.created_at,
            created_by=str(new_workstream.created_by),
            _access={
                "created_by_role": "super_admin"
            }
        )

    except Exception as e:
        logger.error(f"Error creating workstream: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============= DELIVERABLES =============
@router.get("/workstreams/{workstream_id}/deliverables")
async def list_deliverables(
    workstream_id: UUID,
    status: Optional[List[str]] = Query(None),
    creator: Optional[str] = Query(None),
    due_date_from: Optional[date] = Query(None),
    due_date_to: Optional[date] = Query(None),
    has_concept: Optional[bool] = Query(None),
    has_assignment: Optional[bool] = Query(None),
    has_assets: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> DeliverableListResponse:
    """Get deliverables for a workstream"""
    try:
        # Get workstream and check access
        workstream_result = await db.execute(
            select(Workstream).where(Workstream.id == workstream_id)
        )
        workstream = workstream_result.scalar_one_or_none()

        if not workstream:
            raise HTTPException(status_code=404, detail="Workstream not found")

        if not check_campaign_access(str(workstream.campaign_id), operations_access, "viewer"):
            raise OperationsPermissionError(
                detail="You don't have access to this campaign",
                user_role=operations_access.role
            )

        # Build query
        query = select(Deliverable).where(Deliverable.workstream_id == workstream_id)

        # Apply filters
        if status:
            query = query.where(Deliverable.status.in_(status))
        if due_date_from:
            query = query.where(Deliverable.due_date >= due_date_from)
        if due_date_to:
            query = query.where(Deliverable.due_date <= due_date_to)
        if has_concept is not None:
            if has_concept:
                query = query.where(Deliverable.concept_id.isnot(None))
            else:
                query = query.where(Deliverable.concept_id.is_(None))
        if has_assignment is not None:
            if has_assignment:
                query = query.where(Deliverable.assignment_id.isnot(None))
            else:
                query = query.where(Deliverable.assignment_id.is_(None))
        if has_assets is not None:
            if has_assets:
                query = query.where(Deliverable.assets != {})
            else:
                query = query.where(or_(Deliverable.assets == {}, Deliverable.assets.is_(None)))

        # Filter by creator if specified
        if creator and creator != "all":
            # Join with Assignment table
            query = query.join(Assignment, Deliverable.assignment_id == Assignment.id)
            query = query.where(Assignment.creator_username.ilike(f"%{creator}%"))

        result = await db.execute(query.order_by(Deliverable.due_date))
        deliverables = result.scalars().all()

        deliverable_list = []
        for deliverable in deliverables:
            # Build asset info
            assets_data = deliverable.assets or {}
            asset_info = AssetInfo(
                frame_io_share_link=assets_data.get('frame_io_share_link'),
                hd_updated=assets_data.get('hd_updated', False),
                hd_updated_at=datetime.fromisoformat(assets_data['hd_updated_at']) if assets_data.get('hd_updated_at') else None,
                versions=assets_data.get('versions', []),
                edited_files=assets_data.get('edited_files', [])
            )

            # Add superadmin-only asset fields
            if operations_access.role in ['super_admin', 'superadmin']:
                asset_info.frame_io_folder = assets_data.get('frame_io_folder')
                asset_info.hd_updated_by = assets_data.get('hd_updated_by')
                asset_info.raw_files = assets_data.get('raw_files', [])

            # Build posting proof
            posting_proof = None
            if deliverable.posting_proof:
                proof_data = deliverable.posting_proof
                posting_proof = PostingProof(
                    platform=proof_data.get('platform'),
                    url=proof_data.get('url'),
                    posted_at=datetime.fromisoformat(proof_data['posted_at']) if proof_data.get('posted_at') else None,
                    metrics_snapshot=proof_data.get('metrics_snapshot')
                )

            deliverable_data = {
                "id": str(deliverable.id),
                "workstream_id": str(deliverable.workstream_id),
                "campaign_id": str(deliverable.campaign_id),
                "title": deliverable.title,
                "description": deliverable.description,
                "type": deliverable.type,
                "status": deliverable.status.value,
                "due_date": deliverable.due_date.isoformat() if deliverable.due_date else None,
                "posting_date": deliverable.posting_date.isoformat() if deliverable.posting_date else None,
                "concept_id": str(deliverable.concept_id) if deliverable.concept_id else None,
                "assignment_id": str(deliverable.assignment_id) if deliverable.assignment_id else None,
                "production_batch_id": str(deliverable.production_batch_id) if deliverable.production_batch_id else None,
                "assets": asset_info.dict(),
                "posting_proof": posting_proof.dict() if posting_proof else None,
                "dependencies": deliverable.dependencies or [],
                "client_notes": deliverable.client_notes,
                "created_at": deliverable.created_at.isoformat(),
                "updated_at": deliverable.updated_at.isoformat() if deliverable.updated_at else deliverable.created_at.isoformat(),
                "created_by": str(deliverable.created_by),
                "last_modified_by": str(deliverable.last_modified_by) if deliverable.last_modified_by else None
            }

            # Add internal notes for superadmins
            if operations_access.role in ['super_admin', 'superadmin']:
                deliverable_data["internal_notes"] = deliverable.internal_notes

            deliverable_list.append(filter_response_by_role(deliverable_data, operations_access.role))

        return DeliverableListResponse(
            deliverables=deliverable_list,
            _access={
                "user_role": operations_access.role,
                "can_create": operations_access.operations_access.create_deliverables,
                "can_bulk_edit": operations_access.operations_access.bulk_operations,
                "can_delete": operations_access.operations_access.bulk_operations
            }
        )

    except Exception as e:
        logger.error(f"Error listing deliverables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workstreams/{workstream_id}/deliverables", dependencies=[Depends(require_superadmin)])
async def create_deliverable(
    workstream_id: UUID,
    deliverable: DeliverableCreate,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> DeliverableResponse:
    """Create deliverable (SUPERADMIN ONLY)"""
    try:
        # Get workstream
        workstream_result = await db.execute(
            select(Workstream).where(Workstream.id == workstream_id)
        )
        workstream = workstream_result.scalar_one_or_none()

        if not workstream:
            raise HTTPException(status_code=404, detail="Workstream not found")

        new_deliverable = Deliverable(
            workstream_id=workstream_id,
            campaign_id=workstream.campaign_id,
            title=deliverable.title,
            description=deliverable.description,
            type=deliverable.type.value,
            status=deliverable.status.value,
            due_date=deliverable.due_date,
            posting_date=deliverable.posting_date,
            internal_notes=deliverable.internal_notes,
            created_by=UUID(operations_access.user_id)
        )

        db.add(new_deliverable)
        await db.commit()
        await db.refresh(new_deliverable)

        # Log activity
        activity = ActivityLog(
            campaign_id=workstream.campaign_id,
            workstream_id=workstream_id,
            deliverable_id=new_deliverable.id,
            type="deliverable_created",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"Created deliverable '{deliverable.title}'",
            details={"type": deliverable.type.value, "status": deliverable.status.value},
            is_client_visible=True
        )
        db.add(activity)
        await db.commit()

        return DeliverableResponse(
            id=str(new_deliverable.id),
            workstream_id=str(new_deliverable.workstream_id),
            campaign_id=str(new_deliverable.campaign_id),
            title=new_deliverable.title,
            description=new_deliverable.description,
            type=new_deliverable.type,
            status=new_deliverable.status.value,
            due_date=new_deliverable.due_date,
            posting_date=new_deliverable.posting_date,
            internal_notes=new_deliverable.internal_notes,
            created_at=new_deliverable.created_at,
            updated_at=new_deliverable.updated_at or new_deliverable.created_at,
            created_by=str(new_deliverable.created_by)
        )

    except Exception as e:
        logger.error(f"Error creating deliverable: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deliverables/bulk", dependencies=[Depends(require_superadmin)])
async def bulk_deliverable_operations(
    operation: BulkDeliverableOperation,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> Dict[str, Any]:
    """Bulk operations on deliverables (SUPERADMIN ONLY)"""
    try:
        results = []

        for target_id in operation.target_ids:
            try:
                # Get deliverable
                result = await db.execute(
                    select(Deliverable).where(Deliverable.id == UUID(target_id))
                )
                deliverable = result.scalar_one_or_none()

                if not deliverable:
                    results.append({
                        "id": target_id,
                        "success": False,
                        "error": "Deliverable not found"
                    })
                    continue

                previous_state = {
                    "status": deliverable.status.value if hasattr(deliverable.status, 'value') else deliverable.status
                }

                # Perform operation
                if operation.type == "status_change":
                    new_status = operation.params.get("status")
                    if new_status:
                        deliverable.status = new_status
                        deliverable.last_modified_by = UUID(operations_access.user_id)

                        # Log activity
                        activity = ActivityLog(
                            campaign_id=deliverable.campaign_id,
                            workstream_id=deliverable.workstream_id,
                            deliverable_id=deliverable.id,
                            type="status_change",
                            actor_id=UUID(operations_access.user_id),
                            actor_name=operations_access.email,
                            actor_role=operations_access.role,
                            action=f"Changed status to {new_status}",
                            details={"old_status": previous_state["status"], "new_status": new_status},
                            is_client_visible=True
                        )
                        db.add(activity)

                elif operation.type == "assign_creator":
                    # TODO: Implement creator assignment
                    pass

                elif operation.type == "schedule_batch":
                    batch_id = operation.params.get("batch_id")
                    if batch_id:
                        deliverable.production_batch_id = UUID(batch_id)
                        deliverable.last_modified_by = UUID(operations_access.user_id)

                elif operation.type == "delete":
                    await db.delete(deliverable)
                    results.append({
                        "id": target_id,
                        "success": True,
                        "previous_state": previous_state,
                        "new_state": {"deleted": True}
                    })
                    continue

                await db.commit()

                new_state = {
                    "status": deliverable.status.value if hasattr(deliverable.status, 'value') else deliverable.status
                }

                results.append({
                    "id": target_id,
                    "success": True,
                    "previous_state": previous_state,
                    "new_state": new_state
                })

            except Exception as e:
                results.append({
                    "id": target_id,
                    "success": False,
                    "error": str(e)
                })

        return {"results": results}

    except Exception as e:
        logger.error(f"Error in bulk operations: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))