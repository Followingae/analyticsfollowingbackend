"""
UGC Campaign Service - Handles UGC models, concepts, and videos
All writes use raw SQL for PGBouncer compatibility.
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class UGCService:
    """Service for managing UGC campaigns, models, concepts, and videos"""

    # =========================================================================
    # UGC MODEL POOL MANAGEMENT
    # =========================================================================

    async def create_model(self, db: AsyncSession, data: dict, created_by: UUID) -> dict:
        """Create a UGC model in the talent pool"""
        model_id = uuid4()
        await db.execute(
            text("""
                INSERT INTO ugc_models (id, full_name, email, phone, instagram_url, portfolio_url,
                    profile_photo_url, ethnicity, nationality, gender, age_range, languages,
                    specialties, day_rate_usd_cents, previous_brands, notes, created_by, status)
                VALUES (:id, :full_name, :email, :phone, :instagram_url, :portfolio_url,
                    :photo, :ethnicity, :nationality, :gender, :age_range, :languages::jsonb,
                    :specialties::jsonb, :day_rate, :prev_brands::jsonb, :notes, :created_by, 'active')
            """).execution_options(prepare=False),
            {
                "id": str(model_id), "full_name": data["full_name"],
                "email": data.get("email"), "phone": data.get("phone"),
                "instagram_url": data.get("instagram_url"), "portfolio_url": data.get("portfolio_url"),
                "photo": data.get("profile_photo_url"), "ethnicity": data.get("ethnicity"),
                "nationality": data.get("nationality"), "gender": data.get("gender"),
                "age_range": data.get("age_range"),
                "languages": str(data.get("languages", "[]")).replace("'", '"') if data.get("languages") else "[]",
                "specialties": str(data.get("specialties", "[]")).replace("'", '"') if data.get("specialties") else "[]",
                "day_rate": data.get("day_rate_usd_cents"),
                "prev_brands": str(data.get("previous_brands", "[]")).replace("'", '"') if data.get("previous_brands") else "[]",
                "notes": data.get("notes"), "created_by": str(created_by)
            }
        )
        return await self.get_model(db, model_id)

    async def get_model(self, db: AsyncSession, model_id: UUID) -> Optional[dict]:
        """Get a single UGC model"""
        result = await db.execute(
            text("SELECT * FROM ugc_models WHERE id = :id").execution_options(prepare=False),
            {"id": str(model_id)}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None

    async def list_models(self, db: AsyncSession, status_filter: str = None,
                          search: str = None, limit: int = 50, offset: int = 0) -> dict:
        """List UGC models with filters"""
        where_clauses = []
        params = {"limit": limit, "offset": offset}

        if status_filter:
            where_clauses.append("status = :status")
            params["status"] = status_filter
        if search:
            where_clauses.append("(full_name ILIKE :search OR email ILIKE :search OR ethnicity ILIKE :search)")
            params["search"] = f"%{search}%"

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        result = await db.execute(
            text(f"SELECT * FROM ugc_models {where_sql} ORDER BY created_at DESC LIMIT :limit OFFSET :offset").execution_options(prepare=False),
            params
        )
        models = [dict(r) for r in result.mappings().fetchall()]

        count_result = await db.execute(
            text(f"SELECT COUNT(*) as cnt FROM ugc_models {where_sql}").execution_options(prepare=False),
            {k: v for k, v in params.items() if k not in ('limit', 'offset')}
        )
        total = count_result.scalar() or 0

        return {"models": models, "total": total, "limit": limit, "offset": offset}

    async def update_model(self, db: AsyncSession, model_id: UUID, data: dict) -> Optional[dict]:
        """Update a UGC model"""
        import json
        set_parts = []
        params = {"id": str(model_id), "now": datetime.now(timezone.utc)}

        simple_fields = ["full_name", "email", "phone", "instagram_url", "portfolio_url",
                         "profile_photo_url", "ethnicity", "nationality", "gender", "age_range",
                         "day_rate_usd_cents", "notes", "status", "rating"]
        json_fields = ["languages", "specialties", "previous_brands"]

        for field in simple_fields:
            if field in data:
                set_parts.append(f"{field} = :{field}")
                params[field] = data[field]

        for field in json_fields:
            if field in data:
                set_parts.append(f"{field} = :{field}::jsonb")
                params[field] = json.dumps(data[field])

        if not set_parts:
            return await self.get_model(db, model_id)

        set_parts.append("updated_at = :now")

        await db.execute(
            text(f"UPDATE ugc_models SET {', '.join(set_parts)} WHERE id = :id").execution_options(prepare=False),
            params
        )
        return await self.get_model(db, model_id)

    async def delete_model(self, db: AsyncSession, model_id: UUID) -> bool:
        """Delete a UGC model"""
        result = await db.execute(
            text("DELETE FROM ugc_models WHERE id = :id").execution_options(prepare=False),
            {"id": str(model_id)}
        )
        return result.rowcount > 0

    # =========================================================================
    # CAMPAIGN MODEL ASSIGNMENT
    # =========================================================================

    async def assign_models_to_campaign(self, db: AsyncSession, campaign_id: UUID, model_ids: List[UUID]) -> List[dict]:
        """Assign models to a UGC campaign (superadmin action)"""
        assigned = []
        for mid in model_ids:
            assign_id = uuid4()
            try:
                await db.execute(
                    text("""
                        INSERT INTO campaign_ugc_models (id, campaign_id, model_id, status)
                        VALUES (:id, :cid, :mid, 'proposed')
                        ON CONFLICT (campaign_id, model_id) DO NOTHING
                    """).execution_options(prepare=False),
                    {"id": str(assign_id), "cid": str(campaign_id), "mid": str(mid)}
                )
                assigned.append({"model_id": str(mid), "status": "proposed"})
            except Exception as e:
                logger.warning(f"Failed to assign model {mid}: {e}")
        return assigned

    async def get_campaign_models(self, db: AsyncSession, campaign_id: UUID) -> List[dict]:
        """Get all models assigned to a campaign with their details"""
        result = await db.execute(
            text("""
                SELECT cm.id as assignment_id, cm.status as assignment_status,
                       cm.selected_by_brand, cm.brand_feedback, cm.assigned_concepts,
                       cm.created_at as assigned_at,
                       m.*
                FROM campaign_ugc_models cm
                JOIN ugc_models m ON m.id = cm.model_id
                WHERE cm.campaign_id = :cid
                ORDER BY cm.created_at ASC
            """).execution_options(prepare=False),
            {"cid": str(campaign_id)}
        )
        return [dict(r) for r in result.mappings().fetchall()]

    async def remove_model_from_campaign(self, db: AsyncSession, campaign_id: UUID, model_id: UUID) -> bool:
        """Remove a model from a campaign"""
        result = await db.execute(
            text("DELETE FROM campaign_ugc_models WHERE campaign_id = :cid AND model_id = :mid").execution_options(prepare=False),
            {"cid": str(campaign_id), "mid": str(model_id)}
        )
        return result.rowcount > 0

    async def update_model_selection(self, db: AsyncSession, campaign_id: UUID, model_id: UUID,
                                     selected: bool, feedback: str = None) -> Optional[dict]:
        """Brand selects or rejects a model"""
        new_status = "selected" if selected else "rejected"
        await db.execute(
            text("""
                UPDATE campaign_ugc_models
                SET status = :status, selected_by_brand = :selected, brand_feedback = :feedback,
                    updated_at = :now
                WHERE campaign_id = :cid AND model_id = :mid
            """).execution_options(prepare=False),
            {"status": new_status, "selected": selected, "feedback": feedback,
             "now": datetime.now(timezone.utc), "cid": str(campaign_id), "mid": str(model_id)}
        )
        # Return updated assignment
        result = await db.execute(
            text("""
                SELECT cm.*, m.full_name, m.profile_photo_url, m.instagram_url
                FROM campaign_ugc_models cm JOIN ugc_models m ON m.id = cm.model_id
                WHERE cm.campaign_id = :cid AND cm.model_id = :mid
            """).execution_options(prepare=False),
            {"cid": str(campaign_id), "mid": str(model_id)}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None

    # =========================================================================
    # CONCEPT MANAGEMENT
    # =========================================================================

    async def create_concept(self, db: AsyncSession, campaign_id: UUID, data: dict) -> dict:
        """Create a UGC concept"""
        import json
        concept_id = uuid4()

        # Auto-generate concept_number
        num_result = await db.execute(
            text("SELECT COALESCE(MAX(concept_number), 0) + 1 as next_num FROM ugc_concepts WHERE campaign_id = :cid").execution_options(prepare=False),
            {"cid": str(campaign_id)}
        )
        next_num = num_result.scalar() or 1

        await db.execute(
            text("""
                INSERT INTO ugc_concepts (id, campaign_id, concept_number, status, concept_name,
                    reference_url, product_group, shoot_location, creative_direction,
                    primary_hook, content_purpose, scene_description, on_screen_text,
                    script, usability_notes, caption_en, caption_ar, assigned_model_id,
                    shoot_date, foc_products, month)
                VALUES (:id, :cid, :num, :status, :name, :ref_url, :product, :location,
                    :direction, :hook, :purpose, :scene, :screen_text, :script, :usability,
                    :caption_en, :caption_ar, :model_id, :shoot_date, :foc::jsonb, :month)
            """).execution_options(prepare=False),
            {
                "id": str(concept_id), "cid": str(campaign_id), "num": next_num,
                "status": data.get("status", "draft"), "name": data["concept_name"],
                "ref_url": data.get("reference_url"), "product": data.get("product_group"),
                "location": data.get("shoot_location"), "direction": data.get("creative_direction"),
                "hook": data.get("primary_hook"), "purpose": data.get("content_purpose"),
                "scene": data.get("scene_description"), "screen_text": data.get("on_screen_text"),
                "script": data.get("script"), "usability": data.get("usability_notes"),
                "caption_en": data.get("caption_en"), "caption_ar": data.get("caption_ar"),
                "model_id": str(data["assigned_model_id"]) if data.get("assigned_model_id") else None,
                "shoot_date": data.get("shoot_date"),
                "foc": json.dumps(data.get("foc_products", [])),
                "month": data.get("month")
            }
        )
        return await self.get_concept(db, concept_id)

    async def get_concept(self, db: AsyncSession, concept_id: UUID) -> Optional[dict]:
        """Get a single concept with model info"""
        result = await db.execute(
            text("""
                SELECT c.*, m.full_name as model_name, m.profile_photo_url as model_photo,
                       m.instagram_url as model_instagram
                FROM ugc_concepts c
                LEFT JOIN ugc_models m ON m.id = c.assigned_model_id
                WHERE c.id = :id
            """).execution_options(prepare=False),
            {"id": str(concept_id)}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None

    async def list_concepts(self, db: AsyncSession, campaign_id: UUID,
                            status_filter: str = None) -> List[dict]:
        """List concepts for a campaign"""
        where = "WHERE c.campaign_id = :cid"
        params = {"cid": str(campaign_id)}
        if status_filter:
            where += " AND c.status = :status"
            params["status"] = status_filter

        result = await db.execute(
            text(f"""
                SELECT c.*, m.full_name as model_name, m.profile_photo_url as model_photo
                FROM ugc_concepts c
                LEFT JOIN ugc_models m ON m.id = c.assigned_model_id
                {where}
                ORDER BY c.concept_number ASC
            """).execution_options(prepare=False),
            params
        )
        return [dict(r) for r in result.mappings().fetchall()]

    async def update_concept(self, db: AsyncSession, concept_id: UUID, data: dict) -> Optional[dict]:
        """Update a concept"""
        import json
        set_parts = []
        params = {"id": str(concept_id), "now": datetime.now(timezone.utc)}

        simple_fields = ["concept_name", "reference_url", "product_group", "shoot_location",
                         "creative_direction", "primary_hook", "content_purpose", "scene_description",
                         "on_screen_text", "script", "usability_notes", "caption_en", "caption_ar",
                         "brand_feedback", "shoot_date", "month", "status"]

        for field in simple_fields:
            if field in data:
                set_parts.append(f"{field} = :{field}")
                params[field] = data[field]

        if "assigned_model_id" in data:
            set_parts.append("assigned_model_id = :model_id")
            params["model_id"] = str(data["assigned_model_id"]) if data["assigned_model_id"] else None

        if "foc_products" in data:
            set_parts.append("foc_products = :foc::jsonb")
            params["foc"] = json.dumps(data["foc_products"])

        if not set_parts:
            return await self.get_concept(db, concept_id)

        set_parts.append("updated_at = :now")

        await db.execute(
            text(f"UPDATE ugc_concepts SET {', '.join(set_parts)} WHERE id = :id").execution_options(prepare=False),
            params
        )
        return await self.get_concept(db, concept_id)

    async def delete_concept(self, db: AsyncSession, concept_id: UUID) -> bool:
        """Delete a concept"""
        result = await db.execute(
            text("DELETE FROM ugc_concepts WHERE id = :id").execution_options(prepare=False),
            {"id": str(concept_id)}
        )
        return result.rowcount > 0

    async def bulk_create_concepts(self, db: AsyncSession, campaign_id: UUID, concepts: List[dict]) -> List[dict]:
        """Bulk create concepts"""
        created = []
        for concept_data in concepts:
            concept = await self.create_concept(db, campaign_id, concept_data)
            if concept:
                created.append(concept)
        return created

    async def update_concept_status(self, db: AsyncSession, concept_id: UUID,
                                    new_status: str, brand_feedback: str = None) -> Optional[dict]:
        """Update concept status (brand approve/reject/feedback)"""
        params = {"id": str(concept_id), "status": new_status, "now": datetime.now(timezone.utc)}
        feedback_sql = ""
        if brand_feedback is not None:
            feedback_sql = ", brand_feedback = :feedback"
            params["feedback"] = brand_feedback

        await db.execute(
            text(f"UPDATE ugc_concepts SET status = :status, updated_at = :now{feedback_sql} WHERE id = :id").execution_options(prepare=False),
            params
        )
        return await self.get_concept(db, concept_id)

    # =========================================================================
    # VIDEO MANAGEMENT
    # =========================================================================

    async def create_video(self, db: AsyncSession, campaign_id: UUID, data: dict) -> dict:
        """Create a UGC video"""
        video_id = uuid4()
        await db.execute(
            text("""
                INSERT INTO ugc_videos (id, concept_id, campaign_id, video_name, video_url,
                    thumbnail_url, duration_seconds, dimension, file_size_bytes, status)
                VALUES (:id, :concept_id, :cid, :name, :url, :thumb, :duration, :dim, :size, :status)
            """).execution_options(prepare=False),
            {
                "id": str(video_id), "concept_id": str(data["concept_id"]) if data.get("concept_id") else None,
                "cid": str(campaign_id), "name": data.get("video_name"),
                "url": data.get("video_url"), "thumb": data.get("thumbnail_url"),
                "duration": data.get("duration_seconds"), "dim": data.get("dimension"),
                "size": data.get("file_size_bytes"), "status": data.get("status", "uploaded")
            }
        )
        return await self.get_video(db, video_id)

    async def get_video(self, db: AsyncSession, video_id: UUID) -> Optional[dict]:
        """Get a single video with concept info"""
        result = await db.execute(
            text("""
                SELECT v.*, c.concept_name, c.concept_number
                FROM ugc_videos v
                LEFT JOIN ugc_concepts c ON c.id = v.concept_id
                WHERE v.id = :id
            """).execution_options(prepare=False),
            {"id": str(video_id)}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None

    async def list_videos(self, db: AsyncSession, campaign_id: UUID,
                          status_filter: str = None) -> List[dict]:
        """List videos for a campaign"""
        where = "WHERE v.campaign_id = :cid"
        params = {"cid": str(campaign_id)}
        if status_filter:
            where += " AND v.status = :status"
            params["status"] = status_filter

        result = await db.execute(
            text(f"""
                SELECT v.*, c.concept_name, c.concept_number
                FROM ugc_videos v
                LEFT JOIN ugc_concepts c ON c.id = v.concept_id
                {where}
                ORDER BY v.created_at DESC
            """).execution_options(prepare=False),
            params
        )
        return [dict(r) for r in result.mappings().fetchall()]

    async def update_video(self, db: AsyncSession, video_id: UUID, data: dict) -> Optional[dict]:
        """Update a video"""
        set_parts = []
        params = {"id": str(video_id), "now": datetime.now(timezone.utc)}

        fields = ["video_name", "video_url", "thumbnail_url", "duration_seconds",
                   "dimension", "file_size_bytes", "status", "brand_feedback",
                   "posting_status", "posted_url", "learnings"]

        for field in fields:
            if field in data:
                set_parts.append(f"{field} = :{field}")
                params[field] = data[field]

        if "concept_id" in data:
            set_parts.append("concept_id = :concept_id")
            params["concept_id"] = str(data["concept_id"]) if data["concept_id"] else None

        if not set_parts:
            return await self.get_video(db, video_id)

        set_parts.append("updated_at = :now")

        await db.execute(
            text(f"UPDATE ugc_videos SET {', '.join(set_parts)} WHERE id = :id").execution_options(prepare=False),
            params
        )
        return await self.get_video(db, video_id)

    async def review_video(self, db: AsyncSession, video_id: UUID,
                           status: str, feedback: str = None) -> Optional[dict]:
        """Brand review of a video (approve/revision_requested)"""
        params = {"id": str(video_id), "status": status, "feedback": feedback,
                  "now": datetime.now(timezone.utc)}

        revision_sql = ""
        if status == "revision_requested":
            revision_sql = ", revision_count = revision_count + 1"

        await db.execute(
            text(f"""
                UPDATE ugc_videos SET status = :status, brand_feedback = :feedback,
                    updated_at = :now{revision_sql}
                WHERE id = :id
            """).execution_options(prepare=False),
            params
        )
        return await self.get_video(db, video_id)

    async def delete_video(self, db: AsyncSession, video_id: UUID) -> bool:
        """Delete a video"""
        result = await db.execute(
            text("DELETE FROM ugc_videos WHERE id = :id").execution_options(prepare=False),
            {"id": str(video_id)}
        )
        return result.rowcount > 0

    # =========================================================================
    # UGC CAMPAIGN STATS
    # =========================================================================

    async def get_campaign_ugc_stats(self, db: AsyncSession, campaign_id: UUID) -> dict:
        """Get UGC campaign production stats"""
        # Concept stats
        concept_result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total_concepts,
                    COUNT(*) FILTER (WHERE status = 'draft') as draft,
                    COUNT(*) FILTER (WHERE status = 'proposed') as proposed,
                    COUNT(*) FILTER (WHERE status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                    COUNT(*) FILTER (WHERE status = 'revision_requested') as revision_requested,
                    COUNT(*) FILTER (WHERE status = 'in_production') as in_production,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed
                FROM ugc_concepts WHERE campaign_id = :cid
            """).execution_options(prepare=False),
            {"cid": str(campaign_id)}
        )
        concepts = dict(concept_result.mappings().fetchone())

        # Video stats
        video_result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total_videos,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'uploaded') as uploaded,
                    COUNT(*) FILTER (WHERE status = 'in_review') as in_review,
                    COUNT(*) FILTER (WHERE status = 'revision_requested') as revision_requested,
                    COUNT(*) FILTER (WHERE status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'final') as final,
                    COALESCE(AVG(revision_count), 0) as avg_revisions
                FROM ugc_videos WHERE campaign_id = :cid
            """).execution_options(prepare=False),
            {"cid": str(campaign_id)}
        )
        videos = dict(video_result.mappings().fetchone())

        # Model stats
        model_result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total_models,
                    COUNT(*) FILTER (WHERE status = 'proposed') as proposed,
                    COUNT(*) FILTER (WHERE status = 'selected') as selected,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                    COUNT(*) FILTER (WHERE status = 'confirmed') as confirmed
                FROM campaign_ugc_models WHERE campaign_id = :cid
            """).execution_options(prepare=False),
            {"cid": str(campaign_id)}
        )
        models = dict(model_result.mappings().fetchone())

        total_concepts = concepts["total_concepts"]
        approval_rate = round((concepts["approved"] + concepts["completed"]) / total_concepts * 100, 1) if total_concepts > 0 else 0

        return {
            "concepts": concepts,
            "videos": videos,
            "models": models,
            "approval_rate": approval_rate,
            "avg_revisions": round(float(videos["avg_revisions"]), 1)
        }


ugc_service = UGCService()
