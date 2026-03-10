"""
UGC Campaign API Routes
Endpoints for managing UGC models, concepts, and videos within campaigns.
Superadmin manages the talent pool and production; brands review and approve.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import date
import logging

from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.optimized_pools import get_db_optimized as get_db
from app.services.ugc_service import ugc_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["UGC"])


# =============================================================================
# HELPERS
# =============================================================================

async def verify_campaign_access(db, campaign_id, current_user, require_superadmin=False):
    """Verify user has access to this campaign. Returns campaign row."""
    result = await db.execute(
        text("SELECT id, user_id, campaign_type, created_by FROM campaigns WHERE id = :cid").execution_options(prepare=False),
        {"cid": str(campaign_id)}
    )
    campaign = result.mappings().fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign["campaign_type"] != "ugc":
        raise HTTPException(status_code=400, detail="This is not a UGC campaign")

    is_superadmin = current_user.role == 'superadmin'
    is_owner = str(campaign["user_id"]) == str(current_user.id)

    if require_superadmin and not is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    if not is_owner and not is_superadmin:
        raise HTTPException(status_code=403, detail="Not authorized")

    return dict(campaign), is_superadmin


def require_superadmin(current_user: UserInDB):
    """Raise 403 if user is not superadmin"""
    if current_user.role != 'superadmin':
        raise HTTPException(status_code=403, detail="Superadmin only")


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CreateModelRequest(BaseModel):
    """Request model for creating a UGC model"""
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    profile_photo_url: Optional[str] = None
    ethnicity: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    age_range: Optional[str] = None
    languages: Optional[List[str]] = Field(default_factory=list)
    specialties: Optional[List[str]] = Field(default_factory=list)
    day_rate_usd_cents: Optional[int] = None
    previous_brands: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None


class UpdateModelRequest(BaseModel):
    """Request model for updating a UGC model"""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    profile_photo_url: Optional[str] = None
    ethnicity: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    age_range: Optional[str] = None
    languages: Optional[List[str]] = None
    specialties: Optional[List[str]] = None
    day_rate_usd_cents: Optional[int] = None
    previous_brands: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[float] = None


class AssignModelsRequest(BaseModel):
    """Request model for assigning models to a campaign"""
    model_ids: List[UUID]


class ModelSelectionRequest(BaseModel):
    """Request model for brand selecting/rejecting a model"""
    selected: bool
    feedback: Optional[str] = None


class CreateConceptRequest(BaseModel):
    """Request model for creating a UGC concept"""
    concept_name: str
    reference_url: Optional[str] = None
    product_group: Optional[str] = None
    shoot_location: Optional[str] = None
    creative_direction: Optional[str] = None
    primary_hook: Optional[str] = None
    content_purpose: Optional[str] = None
    scene_description: Optional[str] = None
    on_screen_text: Optional[str] = None
    script: Optional[str] = None
    usability_notes: Optional[str] = None
    caption_en: Optional[str] = None
    caption_ar: Optional[str] = None
    assigned_model_id: Optional[UUID] = None
    shoot_date: Optional[date] = None
    foc_products: Optional[List[str]] = Field(default_factory=list)
    month: Optional[str] = None
    status: Optional[str] = "draft"


class UpdateConceptRequest(BaseModel):
    """Request model for updating a UGC concept"""
    concept_name: Optional[str] = None
    reference_url: Optional[str] = None
    product_group: Optional[str] = None
    shoot_location: Optional[str] = None
    creative_direction: Optional[str] = None
    primary_hook: Optional[str] = None
    content_purpose: Optional[str] = None
    scene_description: Optional[str] = None
    on_screen_text: Optional[str] = None
    script: Optional[str] = None
    usability_notes: Optional[str] = None
    caption_en: Optional[str] = None
    caption_ar: Optional[str] = None
    assigned_model_id: Optional[UUID] = None
    shoot_date: Optional[date] = None
    foc_products: Optional[List[str]] = None
    month: Optional[str] = None
    status: Optional[str] = None
    brand_feedback: Optional[str] = None


class BulkCreateConceptsRequest(BaseModel):
    """Request model for bulk creating concepts"""
    concepts: List[CreateConceptRequest]


class ConceptStatusRequest(BaseModel):
    """Request model for updating concept status (brand review)"""
    status: str = Field(..., description="approved, rejected, revision_requested")
    brand_feedback: Optional[str] = None


class CreateVideoRequest(BaseModel):
    """Request model for creating a UGC video"""
    concept_id: Optional[UUID] = None
    video_name: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    dimension: Optional[str] = None
    file_size_bytes: Optional[int] = None
    status: Optional[str] = "uploaded"


class UpdateVideoRequest(BaseModel):
    """Request model for updating a UGC video"""
    concept_id: Optional[UUID] = None
    video_name: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    dimension: Optional[str] = None
    file_size_bytes: Optional[int] = None
    status: Optional[str] = None
    brand_feedback: Optional[str] = None
    posting_status: Optional[str] = None
    posted_url: Optional[str] = None
    learnings: Optional[str] = None


class ReviewVideoRequest(BaseModel):
    """Request model for brand reviewing a video"""
    status: str = Field(..., description="approved, revision_requested")
    feedback: Optional[str] = None


# =============================================================================
# UGC MODEL POOL ENDPOINTS (Superadmin only)
# =============================================================================

@router.post("/ugc/models")
async def create_model(
    request: CreateModelRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new UGC model in the talent pool (superadmin only)"""
    require_superadmin(current_user)
    try:
        model = await ugc_service.create_model(db, request.model_dump(), UUID(current_user.id))
        return {"success": True, "data": model, "message": "Model created successfully"}
    except Exception as e:
        logger.error(f"Error creating UGC model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create UGC model"
        )


