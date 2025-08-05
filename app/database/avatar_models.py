"""
Database models for user avatar functionality
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.unified_models import Base

class UserAvatar(Base):
    """Model for user uploaded avatars"""
    
    __tablename__ = "user_avatars"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    original_filename = Column(String)
    processed_size = Column(String)  # e.g., "400x400"
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<UserAvatar(id={self.id}, user_id={self.user_id}, file_path={self.file_path}, is_active={self.is_active})>"
    
    @property
    def public_url(self):
        """Generate public URL for the avatar"""
        from app.core.config import settings
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/avatars/{self.file_path}"