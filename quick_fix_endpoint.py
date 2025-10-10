"""
Add a quick fix endpoint to the running server
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user

router = APIRouter()

@router.post("/fix/access-records")
async def fix_access_records_endpoint(
    current_user=Depends(get_current_active_user),
    db=Depends(get_db)
):
    """URGENT: Fix free allowance and create access record for barakatme"""

    results = []

    try:
        # Fix #1: Remove free allowance
        result = await db.execute(text("""
            UPDATE credit_pricing_rules
            SET free_allowance_per_month = 0
            WHERE action_type = 'profile_analysis'
        """))
        await db.commit()
        results.append(f"✅ FREE ALLOWANCE REMOVED: Updated {result.rowcount} pricing rule(s)")

        # Fix #2: Create access record for barakatme
        user_result = await db.execute(text("""
            SELECT id FROM users WHERE email = 'client@analyticsfollowing.com'
        """))
        user_row = user_result.fetchone()

        profile_result = await db.execute(text("""
            SELECT id FROM profiles WHERE username = 'barakatme'
        """))
        profile_row = profile_result.fetchone()

        if user_row and profile_row:
            user_id = user_row[0]
            profile_id = profile_row[0]

            await db.execute(text("""
                INSERT INTO user_profile_access (user_id, profile_id, granted_at, expires_at, created_at)
                VALUES (:user_id, :profile_id, NOW(), NOW() + INTERVAL '30 days', NOW())
                ON CONFLICT (user_id, profile_id) DO UPDATE SET
                    granted_at = NOW(),
                    expires_at = NOW() + INTERVAL '30 days'
            """), {
                'user_id': user_id,
                'profile_id': profile_id
            })
            await db.commit()
            results.append(f"✅ ACCESS RECORD CREATED: {user_id} -> {profile_id}")
        else:
            results.append(f"❌ USER OR PROFILE NOT FOUND")

        return {
            "success": True,
            "message": "Fixes applied successfully",
            "results": results
        }

    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "results": results
        }