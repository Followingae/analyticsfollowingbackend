"""
User Notifications Service
General-purpose notification system.
Types: share_received, share_revoked, share_extended, proposal_received,
proposal_updated, analytics_completed, credit_purchase, low_balance,
team_invite, team_update, system.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing user notifications."""

    # =========================================================================
    # CREATE NOTIFICATIONS
    # =========================================================================

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: Optional[UUID],
        user_email: str,
        notification_type: str,
        title: str,
        message: Optional[str] = None,
        action_url: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a single notification."""
        import json

        result = await db.execute(
            text("""
                INSERT INTO user_notifications
                    (user_id, user_email, notification_type, title, message,
                     action_url, reference_type, reference_id, metadata)
                VALUES
                    (CAST(:user_id AS uuid), :user_email, :notification_type, :title, :message,
                     :action_url, :reference_type, CAST(:reference_id AS uuid),
                     CAST(:metadata AS jsonb))
                RETURNING *
            """),
            {
                "user_id": str(user_id) if user_id else None,
                "user_email": user_email,
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "action_url": action_url,
                "reference_type": reference_type,
                "reference_id": str(reference_id) if reference_id else None,
                "metadata": json.dumps(metadata) if metadata else "{}",
            },
        )
        await db.commit()
        row = result.mappings().fetchone()
        return dict(row) if row else {}

    @staticmethod
    async def create_bulk(
        db: AsyncSession,
        notifications: List[Dict[str, Any]],
    ) -> int:
        """Create multiple notifications at once. Returns count created."""
        import json

        count = 0
        for n in notifications:
            await db.execute(
                text("""
                    INSERT INTO user_notifications
                        (user_id, user_email, notification_type, title, message,
                         action_url, reference_type, reference_id, metadata)
                    VALUES
                        (CAST(:user_id AS uuid), :user_email, :notification_type, :title, :message,
                         :action_url, :reference_type, CAST(:reference_id AS uuid),
                         CAST(:metadata AS jsonb))
                """),
                {
                    "user_id": str(n["user_id"]) if n.get("user_id") else None,
                    "user_email": n.get("user_email"),
                    "notification_type": n["notification_type"],
                    "title": n["title"],
                    "message": n.get("message"),
                    "action_url": n.get("action_url"),
                    "reference_type": n.get("reference_type"),
                    "reference_id": str(n["reference_id"]) if n.get("reference_id") else None,
                    "metadata": json.dumps(n.get("metadata", {})),
                },
            )
            count += 1
        await db.commit()
        return count

    # =========================================================================
    # READ / LIST
    # =========================================================================

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        page: int = 1,
        page_size: int = 20,
        notification_type: Optional[str] = None,
        unread_only: bool = False,
    ) -> Dict[str, Any]:
        """List notifications for a user, newest first."""
        conditions = ["(user_id = CAST(:uid AS uuid) OR user_email = :email)"]
        params: Dict[str, Any] = {"uid": str(user_id), "email": user_email}

        if notification_type:
            conditions.append("notification_type = :ntype")
            params["ntype"] = notification_type

        if unread_only:
            conditions.append("is_read = FALSE")

        where = " WHERE " + " AND ".join(conditions)

        # Count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM user_notifications{where}"),
            params,
        )
        total_count = count_result.scalar() or 0

        # Data
        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        data_result = await db.execute(
            text(
                f"SELECT * FROM user_notifications{where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        rows = [dict(r) for r in data_result.mappings().fetchall()]

        return {
            "notifications": rows,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size if page_size else 1,
        }

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
    ) -> Dict[str, Any]:
        """Get unread notification count, broken down by type."""
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE is_read = FALSE) AS total_unread,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type IN ('share_received','share_revoked','share_extended')) AS unread_shares,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type IN ('proposal_received','proposal_updated')) AS unread_proposals,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type = 'analytics_completed') AS unread_analytics,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type IN ('credit_purchase','low_balance')) AS unread_billing,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type IN ('team_invite','team_update')) AS unread_team,
                    COUNT(*) FILTER (WHERE is_read = FALSE AND notification_type = 'system') AS unread_system
                FROM user_notifications
                WHERE user_id = CAST(:uid AS uuid) OR user_email = :email
            """),
            {"uid": str(user_id), "email": user_email},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else {
            "total_unread": 0, "unread_shares": 0, "unread_proposals": 0,
            "unread_analytics": 0, "unread_billing": 0, "unread_team": 0, "unread_system": 0,
        }

    # =========================================================================
    # MARK READ
    # =========================================================================

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        notification_id: UUID,
        user_id: UUID,
        user_email: str,
    ) -> bool:
        """Mark a single notification as read."""
        result = await db.execute(
            text("""
                UPDATE user_notifications
                SET is_read = TRUE, read_at = NOW()
                WHERE id = CAST(:nid AS uuid)
                  AND (user_id = CAST(:uid AS uuid) OR user_email = :email)
                  AND is_read = FALSE
            """),
            {"nid": str(notification_id), "uid": str(user_id), "email": user_email},
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def mark_all_read(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        notification_type: Optional[str] = None,
    ) -> int:
        """Mark all (or filtered) notifications as read. Returns count updated."""
        conditions = [
            "(user_id = CAST(:uid AS uuid) OR user_email = :email)",
            "is_read = FALSE",
        ]
        params: Dict[str, Any] = {"uid": str(user_id), "email": user_email}

        if notification_type:
            conditions.append("notification_type = :ntype")
            params["ntype"] = notification_type

        where = " AND ".join(conditions)
        result = await db.execute(
            text(f"UPDATE user_notifications SET is_read = TRUE, read_at = NOW() WHERE {where}"),
            params,
        )
        await db.commit()
        return result.rowcount

    # =========================================================================
    # NOTIFICATION TRIGGERS (called from other services)
    # =========================================================================

    @staticmethod
    async def notify_share_created(
        db: AsyncSession,
        share_name: str,
        share_id: UUID,
        user_emails: List[str],
        influencer_count: int,
    ) -> int:
        """Notify users that a new share list has been shared with them."""
        notifications = []
        for email in user_emails:
            # Try to resolve user_id from email
            uid_result = await db.execute(
                text("SELECT id FROM auth.users WHERE email = :email"),
                {"email": email},
            )
            uid_row = uid_result.fetchone()
            user_id = uid_row[0] if uid_row else None

            notifications.append({
                "user_id": user_id,
                "user_email": email,
                "notification_type": "share_received",
                "title": f"New influencer list shared: {share_name}",
                "message": f"You have been given access to a list of {influencer_count} influencer{'s' if influencer_count != 1 else ''}.",
                "action_url": "/lists/shared",
                "reference_type": "share",
                "reference_id": share_id,
                "metadata": {
                    "share_name": share_name,
                    "influencer_count": influencer_count,
                },
            })

        if notifications:
            return await NotificationService.create_bulk(db, notifications)
        return 0

    @staticmethod
    async def notify_proposal_received(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        proposal_id: UUID,
        proposal_title: str,
        campaign_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Notify user that a new proposal has been sent to them."""
        return await NotificationService.create(
            db,
            user_id=user_id,
            user_email=user_email,
            notification_type="proposal_received",
            title=f"New proposal: {proposal_title}",
            message=f"You have received a new campaign proposal{f' for {campaign_name}' if campaign_name else ''}. Review and respond.",
            action_url=f"/proposals/{proposal_id}",
            reference_type="proposal",
            reference_id=proposal_id,
            metadata={
                "proposal_title": proposal_title,
                "campaign_name": campaign_name,
            },
        )

    @staticmethod
    async def notify_analytics_completed(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        username: str,
    ) -> Dict[str, Any]:
        """Notify user that creator analytics have completed."""
        return await NotificationService.create(
            db,
            user_id=user_id,
            user_email=user_email,
            notification_type="analytics_completed",
            title=f"Analytics ready for @{username}",
            message=f"Creator analytics for @{username} have been generated and are ready to view.",
            action_url=f"/search/creator/{username}",
            reference_type="profile",
            metadata={
                "username": username,
            },
        )

    # =========================================================================
    # SHARE LIFECYCLE TRIGGERS
    # =========================================================================

    @staticmethod
    async def _resolve_share_users(
        db: AsyncSession, share_id: UUID
    ) -> List[Dict[str, Any]]:
        """Helper: get user_id + email for all users on a share."""
        result = await db.execute(
            text("""
                SELECT su.user_email,
                       au.id AS user_id
                FROM influencer_share_users su
                LEFT JOIN auth.users au ON au.email = su.user_email
                WHERE su.share_id = CAST(:sid AS uuid)
            """),
            {"sid": str(share_id)},
        )
        return [dict(r) for r in result.mappings().fetchall()]

    @staticmethod
    async def notify_share_revoked(
        db: AsyncSession,
        share_id: UUID,
        share_name: str,
    ) -> int:
        """Notify users that their share access has been revoked."""
        users = await NotificationService._resolve_share_users(db, share_id)
        notifications = [
            {
                "user_id": u["user_id"],
                "user_email": u["user_email"],
                "notification_type": "share_revoked",
                "title": f"List access revoked: {share_name}",
                "message": f"Your access to the shared influencer list \"{share_name}\" has been revoked.",
                "action_url": "/lists/shared",
                "reference_type": "share",
                "reference_id": share_id,
                "metadata": {"share_name": share_name},
            }
            for u in users
        ]
        return await NotificationService.create_bulk(db, notifications) if notifications else 0

    @staticmethod
    async def notify_share_extended(
        db: AsyncSession,
        share_id: UUID,
        share_name: str,
        new_expires_at: str,
    ) -> int:
        """Notify users that their share access has been extended."""
        users = await NotificationService._resolve_share_users(db, share_id)
        notifications = [
            {
                "user_id": u["user_id"],
                "user_email": u["user_email"],
                "notification_type": "share_extended",
                "title": f"List access extended: {share_name}",
                "message": f"Your access to \"{share_name}\" has been extended to {new_expires_at}.",
                "action_url": "/lists/shared",
                "reference_type": "share",
                "reference_id": share_id,
                "metadata": {"share_name": share_name, "new_expires_at": new_expires_at},
            }
            for u in users
        ]
        return await NotificationService.create_bulk(db, notifications) if notifications else 0

    # =========================================================================
    # PROPOSAL LIFECYCLE TRIGGERS
    # =========================================================================

    @staticmethod
    async def notify_proposal_approved(
        db: AsyncSession,
        proposal_id: UUID,
        proposal_title: str,
        campaign_name: str,
        admin_id: UUID,
        selected_count: int,
    ) -> Dict[str, Any]:
        """Notify the admin who created the proposal that user approved it."""
        # Resolve admin email
        admin_result = await db.execute(
            text("SELECT email FROM auth.users WHERE id = CAST(:uid AS uuid)"),
            {"uid": str(admin_id)},
        )
        admin_row = admin_result.fetchone()
        if not admin_row:
            return {}

        return await NotificationService.create(
            db,
            user_id=admin_id,
            user_email=admin_row[0],
            notification_type="proposal_updated",
            title=f"Proposal approved: {proposal_title}",
            message=f"The user approved your proposal for {campaign_name} with {selected_count} influencer{'s' if selected_count != 1 else ''} selected.",
            action_url=f"/admin/proposals/{proposal_id}",
            reference_type="proposal",
            reference_id=proposal_id,
            metadata={
                "proposal_title": proposal_title,
                "campaign_name": campaign_name,
                "action": "approved",
                "selected_count": selected_count,
            },
        )

    @staticmethod
    async def notify_proposal_rejected(
        db: AsyncSession,
        proposal_id: UUID,
        proposal_title: str,
        campaign_name: str,
        admin_id: UUID,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Notify the admin who created the proposal that user rejected it."""
        admin_result = await db.execute(
            text("SELECT email FROM auth.users WHERE id = CAST(:uid AS uuid)"),
            {"uid": str(admin_id)},
        )
        admin_row = admin_result.fetchone()
        if not admin_row:
            return {}

        msg = f"The user rejected your proposal for {campaign_name}."
        if reason:
            msg += f" Reason: {reason}"

        return await NotificationService.create(
            db,
            user_id=admin_id,
            user_email=admin_row[0],
            notification_type="proposal_updated",
            title=f"Proposal rejected: {proposal_title}",
            message=msg,
            action_url=f"/admin/proposals/{proposal_id}",
            reference_type="proposal",
            reference_id=proposal_id,
            metadata={
                "proposal_title": proposal_title,
                "campaign_name": campaign_name,
                "action": "rejected",
                "reason": reason,
            },
        )

    # =========================================================================
    # CREDIT & BILLING TRIGGERS
    # =========================================================================

    @staticmethod
    async def notify_credit_purchase(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        credits_added: int,
        plan_name: str,
    ) -> Dict[str, Any]:
        """Notify user that credits have been added after payment."""
        return await NotificationService.create(
            db,
            user_id=user_id,
            user_email=user_email,
            notification_type="credit_purchase",
            title=f"Credits added: {credits_added:,} credits",
            message=f"Your {plan_name} subscription is active. {credits_added:,} credits have been added to your wallet.",
            action_url="/settings/billing",
            reference_type="billing",
            metadata={
                "credits_added": credits_added,
                "plan_name": plan_name,
            },
        )

    @staticmethod
    async def notify_low_balance(
        db: AsyncSession,
        user_id: UUID,
        user_email: str,
        current_balance: int,
    ) -> Dict[str, Any]:
        """Warn user that their credit balance is low."""
        return await NotificationService.create(
            db,
            user_id=user_id,
            user_email=user_email,
            notification_type="low_balance",
            title=f"Low credit balance: {current_balance} credits remaining",
            message=f"Your credit balance is running low ({current_balance} credits). Top up to continue using analytics features.",
            action_url="/settings/billing",
            reference_type="billing",
            metadata={
                "current_balance": current_balance,
            },
        )

    # =========================================================================
    # TEAM TRIGGERS
    # =========================================================================

    @staticmethod
    async def notify_team_invite(
        db: AsyncSession,
        invitee_email: str,
        team_name: str,
        inviter_name: str,
        role: str,
    ) -> Dict[str, Any]:
        """Notify user that they've been invited to a team."""
        # Try to resolve user_id
        uid_result = await db.execute(
            text("SELECT id FROM auth.users WHERE email = :email"),
            {"email": invitee_email},
        )
        uid_row = uid_result.fetchone()

        return await NotificationService.create(
            db,
            user_id=uid_row[0] if uid_row else None,
            user_email=invitee_email,
            notification_type="team_invite",
            title=f"Team invitation: {team_name}",
            message=f"{inviter_name} invited you to join \"{team_name}\" as {role}.",
            action_url="/settings/team",
            reference_type="team",
            metadata={
                "team_name": team_name,
                "inviter_name": inviter_name,
                "role": role,
            },
        )

    @staticmethod
    async def notify_team_invite_accepted(
        db: AsyncSession,
        owner_id: UUID,
        owner_email: str,
        team_name: str,
        accepted_by_email: str,
    ) -> Dict[str, Any]:
        """Notify team owner that someone accepted their invite."""
        return await NotificationService.create(
            db,
            user_id=owner_id,
            user_email=owner_email,
            notification_type="team_update",
            title=f"Invitation accepted: {team_name}",
            message=f"{accepted_by_email} has joined your team \"{team_name}\".",
            action_url="/settings/team",
            reference_type="team",
            metadata={
                "team_name": team_name,
                "accepted_by": accepted_by_email,
            },
        )
