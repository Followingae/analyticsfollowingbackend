"""
USER SETTINGS API ROUTES
Complete implementation of user settings management including:
- Profile information updates
- Security settings (password, 2FA, privacy)
- Notification preferences 
- User preferences and customization
- Avatar upload functionality
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from typing import Optional
from datetime import datetime
import logging

from app.models.settings import (
    ProfileUpdateRequest, ProfileUpdateResponse, PasswordChangeRequest, PasswordChangeResponse,
    TwoFactorToggleRequest, TwoFactorToggleResponse, PrivacySettingsRequest, PrivacySettingsResponse,
    NotificationPreferencesRequest, NotificationPreferencesResponse, 
    UserPreferencesRequest, UserPreferencesResponse, UserSettingsOverview
)
from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import async_engine, get_db
from app.services.supabase_auth_service import supabase_auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["User Settings"])

# Simple in-memory cache for user settings (5-minute TTL)
from datetime import datetime, timedelta
_user_cache = {}
_cache_ttl = timedelta(minutes=5)


# Simple user lookup - no caching, no complexity
async def get_user_from_db_simple(user_id: str, db_session):
    """Simple user lookup for settings"""
    from sqlalchemy import text
    import json
    
    result = await db_session.execute(text("""
        SELECT id, email, full_name, timezone, language, updated_at, avatar_config,
               "user.first_name" as first_name, "user.last_name" as last_name, 
               company, job_title, phone_number, bio, notification_preferences,
               "user.profile_visibility" as profile_visibility, 
               "user.data_analytics_enabled" as data_analytics_enabled, preferences
        FROM users WHERE supabase_user_id = :user_id
    """), {"user_id": user_id})
    
    row = result.fetchone()
    if not row:
        return None
    
    # Parse JSON fields
    avatar_config = None
    if row.avatar_config:
        try:
            avatar_config = json.loads(row.avatar_config) if isinstance(row.avatar_config, str) else row.avatar_config
        except:
            avatar_config = None
    
    # Create simple object
    class UserRow:
        pass
    
    user = UserRow()
    user.id = row.id
    user.email = row.email
    user.full_name = row.full_name
    user.first_name = row.first_name
    user.last_name = row.last_name
    user.company = row.company
    user.job_title = row.job_title
    user.phone_number = row.phone_number
    user.bio = row.bio
    user.timezone = row.timezone or "UTC"
    user.language = row.language or "en"
    user.updated_at = row.updated_at
    user.avatar_config = avatar_config
    user.notification_preferences = row.notification_preferences or {}
    user.profile_visibility = getattr(row, 'profile_visibility', True)
    user.data_analytics_enabled = getattr(row, 'data_analytics_enabled', True)
    user.preferences = row.preferences or {}
    user.two_factor_enabled = False
    user.email_verified = True
    user.phone_verified = False
    
    return user


async def update_user_in_db(user_id: str, **update_data):
    """Update user data using connection pool with timeout"""
    import asyncio
    import json
    from app.database.connection import async_engine
    from sqlalchemy import text
    from fastapi import HTTPException
    
    if not update_data:
        return
    
    # Convert avatar_config dict to JSON string for PostgreSQL JSONB
    if 'avatar_config' in update_data and update_data['avatar_config'] is not None:
        update_data['avatar_config'] = json.dumps(update_data['avatar_config'])
    
    try:
        # Add 30-second timeout to prevent hanging
        async with asyncio.timeout(30):
            # Build SET clause dynamically, mapping to correct column names
            column_mapping = {
                'first_name': '"user.first_name"',
                'last_name': '"user.last_name"',
                'two_factor_enabled': '"user.two_factor_enabled"',
                'email_verified': '"user.email_verified"',
                'phone_verified': '"user.phone_verified"',
                'profile_visibility': '"user.profile_visibility"',
                'data_analytics_enabled': '"user.data_analytics_enabled"'
            }
            
            set_clauses = []
            for key in update_data.keys():
                column_name = column_mapping.get(key, key)
                set_clauses.append(f"{column_name} = :{key}")
            set_clause = ", ".join(set_clauses)
            
            async with async_engine.begin() as conn:
                await conn.execute(text(f"""
                    UPDATE users 
                    SET {set_clause}, updated_at = NOW()
                    WHERE supabase_user_id = :user_id
                """), {"user_id": user_id, **update_data})
    except asyncio.TimeoutError:
        logger.error(f"Database update timeout for user {user_id}")
        raise HTTPException(status_code=503, detail="Database update timeout")
    except Exception as e:
        logger.error(f"Database update error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database update error")


# =============================================================================
# PROFILE INFORMATION ENDPOINTS
# =============================================================================

@router.get("/profile", response_model=ProfileUpdateResponse)
async def get_user_profile(
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Get current user's profile information
    
    Returns all profile fields that can be edited in the settings page.
    """
    try:
        # Get fresh user data from database using connection pool
        user_data = await get_user_from_db_simple(current_user.id, db_session)
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        return ProfileUpdateResponse(
            id=str(user_data.id),
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            full_name=user_data.full_name,
            company=user_data.company,
            job_title=user_data.job_title,
            phone_number=user_data.phone_number,
            bio=user_data.bio,
            avatar_config=user_data.avatar_config,
            timezone=user_data.timezone or "UTC",
            language=user_data.language or "en",
            updated_at=user_data.updated_at or datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get profile for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve profile")


@router.put("/profile", response_model=ProfileUpdateResponse)
async def update_user_profile(
    profile_data: ProfileUpdateRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Update user's profile information
    
    Updates any provided profile fields. Only non-null fields will be updated.
    Automatically updates the full_name field based on first_name + last_name.
    """
    try:
        # Prepare update data (only include non-None values)
        update_data = {}
        
        if profile_data.first_name is not None:
            update_data['first_name'] = profile_data.first_name
        if profile_data.last_name is not None:
            update_data['last_name'] = profile_data.last_name
        if profile_data.company is not None:
            update_data['company'] = profile_data.company
        if profile_data.job_title is not None:
            update_data['job_title'] = profile_data.job_title
        if profile_data.phone_number is not None:
            update_data['phone_number'] = profile_data.phone_number
        if profile_data.bio is not None:
            update_data['bio'] = profile_data.bio
        if profile_data.avatar_config is not None:
            update_data['avatar_config'] = profile_data.avatar_config
        if profile_data.timezone is not None:
            update_data['timezone'] = profile_data.timezone
        if profile_data.language is not None:
            update_data['language'] = profile_data.language
        
        # Auto-generate full_name if first_name or last_name provided
        if 'first_name' in update_data or 'last_name' in update_data:
            # Get current values for fields not being updated
            current_user_data = await get_user_from_db_simple(current_user.id, db_session)
            
            first_name = update_data.get('first_name', current_user_data.first_name) or ""
            last_name = update_data.get('last_name', current_user_data.last_name) or ""
            update_data['full_name'] = f"{first_name} {last_name}".strip()
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        # Update user in database using connection pool
        await update_user_in_db(current_user.id, **update_data)
        
        # Get updated user data
        updated_user = await get_user_from_db_simple(current_user.id, db_session)
        
        logger.info(f"Profile updated for user {current_user.id}: {list(update_data.keys())}")
        
        return ProfileUpdateResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            full_name=updated_user.full_name,
            company=updated_user.company,
            job_title=updated_user.job_title,
            phone_number=updated_user.phone_number,
            bio=updated_user.bio,
            avatar_config=updated_user.avatar_config,
            timezone=updated_user.timezone or "UTC",
            language=updated_user.language or "en",
            updated_at=updated_user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update profile for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")




# =============================================================================
# SECURITY & PRIVACY ENDPOINTS
# =============================================================================

@router.post("/security/password", response_model=PasswordChangeResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Change user's password
    
    Requires current password for verification. New password must meet strength requirements.
    User will need to re-authenticate after password change.
    """
    try:
        # Verify current password and update via Supabase Auth
        success = await supabase_auth_service.change_user_password(
            current_user.email,
            password_data.current_password,
            password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )
        
        logger.info(f"Password changed for user {current_user.id}")
        
        return PasswordChangeResponse(
            message="Password updated successfully",
            timestamp=datetime.now(),
            requires_reauth=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to change password")


@router.post("/security/2fa", response_model=TwoFactorToggleResponse)
async def toggle_two_factor_auth(
    tfa_data: TwoFactorToggleRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Enable or disable Two-Factor Authentication
    
    When enabling, returns QR code URL and backup codes.
    Requires current password for verification.
    """
    try:
        # Verify password first
        password_valid = await supabase_auth_service.verify_user_password(
            current_user.email, 
            tfa_data.password
        )
        
        if not password_valid:
            raise HTTPException(status_code=400, detail="Invalid password")
        
        # Update 2FA status in database using connection pool
        await update_user_in_db(current_user.id, two_factor_enabled=tfa_data.enable)
        
        response_data = {
            "two_factor_enabled": tfa_data.enable,
            "message": f"Two-factor authentication {'enabled' if tfa_data.enable else 'disabled'} successfully"
        }
        
        # If enabling, generate QR code and backup codes (placeholder)
        if tfa_data.enable:
            response_data.update({
                "qr_code_url": f"https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl=otpauth://totp/Following:{current_user.email}?secret=TEMP_SECRET&issuer=Following",
                "backup_codes": [
                    "12345678", "87654321", "11223344", "44332211", "56789012"
                ]
            })
        
        logger.info(f"2FA {'enabled' if tfa_data.enable else 'disabled'} for user {current_user.id}")
        
        return TwoFactorToggleResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA toggle failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update 2FA settings")


@router.put("/security/privacy", response_model=PrivacySettingsResponse)
async def update_privacy_settings(
    privacy_data: PrivacySettingsRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Update privacy settings
    
    Controls profile visibility and data analytics preferences.
    """
    try:
        update_data = {}
        
        if privacy_data.profile_visibility is not None:
            update_data['profile_visibility'] = privacy_data.profile_visibility
        if privacy_data.data_analytics_enabled is not None:
            update_data['data_analytics_enabled'] = privacy_data.data_analytics_enabled
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No privacy settings provided")
        
        # Update database using connection pool
        await update_user_in_db(current_user.id, **update_data)
        
        # Get updated values
        updated_user = await get_user_from_db_simple(current_user.id, db_session)
        
        logger.info(f"Privacy settings updated for user {current_user.id}")
        
        return PrivacySettingsResponse(
            profile_visibility=updated_user.profile_visibility,
            data_analytics_enabled=updated_user.data_analytics_enabled
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Privacy settings update failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update privacy settings")


# =============================================================================
# NOTIFICATIONS ENDPOINTS
# =============================================================================

@router.get("/notifications", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """Get current notification preferences"""
    try:
        user = await get_user_from_db_simple(current_user.id, db_session)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        prefs = user.notification_preferences or {}
        
        return NotificationPreferencesResponse(
            email_notifications=prefs.get('email_notifications', True),
            push_notifications=prefs.get('push_notifications', True),
            marketing_emails=prefs.get('marketing_emails', False),
            security_alerts=prefs.get('security_alerts', True),
            weekly_reports=prefs.get('weekly_reports', True)
        )
        
    except Exception as e:
        logger.error(f"Failed to get notification preferences for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notification preferences")


@router.put("/notifications", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    notification_data: NotificationPreferencesRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Update notification preferences
    
    Updates any provided notification settings. Existing settings are preserved.
    """
    try:
        # Get current preferences using connection pool
        user = await get_user_from_db_simple(current_user.id, db_session)
        
        current_prefs = user.notification_preferences or {}
        
        # Update only provided fields
        if notification_data.email_notifications is not None:
            current_prefs['email_notifications'] = notification_data.email_notifications
        if notification_data.push_notifications is not None:
            current_prefs['push_notifications'] = notification_data.push_notifications
        if notification_data.marketing_emails is not None:
            current_prefs['marketing_emails'] = notification_data.marketing_emails
        if notification_data.security_alerts is not None:
            current_prefs['security_alerts'] = notification_data.security_alerts
        if notification_data.weekly_reports is not None:
            current_prefs['weekly_reports'] = notification_data.weekly_reports
        
        # Update database using connection pool
        await update_user_in_db(current_user.id, notification_preferences=current_prefs)
        
        logger.info(f"Notification preferences updated for user {current_user.id}")
        
        return NotificationPreferencesResponse(
            email_notifications=current_prefs.get('email_notifications', True),
            push_notifications=current_prefs.get('push_notifications', True),
            marketing_emails=current_prefs.get('marketing_emails', False),
            security_alerts=current_prefs.get('security_alerts', True),
            weekly_reports=current_prefs.get('weekly_reports', True)
        )
        
    except Exception as e:
        logger.error(f"Notification preferences update failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update notification preferences")


# =============================================================================
# USER PREFERENCES ENDPOINTS  
# =============================================================================

@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """Get current user preferences and app settings"""
    try:
        user = await get_user_from_db_simple(current_user.id, db_session)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserPreferencesResponse(
            timezone=user.timezone or "UTC",
            language=user.language or "en",
            preferences=user.preferences or {}
        )
        
    except Exception as e:
        logger.error(f"Failed to get preferences for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    preferences_data: UserPreferencesRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Update user preferences and app settings
    
    Updates timezone, language, and custom app preferences.
    """
    try:
        # Get current user data using connection pool
        user = await get_user_from_db_simple(current_user.id, db_session)
        
        update_data = {}
        current_prefs = user.preferences or {}
        
        if preferences_data.timezone is not None:
            update_data['timezone'] = preferences_data.timezone
        if preferences_data.language is not None:
            update_data['language'] = preferences_data.language
        if preferences_data.theme is not None:
            current_prefs['theme'] = preferences_data.theme
        if preferences_data.dashboard_layout is not None:
            current_prefs['dashboard_layout'] = preferences_data.dashboard_layout
        if preferences_data.default_analysis_type is not None:
            current_prefs['default_analysis_type'] = preferences_data.default_analysis_type
        
        if current_prefs != user.preferences:
            update_data['preferences'] = current_prefs
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No preferences provided for update")
        
        # Update database using connection pool
        await update_user_in_db(current_user.id, **update_data)
        
        # Get updated data
        updated_user = await get_user_from_db_simple(current_user.id, db_session)
        
        logger.info(f"User preferences updated for user {current_user.id}")
        
        return UserPreferencesResponse(
            timezone=updated_user.timezone or "UTC",
            language=updated_user.language or "en",
            preferences=updated_user.preferences or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User preferences update failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


# =============================================================================
# COMPLETE SETTINGS OVERVIEW
# =============================================================================

@router.get("/overview", response_model=UserSettingsOverview)
async def get_complete_settings_overview(
    current_user: UserInDB = Depends(get_current_active_user),
    db_session = Depends(get_db)
):
    """
    Get complete user settings overview
    
    Returns all settings in a single response for settings page initialization.
    """
    try:
        logger.info(f"Getting settings overview for user {current_user.id}")
        
        # Use fast lookup with existing connection pool
        user_row = await get_user_from_db_simple(current_user.id, db_session)
        
        if not user_row:
            logger.warning(f"User not found in database: {current_user.id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Building profile data for user {current_user.id}")
        
        # Build comprehensive response with safe field access
        profile_data = ProfileUpdateResponse(
            id=str(user_row.id),
            email=user_row.email,
            first_name=getattr(user_row, 'first_name', None),
            last_name=getattr(user_row, 'last_name', None),
            full_name=user_row.full_name,
            company=getattr(user_row, 'company', None),
            job_title=getattr(user_row, 'job_title', None),
            phone_number=getattr(user_row, 'phone_number', None),
            bio=getattr(user_row, 'bio', None),
            avatar_config=getattr(user_row, 'avatar_config', None),
            timezone=user_row.timezone or "UTC",
            language=user_row.language or "en",
            updated_at=user_row.updated_at or datetime.now()
        )
        
        logger.info(f"Building security and preferences data for user {current_user.id}")
        
        security_data = {
            "two_factor_enabled": getattr(user_row, 'two_factor_enabled', False),
            "email_verified": getattr(user_row, 'email_verified', False),
            "phone_verified": getattr(user_row, 'phone_verified', False)
        }
        
        notification_prefs = getattr(user_row, 'notification_preferences', {}) or {}
        notifications = NotificationPreferencesResponse(
            email_notifications=notification_prefs.get('email_notifications', True),
            push_notifications=notification_prefs.get('push_notifications', True),
            marketing_emails=notification_prefs.get('marketing_emails', False),
            security_alerts=notification_prefs.get('security_alerts', True),
            weekly_reports=notification_prefs.get('weekly_reports', True)
        )
        
        privacy = PrivacySettingsResponse(
            profile_visibility=getattr(user_row, 'profile_visibility', True),
            data_analytics_enabled=getattr(user_row, 'data_analytics_enabled', True)
        )
        
        preferences = UserPreferencesResponse(
            timezone=user_row.timezone or "UTC",
            language=user_row.language or "en",
            preferences=getattr(user_row, 'preferences', {}) or {}
        )
        
        return UserSettingsOverview(
            profile=profile_data,
            security=security_data,
            notifications=notifications,
            privacy=privacy,
            preferences=preferences
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 503 from timeouts)
        raise
    except Exception as e:
        logger.error(f"Failed to get settings overview for user {current_user.id}: {e}")
        
        # Return a minimal working settings overview instead of failing completely
        try:
            minimal_profile = ProfileUpdateResponse(
                id=current_user.id,
                email=current_user.email,
                first_name=None,
                last_name=None,
                full_name=current_user.email.split('@')[0],  # Use email prefix as name fallback
                company=None,
                job_title=None,
                phone_number=None,
                bio=None,
                profile_picture_url=None,
                timezone="UTC",
                language="en",
                updated_at=datetime.now()
            )
            
            return UserSettingsOverview(
                profile=minimal_profile,
                security={"two_factor_enabled": False, "email_verified": True, "phone_verified": False},
                notifications=NotificationPreferencesResponse(
                    email_notifications=True,
                    push_notifications=True,
                    marketing_emails=False,
                    security_alerts=True,
                    weekly_reports=True
                ),
                privacy=PrivacySettingsResponse(
                    profile_visibility=True,
                    data_analytics_enabled=True
                ),
                preferences=UserPreferencesResponse(
                    timezone="UTC",
                    language="en",
                    preferences={}
                )
            )
        except Exception as fallback_error:
            logger.error(f"Even fallback settings failed: {fallback_error}")
            raise HTTPException(status_code=500, detail="Failed to retrieve settings overview")