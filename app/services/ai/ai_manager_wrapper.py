"""
AI Manager Wrapper - Provides unified access to AI models
Simple wrapper to maintain compatibility after cleanup
"""
from app.services.ai.ai_manager_singleton import ai_manager

# Re-export for compatibility
__all__ = ['ai_manager']