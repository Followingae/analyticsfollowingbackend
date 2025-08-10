"""
AI Monitoring and Health Check Service - Mission Critical for Platform Reliability
Monitors AI analysis health, detects issues, and sends alerts
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, or_, desc
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.database.unified_models import (
    AIAnalysisJob, AIAnalysisJobLog, Profile, Post, 
    User, UserProfileAccess
)
from app.services.ai_data_consistency_service import ai_data_consistency_service

logger = logging.getLogger(__name__)

class AIMonitoringService:
    """
    Mission Critical: Monitors AI analysis system health and sends alerts
    
    Key Functions:
    - Monitor job success rates and performance
    - Detect veraciocca-type bugs in real-time
    - Alert on system degradation 
    - Generate health reports
    - Track data consistency trends
    - Monitor background task health
    """
    
    def __init__(self):
        self.alert_thresholds = {
            'job_failure_rate': 0.2,  # Alert if >20% jobs fail
            'hung_job_timeout': 600,  # Alert if jobs hang >10 minutes
            'partial_data_threshold': 5,  # Alert if >5 profiles have partial data
            'processing_time_threshold': 300,  # Alert if jobs take >5 minutes
            'circuit_breaker_threshold': 3,  # Alert if circuit breakers trigger
        }
        
        self.health_metrics = {
            'last_health_check': None,
            'system_status': 'unknown',
            'alerts_sent_today': 0,
            'consecutive_failures': 0
        }
    
    async def run_comprehensive_health_check(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Run comprehensive health check of AI analysis system
        CRITICAL: Detects all types of issues before they affect users
        """
        
        logger.info("Starting comprehensive AI system health check")
        
        health_report = {
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "alerts": [],
            "metrics": {},
            "recommendations": [],
            "system_performance": {}
        }
        
        try:
            # 1. Check job performance metrics
            job_metrics = await self._check_job_performance(db)
            health_report["metrics"]["jobs"] = job_metrics
            
            # 2. Check for hung jobs
            hung_jobs = await self._check_hung_jobs(db)
            health_report["metrics"]["hung_jobs"] = hung_jobs
            
            # 3. Check for veraciocca-type bugs
            veraciocca_bugs = await self._check_veraciocca_bugs(db)
            health_report["metrics"]["partial_data_bugs"] = veraciocca_bugs
            
            # 4. Check processing performance
            performance_metrics = await self._check_processing_performance(db)
            health_report["system_performance"] = performance_metrics
            
            # 5. Check data consistency trends
            consistency_trends = await self._check_consistency_trends(db)
            health_report["metrics"]["consistency"] = consistency_trends
            
            # 6. Generate alerts based on metrics
            alerts = await self._generate_health_alerts(
                job_metrics, hung_jobs, veraciocca_bugs, performance_metrics
            )
            health_report["alerts"] = alerts
            
            # 7. Determine overall system status
            health_report["overall_status"] = self._determine_system_status(alerts)
            
            # 8. Generate recommendations
            health_report["recommendations"] = await self._generate_health_recommendations(
                health_report["metrics"], alerts
            )
            
            # Update internal health metrics
            self.health_metrics['last_health_check'] = datetime.now(timezone.utc)
            self.health_metrics['system_status'] = health_report["overall_status"]
            
            logger.info(f"Health check completed: {health_report['overall_status']} status with {len(alerts)} alerts")
            
            return health_report
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_report["overall_status"] = "health_check_failed"
            health_report["error"] = str(e)
            return health_report
    
    async def _check_job_performance(self, db: AsyncSession) -> Dict[str, Any]:
        """Check AI analysis job success rates and performance"""
        
        # Jobs in last 24 hours
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Total jobs
        total_jobs = await db.execute(
            select(func.count(AIAnalysisJob.id)).where(
                AIAnalysisJob.created_at >= cutoff_time
            )
        )
        total_count = total_jobs.scalar()
        
        # Successful jobs
        successful_jobs = await db.execute(
            select(func.count(AIAnalysisJob.id)).where(
                and_(
                    AIAnalysisJob.created_at >= cutoff_time,
                    AIAnalysisJob.status == 'completed'
                )
            )
        )
        success_count = successful_jobs.scalar()
        
        # Failed jobs
        failed_jobs = await db.execute(
            select(func.count(AIAnalysisJob.id)).where(
                and_(
                    AIAnalysisJob.created_at >= cutoff_time,
                    AIAnalysisJob.status == 'failed'
                )
            )
        )
        failed_count = failed_jobs.scalar()
        
        # Running jobs (potentially hung)
        running_jobs = await db.execute(
            select(func.count(AIAnalysisJob.id)).where(
                and_(
                    AIAnalysisJob.created_at >= cutoff_time,
                    AIAnalysisJob.status == 'running'
                )
            )
        )
        running_count = running_jobs.scalar()
        
        # Calculate rates
        success_rate = (success_count / max(1, total_count)) * 100
        failure_rate = (failed_count / max(1, total_count)) * 100
        
        return {
            "total_jobs_24h": total_count,
            "successful_jobs": success_count,
            "failed_jobs": failed_count,
            "running_jobs": running_count,
            "success_rate_percentage": round(success_rate, 1),
            "failure_rate_percentage": round(failure_rate, 1),
            "is_healthy": failure_rate < (self.alert_thresholds['job_failure_rate'] * 100)
        }
    
    async def _check_hung_jobs(self, db: AsyncSession) -> Dict[str, Any]:
        """Check for jobs that have hung without progress"""
        
        hung_timeout = datetime.now(timezone.utc) - timedelta(seconds=self.alert_thresholds['hung_job_timeout'])
        
        hung_jobs_query = await db.execute(
            select(AIAnalysisJob).where(
                and_(
                    AIAnalysisJob.status == 'running',
                    or_(
                        AIAnalysisJob.last_heartbeat < hung_timeout,
                        AIAnalysisJob.last_heartbeat.is_(None)
                    )
                )
            )
        )
        hung_jobs = hung_jobs_query.scalars().all()
        
        hung_job_details = []
        for job in hung_jobs:
            time_since_heartbeat = None
            if job.last_heartbeat:
                time_since_heartbeat = (datetime.now(timezone.utc) - job.last_heartbeat).total_seconds()
            
            hung_job_details.append({
                "job_id": job.job_id,
                "profile_id": str(job.profile_id),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "time_since_heartbeat_seconds": time_since_heartbeat,
                "posts_processed": job.posts_processed,
                "total_posts": job.total_posts
            })
        
        return {
            "hung_jobs_count": len(hung_jobs),
            "hung_jobs": hung_job_details,
            "is_healthy": len(hung_jobs) == 0
        }
    
    async def _check_veraciocca_bugs(self, db: AsyncSession) -> Dict[str, Any]:
        """Check for profiles with veraciocca-type partial data bugs"""
        
        try:
            bug_profiles = await ai_data_consistency_service.detect_veraciocca_type_bugs(db)
            
            return {
                "veraciocca_bugs_count": len(bug_profiles),
                "affected_profiles": [p['username'] for p in bug_profiles[:10]],  # Limit to 10 for alerts
                "bug_details": bug_profiles,
                "is_healthy": len(bug_profiles) < self.alert_thresholds['partial_data_threshold']
            }
            
        except Exception as e:
            logger.error(f"Failed to check veraciocca bugs: {e}")
            return {
                "veraciocca_bugs_count": -1,
                "error": str(e),
                "is_healthy": False
            }
    
    async def _check_processing_performance(self, db: AsyncSession) -> Dict[str, Any]:
        """Check AI analysis processing performance metrics"""
        
        # Jobs completed in last 24 hours with timing data
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        performance_query = await db.execute(
            select(
                func.avg(AIAnalysisJob.processing_duration_seconds).label('avg_duration'),
                func.max(AIAnalysisJob.processing_duration_seconds).label('max_duration'),
                func.min(AIAnalysisJob.processing_duration_seconds).label('min_duration'),
                func.avg(AIAnalysisJob.posts_per_second).label('avg_posts_per_second')
            ).where(
                and_(
                    AIAnalysisJob.created_at >= cutoff_time,
                    AIAnalysisJob.status == 'completed',
                    AIAnalysisJob.processing_duration_seconds.isnot(None)
                )
            )
        )
        performance_stats = performance_query.first()
        
        avg_duration = performance_stats.avg_duration or 0
        max_duration = performance_stats.max_duration or 0
        min_duration = performance_stats.min_duration or 0
        avg_posts_per_second = performance_stats.avg_posts_per_second or 0
        
        return {
            "average_processing_time_seconds": round(avg_duration, 1),
            "max_processing_time_seconds": max_duration,
            "min_processing_time_seconds": min_duration,
            "average_posts_per_second": round(avg_posts_per_second, 2),
            "performance_threshold_seconds": self.alert_thresholds['processing_time_threshold'],
            "is_healthy": avg_duration < self.alert_thresholds['processing_time_threshold']
        }
    
    async def _check_consistency_trends(self, db: AsyncSession) -> Dict[str, Any]:
        """Check data consistency trends over time"""
        
        try:
            # Run basic consistency check
            consistency_report = await ai_data_consistency_service.run_comprehensive_consistency_check(db)
            
            total_issues = len(consistency_report.get('issues_found', []))
            affected_profiles = len(consistency_report.get('profiles_affected', []))
            
            return {
                "total_consistency_issues": total_issues,
                "profiles_affected": affected_profiles,
                "issue_types": [issue['check_type'] for issue in consistency_report.get('issues_found', [])],
                "overall_consistency_status": consistency_report.get('overall_status', 'unknown'),
                "is_healthy": consistency_report.get('overall_status') == 'healthy'
            }
            
        except Exception as e:
            logger.error(f"Failed to check consistency trends: {e}")
            return {
                "error": str(e),
                "is_healthy": False
            }
    
    async def _generate_health_alerts(self, job_metrics, hung_jobs, veraciocca_bugs, performance_metrics) -> List[Dict[str, Any]]:
        """Generate alerts based on health metrics"""
        
        alerts = []
        
        # Job failure rate alert
        if not job_metrics.get('is_healthy', True):
            alerts.append({
                "severity": "high",
                "type": "job_failure_rate",
                "message": f"AI job failure rate is {job_metrics['failure_rate_percentage']}% (threshold: {self.alert_thresholds['job_failure_rate'] * 100}%)",
                "details": {
                    "failed_jobs": job_metrics['failed_jobs'],
                    "total_jobs": job_metrics['total_jobs_24h'],
                    "failure_rate": job_metrics['failure_rate_percentage']
                },
                "action_required": "Investigate failed jobs and fix underlying issues"
            })
        
        # Hung jobs alert
        if not hung_jobs.get('is_healthy', True):
            alerts.append({
                "severity": "critical",
                "type": "hung_jobs",
                "message": f"{hung_jobs['hung_jobs_count']} AI jobs are hung without progress",
                "details": {
                    "hung_jobs_count": hung_jobs['hung_jobs_count'],
                    "hung_jobs": hung_jobs['hung_jobs'][:3]  # First 3 for alert
                },
                "action_required": "Kill hung jobs and investigate session management issues"
            })
        
        # Veraciocca bugs alert
        if not veraciocca_bugs.get('is_healthy', True):
            alerts.append({
                "severity": "high",
                "type": "partial_data_bugs",
                "message": f"{veraciocca_bugs['veraciocca_bugs_count']} profiles have veraciocca-type partial data bugs",
                "details": {
                    "affected_profiles_count": veraciocca_bugs['veraciocca_bugs_count'],
                    "sample_profiles": veraciocca_bugs['affected_profiles'][:5]
                },
                "action_required": "Run profile aggregation repair for affected profiles"
            })
        
        # Performance alert
        if not performance_metrics.get('is_healthy', True):
            alerts.append({
                "severity": "medium",
                "type": "processing_performance",
                "message": f"AI processing is slow: {performance_metrics['average_processing_time_seconds']}s average (threshold: {self.alert_thresholds['processing_time_threshold']}s)",
                "details": {
                    "average_duration": performance_metrics['average_processing_time_seconds'],
                    "max_duration": performance_metrics['max_processing_time_seconds'],
                    "posts_per_second": performance_metrics['average_posts_per_second']
                },
                "action_required": "Investigate performance bottlenecks and optimize processing"
            })
        
        return alerts
    
    def _determine_system_status(self, alerts: List[Dict[str, Any]]) -> str:
        """Determine overall system status based on alerts"""
        
        if not alerts:
            return "healthy"
        
        critical_alerts = [a for a in alerts if a['severity'] == 'critical']
        high_alerts = [a for a in alerts if a['severity'] == 'high']
        
        if critical_alerts:
            return "critical"
        elif high_alerts:
            return "degraded"
        else:
            return "warning"
    
    async def _generate_health_recommendations(self, metrics: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on health metrics"""
        
        recommendations = []
        
        # Job performance recommendations
        job_metrics = metrics.get('jobs', {})
        if job_metrics.get('failure_rate_percentage', 0) > 10:
            recommendations.append({
                "priority": "high",
                "category": "job_reliability",
                "recommendation": "Investigate and fix root causes of job failures",
                "action": "Review failed job logs and implement fixes"
            })
        
        # Hung jobs recommendations
        hung_jobs = metrics.get('hung_jobs', {})
        if hung_jobs.get('hung_jobs_count', 0) > 0:
            recommendations.append({
                "priority": "critical",
                "category": "background_tasks",
                "recommendation": "Implement job timeout and automatic cleanup for hung jobs",
                "action": "Add heartbeat monitoring and job cleanup service"
            })
        
        # Partial data recommendations
        partial_data = metrics.get('partial_data_bugs', {})
        if partial_data.get('veraciocca_bugs_count', 0) > 0:
            recommendations.append({
                "priority": "high",
                "category": "data_consistency",
                "recommendation": "Run repair operations for profiles with partial AI data",
                "action": "Use /ai/repair/profile-aggregation endpoint to fix affected profiles"
            })
        
        # Performance recommendations
        performance = metrics.get('system_performance', {})
        if performance.get('average_processing_time_seconds', 0) > 180:
            recommendations.append({
                "priority": "medium",
                "category": "performance",
                "recommendation": "Optimize AI processing performance",
                "action": "Review model loading, batch sizes, and database query optimization"
            })
        
        return recommendations
    
    async def send_health_alert(self, alert: Dict[str, Any], recipients: List[str] = None) -> bool:
        """Send health alert via email/webhook (placeholder implementation)"""
        
        try:
            # This is a placeholder - implement actual alerting (email, Slack, etc.)
            logger.warning(f"HEALTH ALERT [{alert['severity'].upper()}]: {alert['message']}")
            logger.warning(f"Action required: {alert['action_required']}")
            
            # Log alert details for debugging
            if alert.get('details'):
                logger.warning(f"Alert details: {alert['details']}")
            
            # In production, implement actual email/Slack/webhook alerts here
            # Example email alert code (requires SMTP configuration):
            # await self._send_email_alert(alert, recipients)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send health alert: {e}")
            return False
    
    async def get_system_health_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get quick system health summary for dashboard"""
        
        try:
            # Quick health metrics (last 1 hour)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            # Recent job stats
            recent_jobs = await db.execute(
                select(func.count(AIAnalysisJob.id)).where(
                    AIAnalysisJob.created_at >= cutoff_time
                )
            )
            recent_jobs_count = recent_jobs.scalar()
            
            # Recent failures
            recent_failures = await db.execute(
                select(func.count(AIAnalysisJob.id)).where(
                    and_(
                        AIAnalysisJob.created_at >= cutoff_time,
                        AIAnalysisJob.status == 'failed'
                    )
                )
            )
            recent_failures_count = recent_failures.scalar()
            
            # Quick veraciocca check
            veraciocca_count = 0
            try:
                bug_profiles = await ai_data_consistency_service.detect_veraciocca_type_bugs(db)
                veraciocca_count = len(bug_profiles)
            except:
                pass
            
            # Determine status
            status = "healthy"
            if veraciocca_count > 5 or recent_failures_count > 3:
                status = "degraded"
            elif recent_failures_count > 0 or veraciocca_count > 0:
                status = "warning"
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "metrics": {
                    "recent_jobs_1h": recent_jobs_count,
                    "recent_failures_1h": recent_failures_count,
                    "veraciocca_bugs": veraciocca_count,
                    "last_health_check": self.health_metrics.get('last_health_check')
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "unknown",
                "error": str(e)
            }

# Global instance
ai_monitoring_service = AIMonitoringService()