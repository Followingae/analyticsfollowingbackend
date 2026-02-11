"""
Campaign Operations OS - Concepts & Approvals Routes
Routes for concept management and approval workflows
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
import json

from app.database.connection import get_db
from app.database.operations_models import (
    Workstream, Concept, Deliverable, ActivityLog,
    ApprovalStatusEnum
)
from app.models.operations_models import (
    ConceptCreate, ConceptUpdate, ConceptApproval,
    ConceptResponse, ConceptListResponse, ConceptComment,
    ApprovalStatus, OperationsAccess
)
from app.middleware.operations_auth import (
    get_operations_access, require_superadmin, require_operations_access,
    filter_response_by_role, check_campaign_access,
    OperationsPermissionError
)

router = APIRouter(tags=["Operations - Concepts"])
logger = logging.getLogger(__name__)


@router.get("/workstreams/{workstream_id}/concepts")
async def list_concepts(
    workstream_id: UUID,
    approval_status: Optional[List[str]] = Query(None),
    has_deliverables: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> ConceptListResponse:
    """Get concepts for workstream"""
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
        query = select(Concept).where(Concept.workstream_id == workstream_id)

        # Apply filters
        if approval_status:
            query = query.where(Concept.approval_status.in_(approval_status))

        result = await db.execute(query.order_by(Concept.created_at))
        concepts = result.scalars().all()

        # Filter by deliverables if requested
        if has_deliverables is not None:
            filtered_concepts = []
            for concept in concepts:
                # Count linked deliverables
                deliverables_result = await db.execute(
                    select(func.count()).select_from(Deliverable)
                    .where(Deliverable.concept_id == concept.id)
                )
                deliverable_count = deliverables_result.scalar()

                if has_deliverables and deliverable_count > 0:
                    filtered_concepts.append(concept)
                elif not has_deliverables and deliverable_count == 0:
                    filtered_concepts.append(concept)
            concepts = filtered_concepts

        concept_list = []
        for concept in concepts:
            # Get linked deliverables
            deliverables_result = await db.execute(
                select(Deliverable.id).where(Deliverable.concept_id == concept.id)
            )
            deliverable_ids = [str(d) for d in deliverables_result.scalars().all()]

            # Parse comments - filter internal comments for clients
            comments = []
            if concept.comments:
                for comment_data in concept.comments:
                    # Skip internal comments for non-superadmins
                    if comment_data.get('is_internal') and operations_access.role not in ['super_admin', 'superadmin']:
                        continue

                    comments.append(ConceptComment(
                        id=comment_data.get('id'),
                        user_id=comment_data.get('user_id'),
                        user_name=comment_data.get('user_name'),
                        user_role=comment_data.get('user_role'),
                        comment=comment_data.get('comment'),
                        timestamp=datetime.fromisoformat(comment_data.get('timestamp')),
                        is_internal=comment_data.get('is_internal', False)
                    ))

            concept_data = {
                "id": str(concept.id),
                "workstream_id": str(concept.workstream_id),
                "campaign_id": str(concept.campaign_id),
                "title": concept.title,
                "hook": concept.hook,
                "script": concept.script,
                "on_screen_text": concept.on_screen_text,
                "reference_links": concept.reference_links or [],
                "key_messages": concept.key_messages or [],
                "purpose": concept.purpose,
                "pillar": concept.pillar,
                "client_facing_version": concept.client_facing_version,
                "approval_status": concept.approval_status.value,
                "approval_history": concept.approval_history or [],
                "comments": [c.dict() for c in comments],
                "deliverable_ids": deliverable_ids,
                "created_at": concept.created_at.isoformat(),
                "updated_at": concept.updated_at.isoformat() if concept.updated_at else concept.created_at.isoformat(),
                "created_by": str(concept.created_by)
            }

            # Add internal version for superadmins
            if operations_access.role in ['super_admin', 'superadmin']:
                concept_data["internal_version"] = concept.internal_version

            concept_list.append(filter_response_by_role(concept_data, operations_access.role))

        return ConceptListResponse(
            concepts=concept_list,
            _access={
                "user_role": operations_access.role,
                "can_create": operations_access.operations_access.create_workstreams,
                "can_approve": operations_access.operations_access.approve_concepts,
                "can_submit_for_approval": operations_access.role in ['super_admin', 'superadmin']
            }
        )

    except Exception as e:
        logger.error(f"Error listing concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workstreams/{workstream_id}/concepts", dependencies=[Depends(require_superadmin)])
async def create_concept(
    workstream_id: UUID,
    concept: ConceptCreate,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> ConceptResponse:
    """Create concept (SUPERADMIN ONLY)"""
    try:
        # Get workstream
        workstream_result = await db.execute(
            select(Workstream).where(Workstream.id == workstream_id)
        )
        workstream = workstream_result.scalar_one_or_none()

        if not workstream:
            raise HTTPException(status_code=404, detail="Workstream not found")

        new_concept = Concept(
            workstream_id=workstream_id,
            campaign_id=workstream.campaign_id,
            title=concept.title,
            hook=concept.hook,
            script=concept.script,
            on_screen_text=concept.on_screen_text,
            reference_links=concept.reference_links,
            key_messages=concept.key_messages,
            purpose=concept.purpose,
            pillar=concept.pillar,
            internal_version=concept.internal_version,
            client_facing_version=concept.client_facing_version,
            approval_status=ApprovalStatusEnum.NOT_SENT,
            approval_history=[],
            comments=[],
            created_by=UUID(operations_access.user_id)
        )

        db.add(new_concept)
        await db.commit()
        await db.refresh(new_concept)

        # Log activity
        activity = ActivityLog(
            campaign_id=workstream.campaign_id,
            workstream_id=workstream_id,
            type="concept_created",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"Created concept '{concept.title}'",
            details={},
            is_client_visible=True
        )
        db.add(activity)
        await db.commit()

        return ConceptResponse(
            id=str(new_concept.id),
            workstream_id=str(new_concept.workstream_id),
            campaign_id=str(new_concept.campaign_id),
            title=new_concept.title,
            hook=new_concept.hook,
            script=new_concept.script,
            on_screen_text=new_concept.on_screen_text,
            reference_links=new_concept.reference_links,
            key_messages=new_concept.key_messages,
            purpose=new_concept.purpose,
            pillar=new_concept.pillar,
            internal_version=new_concept.internal_version,
            client_facing_version=new_concept.client_facing_version,
            approval_status=ApprovalStatus.NOT_SENT,
            approval_history=[],
            comments=[],
            deliverable_ids=[],
            created_at=new_concept.created_at,
            updated_at=new_concept.updated_at or new_concept.created_at,
            created_by=str(new_concept.created_by),
            _access={
                "created_by_role": "super_admin"
            }
        )

    except Exception as e:
        logger.error(f"Error creating concept: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/concepts/{concept_id}/decision")
async def approve_or_reject_concept(
    concept_id: UUID,
    decision: ConceptApproval,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(require_operations_access)
) -> Dict[str, Any]:
    """Approve or request changes on concept (ALL AUTHENTICATED USERS)"""
    try:
        # Get concept
        result = await db.execute(
            select(Concept).where(Concept.id == concept_id)
        )
        concept = result.scalar_one_or_none()

        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")

        # Check campaign access
        if not check_campaign_access(str(concept.campaign_id), operations_access, "viewer"):
            raise OperationsPermissionError(
                detail="You don't have access to this campaign",
                user_role=operations_access.role
            )

        # Only superadmins can set internal comments
        if decision.is_internal and operations_access.role not in ['super_admin', 'superadmin']:
            raise OperationsPermissionError(
                detail="Only administrators can create internal comments",
                user_role=operations_access.role
            )

        # Update approval status
        if decision.decision == "approve":
            concept.approval_status = ApprovalStatusEnum.APPROVED
            action = "approved concept"
        else:
            concept.approval_status = ApprovalStatusEnum.CHANGES_REQUESTED
            action = "requested changes on concept"

        # Add to approval history
        if not concept.approval_history:
            concept.approval_history = []

        approval_entry = {
            "id": str(UUID.uuid4()),
            "status": decision.decision,
            "user_id": operations_access.user_id,
            "user_name": operations_access.email,
            "user_role": "superadmin" if operations_access.role in ['super_admin', 'superadmin'] else "client",
            "timestamp": datetime.utcnow().isoformat(),
            "comment": decision.comment
        }
        concept.approval_history.append(approval_entry)

        # Add comment if provided
        if decision.comment:
            if not concept.comments:
                concept.comments = []

            comment_entry = {
                "id": str(UUID.uuid4()),
                "user_id": operations_access.user_id,
                "user_name": operations_access.email,
                "user_role": "superadmin" if operations_access.role in ['super_admin', 'superadmin'] else "client",
                "comment": decision.comment,
                "timestamp": datetime.utcnow().isoformat(),
                "is_internal": decision.is_internal
            }
            concept.comments.append(comment_entry)

        await db.commit()

        # Log activity
        activity = ActivityLog(
            campaign_id=concept.campaign_id,
            workstream_id=concept.workstream_id,
            type="concept_approval",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"{action} '{concept.title}'",
            details={"decision": decision.decision, "comment": decision.comment},
            is_client_visible=not decision.is_internal  # Hide internal comments from activity
        )
        db.add(activity)
        await db.commit()

        # Build response
        response = {
            "success": True,
            "concept": {
                "id": str(concept.id),
                "title": concept.title,
                "approval_status": concept.approval_status.value,
                "approval_history": concept.approval_history,
                "comments": [
                    c for c in concept.comments
                    if not c.get('is_internal') or operations_access.role in ['super_admin', 'superadmin']
                ]
            },
            "_access": {
                "approved_by_role": operations_access.role
            }
        }

        return filter_response_by_role(response, operations_access.role)

    except Exception as e:
        logger.error(f"Error processing concept decision: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/concepts/{concept_id}", dependencies=[Depends(require_superadmin)])
async def update_concept(
    concept_id: UUID,
    update: ConceptUpdate,
    db: AsyncSession = Depends(get_db),
    operations_access: OperationsAccess = Depends(get_operations_access)
) -> ConceptResponse:
    """Update concept (SUPERADMIN ONLY)"""
    try:
        # Get concept
        result = await db.execute(
            select(Concept).where(Concept.id == concept_id)
        )
        concept = result.scalar_one_or_none()

        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")

        # Update fields if provided
        if update.title is not None:
            concept.title = update.title
        if update.hook is not None:
            concept.hook = update.hook
        if update.script is not None:
            concept.script = update.script
        if update.on_screen_text is not None:
            concept.on_screen_text = update.on_screen_text
        if update.reference_links is not None:
            concept.reference_links = update.reference_links
        if update.key_messages is not None:
            concept.key_messages = update.key_messages
        if update.purpose is not None:
            concept.purpose = update.purpose
        if update.pillar is not None:
            concept.pillar = update.pillar
        if update.internal_version is not None:
            concept.internal_version = update.internal_version
        if update.client_facing_version is not None:
            concept.client_facing_version = update.client_facing_version

        concept.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(concept)

        # Log activity
        activity = ActivityLog(
            campaign_id=concept.campaign_id,
            workstream_id=concept.workstream_id,
            type="concept_updated",
            actor_id=UUID(operations_access.user_id),
            actor_name=operations_access.email,
            actor_role=operations_access.role,
            action=f"Updated concept '{concept.title}'",
            details={},
            is_client_visible=True
        )
        db.add(activity)
        await db.commit()

        # Get linked deliverables
        deliverables_result = await db.execute(
            select(Deliverable.id).where(Deliverable.concept_id == concept.id)
        )
        deliverable_ids = [str(d) for d in deliverables_result.scalars().all()]

        return ConceptResponse(
            id=str(concept.id),
            workstream_id=str(concept.workstream_id),
            campaign_id=str(concept.campaign_id),
            title=concept.title,
            hook=concept.hook,
            script=concept.script,
            on_screen_text=concept.on_screen_text,
            reference_links=concept.reference_links,
            key_messages=concept.key_messages,
            purpose=concept.purpose,
            pillar=concept.pillar,
            internal_version=concept.internal_version,
            client_facing_version=concept.client_facing_version,
            approval_status=concept.approval_status.value,
            approval_history=concept.approval_history,
            comments=[
                c for c in concept.comments
                if not c.get('is_internal') or operations_access.role in ['super_admin', 'superadmin']
            ],
            deliverable_ids=deliverable_ids,
            created_at=concept.created_at,
            updated_at=concept.updated_at,
            created_by=str(concept.created_by)
        )

    except Exception as e:
        logger.error(f"Error updating concept: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))