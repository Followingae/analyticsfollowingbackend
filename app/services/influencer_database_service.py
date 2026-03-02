"""
Influencer Master Database (IMD) - Service Layer
All business logic for superadmin influencer CRM management.

This is an internal CRM — NO external API calls (no Apify, no Creator Analytics pipeline).
If the username already has analytics in our profiles table, we reuse that data.
If not, we just store the username with whatever CRM metadata was provided.
"""
import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class InfluencerDatabaseService:
    """Service for managing the influencer master database."""

    # =========================================================================
    # ADD / IMPORT
    # =========================================================================

    @staticmethod
    async def add_influencer(
        db: AsyncSession,
        username: str,
        added_by: UUID,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        status: str = "active",
        tier: Optional[str] = None,
        cost_pricing: Optional[Dict[str, Any]] = None,
        sell_pricing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a single influencer to the IMD.

        Flow:
        1. Check duplicate in influencer_database
        2. Check profiles table for existing analytics data (reuse if available)
        3. If not in profiles, just store the username with CRM metadata (no external calls)
        """
        username = username.strip().lower().lstrip("@")

        # 1. Check duplicate in influencer_database
        dup = await db.execute(
            text("SELECT id FROM influencer_database WHERE username = :u"),
            {"u": username},
        )
        if dup.fetchone():
            raise ValueError(f"Influencer @{username} already exists in the database")

        # 2. Try to get data from existing profiles table (our analytics DB)
        profile_data = await InfluencerDatabaseService._get_from_profiles_table(db, username)

        if profile_data:
            logger.info(f"IMD: Found @{username} in profiles table — using existing analytics")
            ig_data = profile_data
        else:
            logger.info(f"IMD: @{username} not in profiles — storing as CRM-only entry")
            ig_data = {}

        # 3. Build pricing params from nested objects
        pricing_params: Dict[str, Any] = {}
        pricing_columns = []
        pricing_values = []

        if cost_pricing and isinstance(cost_pricing, dict):
            for k, v in cost_pricing.items():
                if v is not None:
                    pricing_params[k] = v
                    pricing_columns.append(k)
                    pricing_values.append(f":{k}")

        if sell_pricing and isinstance(sell_pricing, dict):
            for k, v in sell_pricing.items():
                if v is not None:
                    pricing_params[k] = v
                    pricing_columns.append(k)
                    pricing_values.append(f":{k}")

        # 4. Insert into influencer_database
        now = datetime.now(timezone.utc)
        params: Dict[str, Any] = {
            "username": username,
            "full_name": ig_data.get("full_name"),
            "biography": ig_data.get("biography"),
            "profile_image_url": ig_data.get("profile_image_url"),
            "is_verified": ig_data.get("is_verified", False),
            "is_private": ig_data.get("is_private", False),
            "followers_count": ig_data.get("followers_count", 0),
            "following_count": ig_data.get("following_count", 0),
            "posts_count": ig_data.get("posts_count", 0),
            "engagement_rate": ig_data.get("engagement_rate", 0),
            "avg_likes": ig_data.get("avg_likes", 0),
            "avg_comments": ig_data.get("avg_comments", 0),
            "avg_views": ig_data.get("avg_views", 0),
            "status": status,
            "tier": tier,
            "categories": categories or ig_data.get("categories", []),
            "tags": tags or [],
            "internal_notes": notes,
            "added_by": str(added_by),
            "ai_content_categories": ig_data.get("ai_content_categories", []),
            "ai_sentiment_score": ig_data.get("ai_sentiment_score"),
            "ai_audience_quality_score": ig_data.get("ai_audience_quality_score"),
            "language_distribution": json.dumps(ig_data["language_distribution"]) if ig_data.get("language_distribution") else None,
            "last_analytics_refresh": now if profile_data else None,
            "created_at": now,
            "updated_at": now,
            **pricing_params,
        }

        extra_cols = f", {', '.join(pricing_columns)}" if pricing_columns else ""
        extra_vals = f", {', '.join(pricing_values)}" if pricing_values else ""

        result = await db.execute(
            text(f"""
                INSERT INTO influencer_database (
                    username, full_name, biography, profile_image_url,
                    is_verified, is_private, followers_count, following_count,
                    posts_count, engagement_rate, avg_likes, avg_comments, avg_views,
                    status, tier, categories, tags, internal_notes,
                    added_by,
                    ai_content_categories, ai_sentiment_score, ai_audience_quality_score,
                    language_distribution,
                    last_analytics_refresh, created_at, updated_at{extra_cols}
                ) VALUES (
                    :username, :full_name, :biography, :profile_image_url,
                    :is_verified, :is_private, :followers_count, :following_count,
                    :posts_count, :engagement_rate, :avg_likes, :avg_comments, :avg_views,
                    :status, :tier, CAST(:categories AS text[]), CAST(:tags AS text[]), :internal_notes,
                    CAST(:added_by AS uuid),
                    CAST(:ai_content_categories AS text[]), :ai_sentiment_score, :ai_audience_quality_score,
                    CAST(:language_distribution AS jsonb),
                    :last_analytics_refresh, :created_at, :updated_at{extra_vals}
                )
                RETURNING *
            """),
            params,
        )
        await db.commit()
        row = result.mappings().fetchone()
        return dict(row) if row else params

    @staticmethod
    async def bulk_import(
        db: AsyncSession,
        usernames: List[str],
        added_by: UUID,
    ) -> Dict[str, Any]:
        """Bulk import influencers. Checks profiles table first per username."""
        added = []
        skipped = []
        failed = []

        for uname in usernames:
            uname = uname.strip().lower().lstrip("@")
            if not uname:
                continue
            try:
                record = await InfluencerDatabaseService.add_influencer(
                    db, uname, added_by
                )
                added.append({"username": uname, "id": str(record.get("id", ""))})
            except ValueError:
                skipped.append({"username": uname, "reason": "duplicate"})
            except Exception as e:
                logger.error(f"Bulk import failed for @{uname}: {e}")
                failed.append({"username": uname, "reason": str(e)})

        return {"added": added, "skipped": skipped, "failed": failed}

    # =========================================================================
    # LIST / GET
    # =========================================================================

    @staticmethod
    async def list_influencers(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        tags: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
        engagement_min: Optional[float] = None,
        engagement_max: Optional[float] = None,
        is_verified: Optional[bool] = None,
        has_pricing: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Paginated list with dynamic filters."""
        conditions = []
        params: Dict[str, Any] = {}

        if search:
            conditions.append(
                "(username ILIKE :search OR full_name ILIKE :search)"
            )
            params["search"] = f"%{search}%"

        if status:
            conditions.append("status = :status")
            params["status"] = status

        if tier:
            conditions.append("tier = :tier")
            params["tier"] = tier

        if tags:
            conditions.append("tags && CAST(:tags AS text[])")
            params["tags"] = tags

        if categories:
            conditions.append("categories && CAST(:categories AS text[])")
            params["categories"] = categories

        if min_followers is not None:
            conditions.append("followers_count >= :min_followers")
            params["min_followers"] = min_followers

        if max_followers is not None:
            conditions.append("followers_count <= :max_followers")
            params["max_followers"] = max_followers

        if engagement_min is not None:
            conditions.append("engagement_rate >= :engagement_min")
            params["engagement_min"] = engagement_min

        if engagement_max is not None:
            conditions.append("engagement_rate <= :engagement_max")
            params["engagement_max"] = engagement_max

        if is_verified is not None:
            conditions.append("is_verified = :is_verified")
            params["is_verified"] = is_verified

        if has_pricing is True:
            conditions.append(
                "(cost_post_usd_cents IS NOT NULL OR sell_post_usd_cents IS NOT NULL)"
            )

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        # Whitelist allowed sort columns
        allowed_sort = {
            "created_at", "updated_at", "username", "followers_count",
            "engagement_rate", "status", "tier",
        }
        if sort_by not in allowed_sort:
            sort_by = "created_at"
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        # Count query
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM influencer_database{where}"),
            params,
        )
        total_count = count_result.scalar() or 0

        # Data query
        data_result = await db.execute(
            text(
                f"SELECT * FROM influencer_database{where} "
                f"ORDER BY {sort_by} {direction} LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        rows = [dict(r) for r in data_result.mappings().fetchall()]

        return {
            "influencers": rows,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size if page_size else 1,
        }

    @staticmethod
    async def get_detailed(
        db: AsyncSession,
        identifier: str,
    ) -> Dict[str, Any]:
        """
        Get detailed influencer data. DB-only — no external API calls.
        Checks: influencer_database -> profiles table.
        """
        clean = identifier.lower().lstrip("@")
        row = None

        # Try UUID lookup in influencer_database
        try:
            UUID(identifier)
            result = await db.execute(
                text("SELECT * FROM influencer_database WHERE id = CAST(:id AS uuid)"),
                {"id": identifier},
            )
            row = result.mappings().fetchone()
        except (ValueError, AttributeError):
            pass

        # Try username lookup in influencer_database
        if row is None:
            result = await db.execute(
                text("SELECT * FROM influencer_database WHERE username = :u"),
                {"u": clean},
            )
            row = result.mappings().fetchone()

        if row:
            return {"source": "database", "influencer": dict(row)}

        # Not in influencer_database — check profiles table (our full analytics DB)
        profile_data = await InfluencerDatabaseService._get_from_profiles_table(db, clean)
        if profile_data:
            return {
                "source": "profiles_preview",
                "influencer": profile_data,
                "message": "Found in analytics database. Click 'Add to Database' to import.",
            }

        # Not found anywhere
        raise ValueError(f"Influencer '{identifier}' not found. Use 'Add' to fetch from Instagram.")

    # =========================================================================
    # UPDATE / DELETE / REFRESH
    # =========================================================================

    @staticmethod
    async def update_influencer(
        db: AsyncSession,
        influencer_id: UUID,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Partial update — flatten nested pricing objects to columns."""
        set_clauses = []
        params: Dict[str, Any] = {"id": str(influencer_id)}

        # Flatten cost_pricing
        cost = data.pop("cost_pricing", None)
        if cost and isinstance(cost, dict):
            for k, v in cost.items():
                if v is not None:
                    set_clauses.append(f"{k} = :{k}")
                    params[k] = v

        # Flatten sell_pricing
        sell = data.pop("sell_pricing", None)
        if sell and isinstance(sell, dict):
            for k, v in sell.items():
                if v is not None:
                    set_clauses.append(f"{k} = :{k}")
                    params[k] = v

        # Direct columns — with explicit CASTs for array/JSONB types
        allowed = {
            "full_name", "status", "tier", "categories", "tags",
            "internal_notes", "auto_calculate_sell", "default_markup_percentage",
            "package_pricing", "volume_discounts",
        }
        cast_map = {
            "categories": "text[]",
            "tags": "text[]",
            "package_pricing": "jsonb",
            "volume_discounts": "jsonb",
        }
        for key, val in data.items():
            if key in allowed and val is not None:
                if key in cast_map:
                    if cast_map[key] == "jsonb":
                        set_clauses.append(f"{key} = CAST(:{key} AS jsonb)")
                        params[key] = json.dumps(val) if not isinstance(val, str) else val
                    else:
                        set_clauses.append(f"{key} = CAST(:{key} AS {cast_map[key]})")
                        params[key] = val
                else:
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = val

        if not set_clauses:
            raise ValueError("No valid fields to update")

        set_clauses.append("updated_at = NOW()")
        sql = (
            f"UPDATE influencer_database SET {', '.join(set_clauses)} "
            f"WHERE id = CAST(:id AS uuid) RETURNING *"
        )
        result = await db.execute(text(sql), params)
        await db.commit()
        row = result.mappings().fetchone()
        if not row:
            raise ValueError("Influencer not found")
        return dict(row)

    @staticmethod
    async def delete_influencer(db: AsyncSession, influencer_id: UUID) -> bool:
        """Delete influencer and clean up share references."""
        iid = str(influencer_id)

        # Remove from shares
        await db.execute(
            text("""
                UPDATE influencer_access_shares
                SET influencer_ids = array_remove(influencer_ids, CAST(:iid AS uuid)),
                    updated_at = NOW()
                WHERE CAST(:iid AS uuid) = ANY(influencer_ids)
            """),
            {"iid": iid},
        )

        result = await db.execute(
            text("DELETE FROM influencer_database WHERE id = CAST(:id AS uuid)"),
            {"id": iid},
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def refresh_influencer(
        db: AsyncSession, influencer_id: UUID
    ) -> Dict[str, Any]:
        """
        Re-sync from profiles table. No external API calls.
        If the influencer now has analytics in profiles (e.g. a user searched for them),
        pull that data into the IMD record.
        """
        iid = str(influencer_id)
        result = await db.execute(
            text("SELECT username FROM influencer_database WHERE id = CAST(:id AS uuid)"),
            {"id": iid},
        )
        row = result.fetchone()
        if not row:
            raise ValueError("Influencer not found")

        username = row[0]

        # Check profiles table for analytics data
        ig_data = await InfluencerDatabaseService._get_from_profiles_table(db, username)

        if not ig_data:
            raise ValueError(
                f"No analytics available for @{username}. "
                f"Search for this influencer in Creator Analytics first to generate data."
            )

        update_result = await db.execute(
            text("""
                UPDATE influencer_database SET
                    full_name = :full_name,
                    biography = :biography,
                    profile_image_url = :profile_image_url,
                    is_verified = :is_verified,
                    is_private = :is_private,
                    followers_count = :followers_count,
                    following_count = :following_count,
                    posts_count = :posts_count,
                    engagement_rate = :engagement_rate,
                    avg_likes = :avg_likes,
                    avg_comments = :avg_comments,
                    avg_views = :avg_views,
                    ai_content_categories = CAST(:ai_content_categories AS text[]),
                    ai_sentiment_score = :ai_sentiment_score,
                    ai_audience_quality_score = :ai_audience_quality_score,
                    language_distribution = CAST(:language_distribution AS jsonb),
                    last_analytics_refresh = NOW(),
                    updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
                RETURNING *
            """),
            {
                "id": iid,
                "full_name": ig_data.get("full_name"),
                "biography": ig_data.get("biography"),
                "profile_image_url": ig_data.get("profile_image_url"),
                "is_verified": ig_data.get("is_verified", False),
                "is_private": ig_data.get("is_private", False),
                "followers_count": ig_data.get("followers_count", 0),
                "following_count": ig_data.get("following_count", 0),
                "posts_count": ig_data.get("posts_count", 0),
                "engagement_rate": ig_data.get("engagement_rate", 0),
                "avg_likes": ig_data.get("avg_likes", 0),
                "avg_comments": ig_data.get("avg_comments", 0),
                "avg_views": ig_data.get("avg_views", 0),
                "ai_content_categories": ig_data.get("ai_content_categories", []),
                "ai_sentiment_score": ig_data.get("ai_sentiment_score"),
                "ai_audience_quality_score": ig_data.get("ai_audience_quality_score"),
                "language_distribution": json.dumps(ig_data["language_distribution"]) if ig_data.get("language_distribution") else None,
            },
        )
        await db.commit()
        row = update_result.mappings().fetchone()
        return dict(row) if row else {}

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    @staticmethod
    async def bulk_tag(
        db: AsyncSession,
        influencer_ids: List[UUID],
        tags: List[str],
        action: str = "add",
    ) -> int:
        """Bulk add or remove tags. Returns count of updated rows."""
        ids = [str(i) for i in influencer_ids]

        if action == "add":
            result = await db.execute(
                text("""
                    UPDATE influencer_database
                    SET tags = (
                        SELECT ARRAY(SELECT DISTINCT unnest(array_cat(tags, CAST(:tags AS text[]))))
                    ),
                    updated_at = NOW()
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                """),
                {"tags": tags, "ids": ids},
            )
        else:
            result = await db.execute(
                text("""
                    UPDATE influencer_database
                    SET tags = (
                        SELECT ARRAY(
                            SELECT unnest(tags)
                            EXCEPT
                            SELECT unnest(CAST(:tags AS text[]))
                        )
                    ),
                    updated_at = NOW()
                    WHERE id = ANY(CAST(:ids AS uuid[]))
                """),
                {"tags": tags, "ids": ids},
            )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def bulk_pricing(
        db: AsyncSession,
        updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Bulk pricing update per influencer."""
        updated = 0
        failed = []

        for item in updates:
            iid = str(item["influencer_id"])
            set_clauses = []
            params: Dict[str, Any] = {"id": iid}

            cost = item.get("cost_pricing") or {}
            if isinstance(cost, dict):
                for k, v in cost.items():
                    if v is not None:
                        set_clauses.append(f"{k} = :{k}")
                        params[k] = v

            sell = item.get("sell_pricing") or {}
            if isinstance(sell, dict):
                for k, v in sell.items():
                    if v is not None:
                        set_clauses.append(f"{k} = :{k}")
                        params[k] = v

            if not set_clauses:
                continue

            set_clauses.append("updated_at = NOW()")
            try:
                await db.execute(
                    text(
                        f"UPDATE influencer_database SET {', '.join(set_clauses)} "
                        f"WHERE id = CAST(:id AS uuid)"
                    ),
                    params,
                )
                updated += 1
            except Exception as e:
                failed.append({"influencer_id": iid, "error": str(e)})

        await db.commit()
        return {"updated": updated, "failed": failed}

    # =========================================================================
    # EXPORT
    # =========================================================================

    @staticmethod
    async def export_influencers(
        db: AsyncSession,
        format: str = "csv",
        fields: Optional[Dict[str, bool]] = None,
        scope: str = "all",
        selected_ids: Optional[List[UUID]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, str]:
        """Export influencers. Returns (content, media_type, filename)."""
        conditions = []
        params: Dict[str, Any] = {}

        if scope == "selected" and selected_ids:
            conditions.append("id = ANY(CAST(:ids AS uuid[]))")
            params["ids"] = [str(i) for i in selected_ids]
        elif scope == "filtered" and filters:
            if filters.get("status"):
                conditions.append("status = :f_status")
                params["f_status"] = filters["status"]
            if filters.get("tags"):
                conditions.append("tags && CAST(:f_tags AS text[])")
                params["f_tags"] = filters["tags"]
            if filters.get("min_followers"):
                conditions.append("followers_count >= :f_min")
                params["f_min"] = filters["min_followers"]

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        result = await db.execute(
            text(f"SELECT * FROM influencer_database{where} ORDER BY created_at DESC"),
            params,
        )
        rows = [dict(r) for r in result.mappings().fetchall()]

        # Field filtering
        if fields:
            enabled = {k for k, v in fields.items() if v}
            if enabled:
                rows = [{k: v for k, v in row.items() if k in enabled} for row in rows]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if format == "json":
            content = json.dumps(rows, default=str, indent=2)
            return content, "application/json", f"influencers_export_{timestamp}.json"

        # CSV
        if not rows:
            return "", "text/csv", f"influencers_export_{timestamp}.csv"

        output = io.StringIO()
        writer = csv.writer(output)
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([str(row.get(h, "")) for h in headers])

        return output.getvalue(), "text/csv", f"influencers_export_{timestamp}.csv"

    # =========================================================================
    # TAGS
    # =========================================================================

    @staticmethod
    async def get_all_tags(db: AsyncSession) -> List[str]:
        """Get all unique tags across all influencers."""
        result = await db.execute(
            text("SELECT DISTINCT unnest(tags) AS tag FROM influencer_database ORDER BY 1")
        )
        return [r[0] for r in result.fetchall()]

    # =========================================================================
    # SHARES
    # =========================================================================

    @staticmethod
    async def create_share(
        db: AsyncSession,
        name: str,
        created_by: UUID,
        influencer_ids: List[UUID],
        user_emails: List[str],
        description: Optional[str] = None,
        visible_fields: Optional[Dict[str, Any]] = None,
        duration: str = "30d",
    ) -> Dict[str, Any]:
        """Create a share with associated user access records."""
        expires_at = InfluencerDatabaseService._parse_duration(duration)

        default_visible = {
            "show_analytics": True,
            "show_sell_pricing": False,
            "show_engagement": True,
            "show_audience": True,
            "show_content_analysis": True,
            "show_contact_info": False,
        }
        vf = visible_fields or default_visible
        inf_ids = [str(i) for i in influencer_ids]

        result = await db.execute(
            text("""
                INSERT INTO influencer_access_shares
                    (name, description, influencer_ids, visible_fields, duration,
                     is_active, created_by, expires_at)
                VALUES
                    (:name, :description, CAST(:inf_ids AS uuid[]),
                     CAST(:visible_fields AS jsonb), :duration,
                     TRUE, CAST(:created_by AS uuid), :expires_at)
                RETURNING *
            """),
            {
                "name": name,
                "description": description,
                "inf_ids": inf_ids,
                "visible_fields": json.dumps(vf),
                "duration": duration,
                "created_by": str(created_by),
                "expires_at": expires_at,
            },
        )
        share_row = result.mappings().fetchone()
        share_id = str(share_row["id"])

        for email in user_emails:
            await db.execute(
                text("""
                    INSERT INTO influencer_share_users (share_id, user_email, expires_at)
                    VALUES (CAST(:share_id AS uuid), :email, :expires_at)
                """),
                {"share_id": share_id, "email": email, "expires_at": expires_at},
            )

        await db.commit()
        return dict(share_row)

    @staticmethod
    async def list_shares(db: AsyncSession) -> List[Dict[str, Any]]:
        """List all shares with their associated users."""
        result = await db.execute(
            text("SELECT * FROM influencer_access_shares ORDER BY created_at DESC")
        )
        shares = [dict(r) for r in result.mappings().fetchall()]

        for share in shares:
            users_result = await db.execute(
                text("SELECT * FROM influencer_share_users WHERE share_id = CAST(:sid AS uuid)"),
                {"sid": str(share["id"])},
            )
            share["shared_with_users"] = [dict(u) for u in users_result.mappings().fetchall()]

        return shares

    @staticmethod
    async def update_share(
        db: AsyncSession,
        share_id: UUID,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Partial update a share. Handle user_emails diff if provided."""
        sid = str(share_id)
        set_clauses = []
        params: Dict[str, Any] = {"id": sid}

        simple_fields = {"name", "description", "duration", "is_active"}
        for key in simple_fields:
            if key in data and data[key] is not None:
                set_clauses.append(f"{key} = :{key}")
                params[key] = data[key]

        if "influencer_ids" in data and data["influencer_ids"] is not None:
            set_clauses.append("influencer_ids = CAST(:inf_ids AS uuid[])")
            params["inf_ids"] = [str(i) for i in data["influencer_ids"]]

        if "visible_fields" in data and data["visible_fields"] is not None:
            set_clauses.append("visible_fields = CAST(:vf AS jsonb)")
            params["vf"] = json.dumps(data["visible_fields"])

        if set_clauses:
            set_clauses.append("updated_at = NOW()")
            sql = (
                f"UPDATE influencer_access_shares SET {', '.join(set_clauses)} "
                f"WHERE id = CAST(:id AS uuid) RETURNING *"
            )
            result = await db.execute(text(sql), params)
            row = result.mappings().fetchone()
            if not row:
                raise ValueError("Share not found")

        # Handle user_emails diff
        if "user_emails" in data and data["user_emails"] is not None:
            new_emails = set(data["user_emails"])
            existing = await db.execute(
                text("SELECT user_email FROM influencer_share_users WHERE share_id = CAST(:sid AS uuid)"),
                {"sid": sid},
            )
            current_emails = {r[0] for r in existing.fetchall()}

            to_remove = current_emails - new_emails
            if to_remove:
                await db.execute(
                    text("""
                        DELETE FROM influencer_share_users
                        WHERE share_id = CAST(:sid AS uuid) AND user_email = ANY(:emails)
                    """),
                    {"sid": sid, "emails": list(to_remove)},
                )

            to_add = new_emails - current_emails
            share_result = await db.execute(
                text("SELECT expires_at FROM influencer_access_shares WHERE id = CAST(:sid AS uuid)"),
                {"sid": sid},
            )
            share_row = share_result.fetchone()
            exp = share_row[0] if share_row else None

            for email in to_add:
                await db.execute(
                    text("""
                        INSERT INTO influencer_share_users (share_id, user_email, expires_at)
                        VALUES (CAST(:sid AS uuid), :email, :exp)
                    """),
                    {"sid": sid, "email": email, "exp": exp},
                )

        await db.commit()

        result = await db.execute(
            text("SELECT * FROM influencer_access_shares WHERE id = CAST(:id AS uuid)"),
            {"id": sid},
        )
        row = result.mappings().fetchone()
        if not row:
            raise ValueError("Share not found")
        return dict(row)

    @staticmethod
    async def revoke_share(db: AsyncSession, share_id: UUID) -> bool:
        """Revoke a share (set is_active=false)."""
        result = await db.execute(
            text("""
                UPDATE influencer_access_shares
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(share_id)},
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def extend_share(
        db: AsyncSession, share_id: UUID, expires_at: datetime
    ) -> Dict[str, Any]:
        """Extend a share's expiration date."""
        sid = str(share_id)
        result = await db.execute(
            text("""
                UPDATE influencer_access_shares
                SET expires_at = :exp, updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
                RETURNING *
            """),
            {"id": sid, "exp": expires_at},
        )
        row = result.mappings().fetchone()
        if not row:
            raise ValueError("Share not found")

        await db.execute(
            text("""
                UPDATE influencer_share_users
                SET expires_at = :exp
                WHERE share_id = CAST(:sid AS uuid)
            """),
            {"sid": sid, "exp": expires_at},
        )
        await db.commit()
        return dict(row)

    # =========================================================================
    # SHARED ACCESS (User-facing)
    # =========================================================================

    @staticmethod
    async def get_shared_influencers(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
    ) -> List[Dict[str, Any]]:
        """
        Get influencers shared with a user. Applies visible_fields filtering.
        NEVER returns cost_pricing or internal_notes.
        """
        now = datetime.now(timezone.utc)

        shares_result = await db.execute(
            text("""
                SELECT s.*, su.access_level
                FROM influencer_access_shares s
                JOIN influencer_share_users su ON su.share_id = s.id
                WHERE s.is_active = TRUE
                  AND (s.expires_at IS NULL OR s.expires_at > :now)
                  AND (su.expires_at IS NULL OR su.expires_at > :now)
                  AND (su.user_id = CAST(:uid AS uuid) OR su.user_email = :email)
            """),
            {"now": now, "uid": str(user_id), "email": user_email},
        )
        shares = shares_result.mappings().fetchall()

        if not shares:
            return []

        all_influencers = []
        seen_ids = set()

        for share in shares:
            inf_ids = share["influencer_ids"]
            if not inf_ids:
                continue

            # Increment access count
            await db.execute(
                text("""
                    UPDATE influencer_access_shares
                    SET access_count = access_count + 1, last_accessed_at = :now
                    WHERE id = CAST(:sid AS uuid)
                """),
                {"now": now, "sid": str(share["id"])},
            )

            id_strs = [str(i) for i in inf_ids]
            inf_result = await db.execute(
                text("SELECT * FROM influencer_database WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": id_strs},
            )
            influencers = [dict(r) for r in inf_result.mappings().fetchall()]

            visible = share["visible_fields"] or {}

            for inf in influencers:
                if inf["id"] in seen_ids:
                    continue
                seen_ids.add(inf["id"])

                # ALWAYS strip cost pricing and internal notes
                filtered = {
                    "id": inf["id"],
                    "username": inf["username"],
                    "full_name": inf.get("full_name"),
                    "biography": inf.get("biography"),
                    "profile_image_url": inf.get("profile_image_url"),
                    "is_verified": inf.get("is_verified", False),
                    "is_private": inf.get("is_private", False),
                    "followers_count": inf.get("followers_count", 0),
                    "following_count": inf.get("following_count", 0),
                    "posts_count": inf.get("posts_count", 0),
                    "status": inf.get("status"),
                    "tier": inf.get("tier"),
                    "categories": inf.get("categories", []),
                    "tags": inf.get("tags", []),
                }

                if visible.get("show_engagement", True):
                    filtered["engagement_rate"] = inf.get("engagement_rate")
                    filtered["avg_likes"] = inf.get("avg_likes")
                    filtered["avg_comments"] = inf.get("avg_comments")
                    filtered["avg_views"] = inf.get("avg_views")

                if visible.get("show_sell_pricing", False):
                    for k in [
                        "sell_post_usd_cents", "sell_story_usd_cents",
                        "sell_reel_usd_cents", "sell_carousel_usd_cents",
                        "sell_video_usd_cents", "sell_bundle_usd_cents",
                        "sell_monthly_usd_cents",
                    ]:
                        filtered[k] = inf.get(k)

                if visible.get("show_content_analysis", True):
                    filtered["ai_content_categories"] = inf.get("ai_content_categories")
                    filtered["ai_sentiment_score"] = inf.get("ai_sentiment_score")
                    filtered["language_distribution"] = inf.get("language_distribution")

                all_influencers.append(filtered)

        await db.commit()
        return all_influencers

    # =========================================================================
    # USER-FACING: SHARED LISTS
    # =========================================================================

    @staticmethod
    async def get_user_shared_lists(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
    ) -> List[Dict[str, Any]]:
        """
        Get share list summaries for a user. Returns share metadata + influencer count.
        Does NOT return the actual influencer data (use get_user_shared_list_detail for that).
        """
        now = datetime.now(timezone.utc)

        result = await db.execute(
            text("""
                SELECT
                    s.id,
                    s.name,
                    s.description,
                    s.visible_fields,
                    s.duration,
                    s.is_active,
                    s.expires_at,
                    s.created_at,
                    array_length(s.influencer_ids, 1) AS influencer_count,
                    su.access_level,
                    su.granted_at
                FROM influencer_access_shares s
                JOIN influencer_share_users su ON su.share_id = s.id
                WHERE s.is_active = TRUE
                  AND (s.expires_at IS NULL OR s.expires_at > :now)
                  AND (su.expires_at IS NULL OR su.expires_at > :now)
                  AND (su.user_id = CAST(:uid AS uuid) OR su.user_email = :email)
                ORDER BY s.created_at DESC
            """),
            {"now": now, "uid": str(user_id), "email": user_email},
        )
        return [dict(r) for r in result.mappings().fetchall()]

    @staticmethod
    async def get_user_shared_list_detail(
        db: AsyncSession,
        share_id: UUID,
        user_id: UUID,
        user_email: str,
    ) -> Dict[str, Any]:
        """
        Get full detail for a specific share: share metadata + filtered influencer data.
        Verifies user has access. Applies visible_fields filtering.
        """
        now = datetime.now(timezone.utc)
        sid = str(share_id)

        # Verify access and get share
        share_result = await db.execute(
            text("""
                SELECT s.*
                FROM influencer_access_shares s
                JOIN influencer_share_users su ON su.share_id = s.id
                WHERE s.id = CAST(:sid AS uuid)
                  AND s.is_active = TRUE
                  AND (s.expires_at IS NULL OR s.expires_at > :now)
                  AND (su.expires_at IS NULL OR su.expires_at > :now)
                  AND (su.user_id = CAST(:uid AS uuid) OR su.user_email = :email)
            """),
            {"sid": sid, "now": now, "uid": str(user_id), "email": user_email},
        )
        share = share_result.mappings().fetchone()
        if not share:
            raise ValueError("Share not found or access denied")

        share_dict = dict(share)

        # Increment access count
        await db.execute(
            text("""
                UPDATE influencer_access_shares
                SET access_count = access_count + 1, last_accessed_at = :now
                WHERE id = CAST(:sid AS uuid)
            """),
            {"now": now, "sid": sid},
        )

        # Get influencers with visible_fields filtering
        inf_ids = share_dict.get("influencer_ids") or []
        if not inf_ids:
            await db.commit()
            return {
                "share": {
                    "id": share_dict["id"],
                    "name": share_dict["name"],
                    "description": share_dict.get("description"),
                    "expires_at": share_dict.get("expires_at"),
                    "created_at": share_dict.get("created_at"),
                    "influencer_count": 0,
                },
                "influencers": [],
            }

        id_strs = [str(i) for i in inf_ids]
        inf_result = await db.execute(
            text("SELECT * FROM influencer_database WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": id_strs},
        )
        influencers = [dict(r) for r in inf_result.mappings().fetchall()]
        visible = share_dict.get("visible_fields") or {}

        filtered_influencers = []
        for inf in influencers:
            filtered = {
                "id": inf["id"],
                "username": inf["username"],
                "full_name": inf.get("full_name"),
                "biography": inf.get("biography"),
                "profile_image_url": inf.get("profile_image_url"),
                "is_verified": inf.get("is_verified", False),
                "is_private": inf.get("is_private", False),
                "followers_count": inf.get("followers_count", 0),
                "following_count": inf.get("following_count", 0),
                "posts_count": inf.get("posts_count", 0),
                "status": inf.get("status"),
                "tier": inf.get("tier"),
                "categories": inf.get("categories", []),
                "tags": inf.get("tags", []),
            }

            if visible.get("show_engagement", True):
                filtered["engagement_rate"] = inf.get("engagement_rate")
                filtered["avg_likes"] = inf.get("avg_likes")
                filtered["avg_comments"] = inf.get("avg_comments")
                filtered["avg_views"] = inf.get("avg_views")

            if visible.get("show_sell_pricing", False):
                for k in [
                    "sell_post_usd_cents", "sell_story_usd_cents",
                    "sell_reel_usd_cents", "sell_carousel_usd_cents",
                    "sell_video_usd_cents", "sell_bundle_usd_cents",
                    "sell_monthly_usd_cents",
                ]:
                    filtered[k] = inf.get(k)

            if visible.get("show_content_analysis", True):
                filtered["ai_content_categories"] = inf.get("ai_content_categories")
                filtered["ai_sentiment_score"] = inf.get("ai_sentiment_score")
                filtered["language_distribution"] = inf.get("language_distribution")

            filtered_influencers.append(filtered)

        await db.commit()
        return {
            "share": {
                "id": share_dict["id"],
                "name": share_dict["name"],
                "description": share_dict.get("description"),
                "visible_fields": visible,
                "expires_at": share_dict.get("expires_at"),
                "created_at": share_dict.get("created_at"),
                "influencer_count": len(filtered_influencers),
            },
            "influencers": filtered_influencers,
        }

    # =========================================================================
    # PRICING SYNC
    # =========================================================================

    @staticmethod
    async def sync_pricing(
        db: AsyncSession,
        influencer_id: UUID,
        pricing_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Write pricing to influencer_database from proposal context."""
        set_clauses = []
        params: Dict[str, Any] = {"id": str(influencer_id)}

        pricing_fields = [
            "cost_post_usd_cents", "cost_story_usd_cents", "cost_reel_usd_cents",
            "cost_carousel_usd_cents", "cost_video_usd_cents", "cost_bundle_usd_cents",
            "cost_monthly_usd_cents", "sell_post_usd_cents", "sell_story_usd_cents",
            "sell_reel_usd_cents", "sell_carousel_usd_cents", "sell_video_usd_cents",
            "sell_bundle_usd_cents", "sell_monthly_usd_cents",
        ]

        for field in pricing_fields:
            if field in pricing_data and pricing_data[field] is not None:
                set_clauses.append(f"{field} = :{field}")
                params[field] = pricing_data[field]

        if not set_clauses:
            raise ValueError("No pricing fields provided")

        set_clauses.append("updated_at = NOW()")
        result = await db.execute(
            text(
                f"UPDATE influencer_database SET {', '.join(set_clauses)} "
                f"WHERE id = CAST(:id AS uuid) RETURNING *"
            ),
            params,
        )
        await db.commit()
        row = result.mappings().fetchone()
        if not row:
            raise ValueError("Influencer not found")
        return dict(row)

    # =========================================================================
    # INTERNAL: DATA SOURCES
    # =========================================================================

    @staticmethod
    async def _get_from_profiles_table(
        db: AsyncSession, username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check the profiles table for existing Creator Analytics data.
        This is our full analytics DB with engagement, AI, CDN, etc.
        Returns a flat dict suitable for influencer_database, or None.
        """
        result = await db.execute(
            text("""
                SELECT
                    p.username,
                    p.full_name,
                    p.biography,
                    COALESCE(p.cdn_avatar_url, p.profile_pic_url_hd, p.profile_pic_url) AS profile_image_url,
                    p.is_verified,
                    p.is_private,
                    p.followers_count,
                    p.following_count,
                    p.posts_count,
                    p.engagement_rate,
                    p.detected_country,
                    p.category,
                    p.ai_avg_sentiment_score,
                    p.ai_content_distribution,
                    p.ai_language_distribution,
                    p.ai_top_3_categories,
                    p.ai_profile_analyzed_at,
                    p.ai_content_quality_score,
                    p.ai_audience_quality,
                    p.ai_fraud_detection,
                    p.ai_comprehensive_analyzed_at,
                    p.ai_models_success_rate
                FROM profiles p
                WHERE p.username = :u
            """),
            {"u": username},
        )
        row = result.mappings().fetchone()
        if not row:
            return None

        data = dict(row)

        # Calculate avg_likes / avg_comments from posts table
        post_stats = await db.execute(
            text("""
                SELECT
                    CAST(COALESCE(AVG(likes_count), 0) AS bigint) AS avg_likes,
                    CAST(COALESCE(AVG(comments_count), 0) AS bigint) AS avg_comments,
                    CAST(COALESCE(AVG(CASE WHEN is_video THEN video_view_count ELSE 0 END), 0) AS bigint) AS avg_views
                FROM posts
                WHERE profile_id = (SELECT id FROM profiles WHERE username = :u)
            """),
            {"u": username},
        )
        stats = post_stats.mappings().fetchone()
        if stats:
            data["avg_likes"] = stats["avg_likes"] or 0
            data["avg_comments"] = stats["avg_comments"] or 0
            data["avg_views"] = stats["avg_views"] or 0

        # Map AI fields to influencer_database format
        top3 = data.get("ai_top_3_categories")
        if top3 and isinstance(top3, list):
            data["ai_content_categories"] = [c.get("category", "") for c in top3 if isinstance(c, dict)]
            # Also use as default categories
            data["categories"] = data["ai_content_categories"][:3]
        else:
            data["ai_content_categories"] = []
            data["categories"] = [data["category"]] if data.get("category") else []

        data["ai_sentiment_score"] = data.pop("ai_avg_sentiment_score", None)

        # Extract audience quality score from JSONB
        aq = data.pop("ai_audience_quality", None)
        if aq and isinstance(aq, dict):
            data["ai_audience_quality_score"] = aq.get("authenticity_score")
        else:
            data["ai_audience_quality_score"] = None

        data["language_distribution"] = data.pop("ai_language_distribution", None)

        return data

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _parse_duration(duration: str) -> Optional[datetime]:
        """Parse duration string like '7d', '30d', '90d' to expiry datetime."""
        if not duration:
            return None
        try:
            if duration.endswith("d"):
                days = int(duration[:-1])
                return datetime.now(timezone.utc) + timedelta(days=days)
            elif duration.endswith("m"):
                months = int(duration[:-1])
                return datetime.now(timezone.utc) + timedelta(days=months * 30)
        except (ValueError, IndexError):
            pass
        return datetime.now(timezone.utc) + timedelta(days=30)
