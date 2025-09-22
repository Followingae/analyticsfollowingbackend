# app/services/cdn_sync_repair_service.py

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CDNSyncRepairService:
    """Service for detecting and repairing CDN database sync gaps"""

    def __init__(self):
        pass  # No initialization needed, uses dependency injection

    async def detect_sync_gaps(self, db: AsyncSession, max_age_hours: int = 2) -> List[Dict]:
        """
        Find records where files exist in R2 but DB shows pending/processing
        """
        logger.info(f"Starting sync gap detection for assets older than {max_age_hours} hours")

        # Get pending assets older than specified hours
        pending_assets = await self._get_pending_assets(db, max_age_hours)
        logger.info(f"Found {len(pending_assets)} pending assets to check")

        if not pending_assets:
            return []

        # Verify which files actually exist in R2
        verified_gaps = []
        for asset in pending_assets:
            gap_info = await self._verify_single_asset(asset)
            if gap_info:
                verified_gaps.append(gap_info)

        logger.info(f"Identified {len(verified_gaps)} confirmed sync gaps")
        return verified_gaps

    async def _get_pending_assets(self, db: AsyncSession, max_age_hours: int) -> List[Dict]:
        """Get all pending/processing CDN assets older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        query = text("""
            SELECT
                c.id as asset_id,
                c.source_type,
                c.source_id,
                c.media_id,
                c.processing_status,
                c.created_at,
                p.username
            FROM cdn_image_assets c
            LEFT JOIN profiles p ON c.source_id = p.id
            WHERE c.processing_status IN ('pending', 'processing', 'queued')
              AND c.created_at < :cutoff_time
              AND c.cdn_path_512 IS NULL
            ORDER BY c.created_at DESC
        """)

        result = await db.execute(query, {"cutoff_time": cutoff_time})
        return [
            {
                "asset_id": str(row.asset_id),
                "source_type": row.source_type,
                "source_id": str(row.source_id),
                "media_id": row.media_id,
                "processing_status": row.processing_status,
                "created_at": row.created_at,
                "username": row.username
            }
            for row in result.fetchall()
        ]

    async def _verify_single_asset(self, asset: Dict) -> Optional[Dict]:
        """Verify if a single asset exists in R2 storage using our MCP integration"""
        try:
            # Construct expected R2 path
            expected_path = self._construct_cdn_path(asset)
            if not expected_path:
                return None

            # Check if file exists in R2 using our existing MCP integration
            file_info = await self._check_r2_file_exists(expected_path)

            if file_info["exists"]:
                return {
                    "asset_id": asset["asset_id"],
                    "media_id": asset["media_id"],
                    "username": asset["username"],
                    "source_type": asset["source_type"],
                    "expected_path": expected_path,
                    "file_info": file_info,
                    "created_at": asset["created_at"]
                }

            return None

        except Exception as e:
            logger.error(f"Error verifying asset {asset['asset_id']}: {str(e)}")
            return None

    def _construct_cdn_path(self, asset: Dict) -> Optional[str]:
        """Construct expected R2 path from asset data"""
        username = asset.get("username")
        if not username:
            logger.warning(f"No username found for asset {asset['asset_id']}")
            return None

        if asset["source_type"] == "post_thumbnail":
            # thumbnails/ig/{username}/{shortcode}/512.webp
            media_id = asset["media_id"]  # e.g., "shortcode_C3lTQB1NtVX"
            return f"thumbnails/ig/{username}/{media_id}/512.webp"

        elif asset["source_type"] == "instagram_profile":
            # profiles/ig/{username}/profile_picture.webp
            return f"profiles/ig/{username}/profile_picture.webp"

        else:
            logger.warning(f"Unknown source_type: {asset['source_type']}")
            return None

    async def _check_r2_file_exists(self, path: str) -> Dict:
        """Check if file exists in R2 storage using existing MCP integration"""
        try:
            # Import the MCP function at runtime to avoid initialization issues
            

            # Use our existing MCP integration to check file existence
            result = mcp__cloudflare__r2_list_objects(
                bucket="thumbnails-prod",
                prefix=path,
                limit=1
            )

            if result.get("result") and len(result["result"]) > 0:
                file_obj = result["result"][0]
                return {
                    "exists": True,
                    "size": file_obj.get("size"),
                    "etag": file_obj.get("etag"),
                    "last_modified": file_obj.get("last_modified")
                }
            else:
                return {"exists": False}

        except Exception as e:
            logger.error(f"Error checking R2 file {path}: {str(e)}")
            return {"exists": False, "error": str(e)}

    async def repair_sync_gaps(self, db: AsyncSession, gaps: List[Dict]) -> Dict:
        """Repair identified sync gaps"""
        results = {
            "repaired": 0,
            "failed": 0,
            "errors": [],
            "repaired_assets": []
        }

        logger.info(f"Starting repair of {len(gaps)} sync gaps")

        for gap in gaps:
            try:
                await self._repair_single_asset(db, gap)
                results["repaired"] += 1
                results["repaired_assets"].append({
                    "asset_id": gap["asset_id"],
                    "media_id": gap["media_id"],
                    "username": gap["username"]
                })
                logger.info(f"Repaired asset {gap['asset_id']} ({gap['media_id']})")

            except Exception as e:
                error_msg = f"{gap['media_id']}: {str(e)}"
                results["failed"] += 1
                results["errors"].append(error_msg)
                logger.error(f"Failed to repair asset {gap['asset_id']}: {str(e)}")

        await db.commit()
        logger.info(f"Sync repair completed: {results['repaired']} repaired, {results['failed']} failed")
        return results

    async def _repair_single_asset(self, db: AsyncSession, gap: Dict):
        """Repair a single asset record"""
        asset_id = gap["asset_id"]
        expected_path = gap["expected_path"]
        file_info = gap["file_info"]

        # Construct CDN URL
        cdn_url = f"https://cdn.following.ae/{expected_path}"

        # Update asset record
        update_query = text("""
            UPDATE cdn_image_assets
            SET cdn_path_512 = :cdn_path,
                cdn_url_512 = :cdn_url,
                processing_status = 'completed',
                processing_completed_at = :completed_at,
                file_size_512 = :file_size,
                updated_at = :updated_at
            WHERE id = :asset_id
        """)

        await db.execute(update_query, {
            "cdn_path": expected_path,
            "cdn_url": cdn_url,
            "completed_at": datetime.utcnow(),
            "file_size": file_info.get("size"),
            "updated_at": datetime.utcnow(),
            "asset_id": asset_id
        })

        # Update corresponding job status if exists
        job_update_query = text("""
            UPDATE cdn_image_jobs
            SET status = 'completed',
                completed_at = :completed_at,
                updated_at = :updated_at
            WHERE asset_id = :asset_id
        """)

        await db.execute(job_update_query, {
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "asset_id": asset_id
        })

    async def get_sync_health_report(self, db: AsyncSession) -> Dict:
        """Generate comprehensive sync health report"""
        # Count various asset states
        pending_count = await self._count_assets_by_status(db, ['pending', 'processing', 'queued'])
        completed_count = await self._count_assets_by_status(db, ['completed'])
        failed_count = await self._count_assets_by_status(db, ['failed', 'error'])

        # Find old pending assets (potential gaps)
        old_pending = await self._count_old_pending_assets(db, hours=24)

        return {
            "total_assets": pending_count + completed_count + failed_count,
            "pending_assets": pending_count,
            "completed_assets": completed_count,
            "failed_assets": failed_count,
            "potential_sync_gaps": old_pending,
            "last_check": datetime.utcnow().isoformat(),
            "health_score": self._calculate_health_score(
                completed_count, pending_count, failed_count, old_pending
            )
        }

    async def _count_assets_by_status(self, db: AsyncSession, statuses: List[str]) -> int:
        """Count assets by status"""
        query = text("""
            SELECT COUNT(*) as count
            FROM cdn_image_assets
            WHERE processing_status = ANY(:statuses)
        """)
        result = await db.execute(query, {"statuses": statuses})
        return result.scalar() or 0

    async def _count_old_pending_assets(self, db: AsyncSession, hours: int) -> int:
        """Count pending assets older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        query = text("""
            SELECT COUNT(*) as count
            FROM cdn_image_assets
            WHERE processing_status IN ('pending', 'processing', 'queued')
              AND created_at < :cutoff_time
        """)
        result = await db.execute(query, {"cutoff_time": cutoff_time})
        return result.scalar() or 0

    def _calculate_health_score(self, completed: int, pending: int, failed: int, old_pending: int) -> float:
        """Calculate overall sync health score (0-100)"""
        total = completed + pending + failed
        if total == 0:
            return 100.0

        # Base score from completion rate
        completion_rate = completed / total

        # Penalty for old pending (potential gaps)
        gap_penalty = min(old_pending / total, 0.3) if total > 0 else 0

        # Penalty for failures
        failure_penalty = min(failed / total, 0.2) if total > 0 else 0

        health_score = (completion_rate - gap_penalty - failure_penalty) * 100
        return max(0.0, min(100.0, health_score))