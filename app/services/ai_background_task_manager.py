"""
AI Background Task Manager - Handles AI analysis task scheduling and monitoring
Integrates with Celery workers for scalable background processing (with development fallback)
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

# Optional Celery imports for development
try:
    from celery.result import AsyncResult
    from app.workers.ai_background_worker import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    AsyncResult = None
    celery_app = None

logger = logging.getLogger(__name__)

class AIBackgroundTaskManager:
    """
    Manages AI analysis background tasks with monitoring and status tracking
    """
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        
    def schedule_profile_analysis(self, profile_id: str, profile_username: str) -> Dict[str, Any]:
        """
        Schedule AI analysis for all posts of a profile
        
        Args:
            profile_id: UUID of the profile
            profile_username: Username for logging/tracking
            
        Returns:
            Task information including task_id
        """
        # Development fallback when Celery is not available
        if not CELERY_AVAILABLE:
            logger.error("Celery not available - AI background processing disabled")
            return {
                "success": False,
                "error": "Background processing not available",
                "message": f"AI analysis requires Celery worker. Use direct analysis endpoint: POST /api/v1/ai/analyze/direct/{profile_username}",
                "recommendation": "Use direct AI analysis for immediate results"
            }
            
        try:
            # Check if analysis is already running for this profile
            for task_id, task_info in self.active_tasks.items():
                if (task_info.get('profile_id') == profile_id and 
                    task_info.get('status') in ['PENDING', 'STARTED']):
                    logger.info(f"Analysis already running for profile {profile_username} (task: {task_id})")
                    return {
                        "success": True,
                        "task_id": task_id,
                        "status": "already_running",
                        "message": f"Analysis already in progress for {profile_username}"
                    }
            
            # Schedule new background task
            task_result = celery_app.send_task(
                'ai_worker.analyze_profile_posts',
                args=[profile_id, profile_username],
                task_id=str(uuid.uuid4())  # Generate unique task ID
            )
            
            task_info = {
                "task_id": task_result.id,
                "profile_id": profile_id,
                "profile_username": profile_username,
                "status": "PENDING",
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None
            }
            
            self.active_tasks[task_result.id] = task_info
            
            logger.info(f"[SUCCESS] Scheduled AI analysis task {task_result.id} for profile {profile_username}")
            
            return {
                "success": True,
                "task_id": task_result.id,
                "status": "scheduled",
                "message": f"AI analysis scheduled for {profile_username}",
                "estimated_duration": "2-5 minutes"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to schedule AI analysis for {profile_username}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to schedule AI analysis for {profile_username}"
            }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current status of a background task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information
        """
        # Development fallback when Celery is not available
        if not CELERY_AVAILABLE:
            return {
                "success": False,
                "task_id": task_id,
                "status": "UNAVAILABLE",
                "error": "Celery not available",
                "message": "Background processing not available. Use direct AI analysis instead.",
                "recommendation": f"Use POST /api/v1/ai/analyze/direct/{{username}} for immediate AI analysis"
            }
                
        try:
            # Get task result from Celery
            task_result = AsyncResult(task_id, app=celery_app)
            
            # Update our local tracking
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                task_info["status"] = task_result.status
                
                if task_result.status == "STARTED" and not task_info.get("started_at"):
                    task_info["started_at"] = datetime.now(timezone.utc).isoformat()
                
                if task_result.status in ["SUCCESS", "FAILURE"]:
                    task_info["completed_at"] = datetime.now(timezone.utc).isoformat()
                    
                    if task_result.status == "SUCCESS":
                        task_info["result"] = task_result.result
                    else:
                        task_info["error"] = str(task_result.info)
            else:
                # Task not in our tracking - create minimal info
                task_info = {
                    "task_id": task_id,
                    "status": task_result.status,
                    "profile_id": "unknown",
                    "profile_username": "unknown"
                }
            
            # Prepare response based on status
            response = {
                "task_id": task_id,
                "status": task_result.status,
                "profile_username": task_info.get("profile_username", "unknown"),
                "scheduled_at": task_info.get("scheduled_at"),
                "started_at": task_info.get("started_at"),
                "completed_at": task_info.get("completed_at")
            }
            
            # Add status-specific information
            if task_result.status == "PENDING":
                response["message"] = "Task is queued and waiting to start"
                response["estimated_remaining"] = "2-5 minutes"
                
            elif task_result.status == "STARTED":
                response["message"] = "AI analysis is currently running"
                response["estimated_remaining"] = "1-3 minutes"
                
            elif task_result.status == "SUCCESS":
                result = task_result.result or {}
                response["message"] = "AI analysis completed successfully"
                response["posts_analyzed"] = result.get("posts_analyzed", 0)
                response["profile_insights_updated"] = result.get("profile_insights", False)
                response["success_rate"] = result.get("batch_success_rate", 0)
                
                # Clean up completed task from active tracking
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                    
            elif task_result.status == "FAILURE":
                response["message"] = "AI analysis failed"
                response["error"] = str(task_result.info)
                
                # Clean up failed task from active tracking
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                    
            elif task_result.status == "RETRY":
                response["message"] = "Task failed and is being retried"
                response["retry_count"] = getattr(task_result.info, 'retries', 0)
                
            else:
                response["message"] = f"Task status: {task_result.status}"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "UNKNOWN",
                "error": str(e),
                "message": "Failed to retrieve task status"
            }
    
    def get_profile_analysis_status(self, profile_id: str) -> Dict[str, Any]:
        """
        Get AI analysis status for a specific profile
        
        Args:
            profile_id: UUID of the profile
            
        Returns:
            Analysis status information
        """
        try:
            # Check if there's an active task for this profile
            active_task = None
            for task_id, task_info in self.active_tasks.items():
                if (task_info.get('profile_id') == profile_id and 
                    task_info.get('status') in ['PENDING', 'STARTED']):
                    active_task = self.get_task_status(task_id)
                    break
            
            if active_task:
                return {
                    "profile_id": profile_id,
                    "has_active_analysis": True,
                    "task_status": active_task,
                    "message": "AI analysis is currently running or queued"
                }
            else:
                return {
                    "profile_id": profile_id,
                    "has_active_analysis": False,
                    "message": "No active AI analysis for this profile"
                }
                
        except Exception as e:
            logger.error(f"Failed to get profile analysis status for {profile_id}: {e}")
            return {
                "profile_id": profile_id,
                "has_active_analysis": False,
                "error": str(e),
                "message": "Failed to check analysis status"
            }
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running background task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Cancellation status
        """
        try:
            celery_app.control.revoke(task_id, terminate=True)
            
            # Clean up from tracking
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            logger.info(f"Cancelled task {task_id}")
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "Task cancelled successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "message": "Failed to cancel task"
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get background processing system statistics"""
        # Development fallback when Celery is not available
        if not CELERY_AVAILABLE:
            return {
                "active_workers": 0,
                "active_tasks_count": 0,
                "task_status_breakdown": {},
                "celery_broker": "Not available (development mode)",
                "system_healthy": False,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "development_mode": True
            }
            
        try:
            # Get Celery worker stats
            active_workers = celery_app.control.inspect().active()
            registered_tasks = celery_app.control.inspect().registered()
            
            # Count active tasks by status
            status_counts = {}
            for task_info in self.active_tasks.values():
                status = task_info.get('status', 'UNKNOWN')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "active_workers": len(active_workers) if active_workers else 0,
                "active_tasks_count": len(self.active_tasks),
                "task_status_breakdown": status_counts,
                "celery_broker": "redis://localhost:6379/0",
                "system_healthy": len(active_workers) > 0 if active_workers else False,
                "last_check": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {
                "error": str(e),
                "system_healthy": False,
                "last_check": datetime.now(timezone.utc).isoformat()
            }
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed task records"""
        try:
            current_time = datetime.now(timezone.utc)
            tasks_to_remove = []
            
            for task_id, task_info in self.active_tasks.items():
                if task_info.get('completed_at'):
                    completed_at = datetime.fromisoformat(task_info['completed_at'].replace('Z', '+00:00'))
                    age_hours = (current_time - completed_at).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.active_tasks[task_id]
            
            if tasks_to_remove:
                logger.info(f"Cleaned up {len(tasks_to_remove)} old task records")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")

# Global instance
ai_background_task_manager = AIBackgroundTaskManager()