@router.get("/ugc/models")
async def list_models(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List UGC models in the talent pool (superadmin only)"""
    require_superadmin(current_user)
    try:
        result = await ugc_service.list_models(db, status_filter=status_filter,
                                               search=search, limit=limit, offset=offset)
        return {"success": True, "data": result, "message": "Models retrieved"}
    except Exception as e:
        logger.error(f"Error listing UGC models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list UGC models"
        )


@router.get("/ugc/models/{model_id}")
async def get_model(
    model_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single UGC model (superadmin only)"""
    require_superadmin(current_user)
    try:
        model = await ugc_service.get_model(db, model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True, "data": model, "message": "Model retrieved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting UGC model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get UGC model"
        )


@router.put("/ugc/models/{model_id}")
async def update_model(
    model_id: UUID,
    request: UpdateModelRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a UGC model (superadmin only)"""
    require_superadmin(current_user)
    try:
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        model = await ugc_service.update_model(db, model_id, update_data)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True, "data": model, "message": "Model updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating UGC model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update UGC model"
        )


@router.delete("/ugc/models/{model_id}")
async def delete_model(
    model_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a UGC model (superadmin only)"""
    require_superadmin(current_user)
    try:
        deleted = await ugc_service.delete_model(db, model_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True, "data": None, "message": "Model deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting UGC model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete UGC model"
        )


# =============================================================================
# CAMPAIGN MODEL ASSIGNMENT ENDPOINTS
# =============================================================================

@router.post("/{campaign_id}/ugc/models")
async def assign_models_to_campaign(
    campaign_id: UUID,
    request: AssignModelsRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign models to a UGC campaign (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        assigned = await ugc_service.assign_models_to_campaign(db, campaign_id, request.model_ids)
        return {
            "success": True,
            "data": assigned,
            "message": f"{len(assigned)} model(s) assigned to campaign"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning models to campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign models"
        )


@router.get("/{campaign_id}/ugc/models")
async def get_campaign_models(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List models assigned to a UGC campaign (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        models = await ugc_service.get_campaign_models(db, campaign_id)
        return {"success": True, "data": models, "message": f"{len(models)} model(s) found"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign models for {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get campaign models"
        )


@router.delete("/{campaign_id}/ugc/models/{model_id}")
async def remove_model_from_campaign(
    campaign_id: UUID,
    model_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a model from a UGC campaign (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        removed = await ugc_service.remove_model_from_campaign(db, campaign_id, model_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Model assignment not found")
        return {"success": True, "data": None, "message": "Model removed from campaign"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing model {model_id} from campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove model"
        )


@router.put("/{campaign_id}/ugc/models/{model_id}/select")
async def select_model(
    campaign_id: UUID,
    model_id: UUID,
    request: ModelSelectionRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Brand selects or rejects a proposed model (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        result = await ugc_service.update_model_selection(
            db, campaign_id, model_id,
            selected=request.selected, feedback=request.feedback
        )
        if not result:
            raise HTTPException(status_code=404, detail="Model assignment not found")
        action = "selected" if request.selected else "rejected"
        return {"success": True, "data": result, "message": f"Model {action}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting model {model_id} in campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model selection"
        )


# =============================================================================
# CONCEPT ENDPOINTS
# =============================================================================

@router.post("/{campaign_id}/ugc/concepts")
async def create_concept(
    campaign_id: UUID,
    request: CreateConceptRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a UGC concept (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        concept = await ugc_service.create_concept(db, campaign_id, request.model_dump())
        return {"success": True, "data": concept, "message": "Concept created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating concept for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create concept"
        )


@router.get("/{campaign_id}/ugc/concepts")
async def list_concepts(
    campaign_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List concepts for a UGC campaign (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        concepts = await ugc_service.list_concepts(db, campaign_id, status_filter=status_filter)
        return {"success": True, "data": concepts, "message": f"{len(concepts)} concept(s) found"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing concepts for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list concepts"
        )


@router.get("/{campaign_id}/ugc/concepts/{concept_id}")
async def get_concept(
    campaign_id: UUID,
    concept_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single concept detail (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        concept = await ugc_service.get_concept(db, concept_id)
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        # Verify concept belongs to this campaign
        if str(concept.get("campaign_id")) != str(campaign_id):
            raise HTTPException(status_code=404, detail="Concept not found in this campaign")
        return {"success": True, "data": concept, "message": "Concept retrieved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting concept {concept_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get concept"
        )


@router.put("/{campaign_id}/ugc/concepts/{concept_id}")
async def update_concept(
    campaign_id: UUID,
    concept_id: UUID,
    request: UpdateConceptRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a UGC concept (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        concept = await ugc_service.update_concept(db, concept_id, update_data)
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        return {"success": True, "data": concept, "message": "Concept updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating concept {concept_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update concept"
        )


@router.delete("/{campaign_id}/ugc/concepts/{concept_id}")
async def delete_concept(
    campaign_id: UUID,
    concept_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a UGC concept (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        deleted = await ugc_service.delete_concept(db, concept_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Concept not found")
        return {"success": True, "data": None, "message": "Concept deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting concept {concept_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete concept"
        )


@router.post("/{campaign_id}/ugc/concepts/bulk")
async def bulk_create_concepts(
    campaign_id: UUID,
    request: BulkCreateConceptsRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk create UGC concepts (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        concepts_data = [c.model_dump() for c in request.concepts]
        created = await ugc_service.bulk_create_concepts(db, campaign_id, concepts_data)
        return {
            "success": True,
            "data": created,
            "message": f"{len(created)} concept(s) created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk creating concepts for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk create concepts"
        )


@router.put("/{campaign_id}/ugc/concepts/{concept_id}/status")
async def update_concept_status(
    campaign_id: UUID,
    concept_id: UUID,
    request: ConceptStatusRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Brand reviews a concept - approve, reject, or request revision (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        valid_statuses = ["approved", "rejected", "revision_requested"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        concept = await ugc_service.update_concept_status(
            db, concept_id,
            new_status=request.status, brand_feedback=request.brand_feedback
        )
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        return {"success": True, "data": concept, "message": f"Concept {request.status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating concept status {concept_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update concept status"
        )


# =============================================================================
# VIDEO ENDPOINTS
# =============================================================================

@router.post("/{campaign_id}/ugc/videos")
async def create_video(
    campaign_id: UUID,
    request: CreateVideoRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload video info for a UGC campaign (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        video = await ugc_service.create_video(db, campaign_id, request.model_dump())
        return {"success": True, "data": video, "message": "Video created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating video for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create video"
        )


@router.get("/{campaign_id}/ugc/videos")
async def list_videos(
    campaign_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List videos for a UGC campaign (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        videos = await ugc_service.list_videos(db, campaign_id, status_filter=status_filter)
        return {"success": True, "data": videos, "message": f"{len(videos)} video(s) found"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing videos for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list videos"
        )


@router.put("/{campaign_id}/ugc/videos/{video_id}")
async def update_video(
    campaign_id: UUID,
    video_id: UUID,
    request: UpdateVideoRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a UGC video (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        video = await ugc_service.update_video(db, video_id, update_data)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return {"success": True, "data": video, "message": "Video updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update video"
        )


@router.put("/{campaign_id}/ugc/videos/{video_id}/review")
async def review_video(
    campaign_id: UUID,
    video_id: UUID,
    request: ReviewVideoRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Brand reviews a video - approve or request revision (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        valid_statuses = ["approved", "revision_requested"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        video = await ugc_service.review_video(
            db, video_id,
            status=request.status, feedback=request.feedback
        )
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return {"success": True, "data": video, "message": f"Video {request.status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to review video"
        )


@router.delete("/{campaign_id}/ugc/videos/{video_id}")
async def delete_video(
    campaign_id: UUID,
    video_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a UGC video (superadmin only)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user, require_superadmin=True)
        deleted = await ugc_service.delete_video(db, video_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Video not found")
        return {"success": True, "data": None, "message": "Video deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video"
        )


# =============================================================================
# STATS ENDPOINT
# =============================================================================

@router.get("/{campaign_id}/ugc/stats")
async def get_campaign_ugc_stats(
    campaign_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get UGC campaign production stats (owner or superadmin)"""
    try:
        await verify_campaign_access(db, campaign_id, current_user)
        stats = await ugc_service.get_campaign_ugc_stats(db, campaign_id)
        return {"success": True, "data": stats, "message": "UGC stats retrieved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting UGC stats for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get UGC stats"
        )
