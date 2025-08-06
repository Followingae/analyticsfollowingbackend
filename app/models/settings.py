"""
Settings-related Pydantic models for user profile, security, and preferences
"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, Dict, Any
from datetime import datetime


class ProfileUpdateRequest(BaseModel):
    """Request model for updating user profile information"""
    first_name: Optional[str] = Field(None, max_length=100, description="User's first name")
    last_name: Optional[str] = Field(None, max_length=100, description="User's last name")
    company: Optional[str] = Field(None, max_length=200, description="User's company")
    job_title: Optional[str] = Field(None, max_length=100, description="User's job title")
    phone_number: Optional[str] = Field(None, max_length=20, description="User's phone number")
    bio: Optional[str] = Field(None, max_length=500, description="User's biography/description")
    avatar_config: Optional[Dict[str, Any]] = Field(None, description="BoringAvatars configuration")
    timezone: Optional[str] = Field(None, description="User's timezone")
    language: Optional[str] = Field(None, description="User's preferred language")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if v and not v.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            raise ValueError('Invalid phone number format')
        return v


class ProfileUpdateResponse(BaseModel):
    """Response model for profile updates"""
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    phone_number: Optional[str]
    bio: Optional[str]
    avatar_config: Optional[Dict[str, Any]]
    timezone: str
    language: str
    updated_at: datetime
    message: str = "Profile updated successfully"


class PasswordChangeRequest(BaseModel):
    """Request model for changing user password"""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v


class PasswordChangeResponse(BaseModel):
    """Response model for password changes"""
    message: str = "Password updated successfully"
    timestamp: datetime
    requires_reauth: bool = True  # User should re-authenticate after password change


class TwoFactorToggleRequest(BaseModel):
    """Request model for enabling/disabling 2FA"""
    enable: bool = Field(..., description="Enable or disable 2FA")
    password: str = Field(..., description="Current password for verification")


class TwoFactorToggleResponse(BaseModel):
    """Response model for 2FA toggle"""
    two_factor_enabled: bool
    message: str
    qr_code_url: Optional[str] = None  # Only provided when enabling 2FA
    backup_codes: Optional[list] = None  # Only provided when enabling 2FA


class PrivacySettingsRequest(BaseModel):
    """Request model for privacy settings"""
    profile_visibility: Optional[bool] = Field(None, description="Make profile visible to other users")
    data_analytics_enabled: Optional[bool] = Field(None, description="Allow usage analytics for improvements")


class PrivacySettingsResponse(BaseModel):
    """Response model for privacy settings"""
    profile_visibility: bool
    data_analytics_enabled: bool
    message: str = "Privacy settings updated successfully"


class NotificationPreferencesRequest(BaseModel):
    """Request model for notification preferences"""
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    security_alerts: Optional[bool] = None
    weekly_reports: Optional[bool] = None


class NotificationPreferencesResponse(BaseModel):
    """Response model for notification preferences"""
    email_notifications: bool
    push_notifications: bool
    marketing_emails: bool
    security_alerts: bool
    weekly_reports: bool
    message: str = "Notification preferences updated successfully"


class UserPreferencesRequest(BaseModel):
    """Request model for general app preferences"""
    timezone: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = Field(None, description="UI theme preference")
    dashboard_layout: Optional[str] = Field(None, description="Dashboard layout preference")
    default_analysis_type: Optional[str] = Field(None, description="Default Instagram analysis type")


class UserPreferencesResponse(BaseModel):
    """Response model for user preferences"""
    timezone: str
    language: str
    preferences: Dict[str, Any]
    message: str = "Preferences updated successfully"




class UserSettingsOverview(BaseModel):
    """Complete user settings overview"""
    profile: ProfileUpdateResponse
    security: Dict[str, Any]
    notifications: NotificationPreferencesResponse
    privacy: PrivacySettingsResponse
    preferences: UserPreferencesResponse
    
    class Config:
        schema_extra = {
            "example": {
                "profile": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "company": "Acme Corp",
                    "job_title": "Marketing Manager"
                },
                "security": {
                    "two_factor_enabled": False,
                    "email_verified": True,
                    "phone_verified": False
                },
                "notifications": {
                    "email_notifications": True,
                    "push_notifications": True,
                    "marketing_emails": False
                }
            }
        }