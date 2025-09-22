# app/tasks/cdn_sync_monitor.py

import logging
from datetime import datetime
from typing import Dict
import asyncio

from app.core.celery_app import celery_app
from app.services.cdn_sync_repair_service import CDNSyncRepairService
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="cdn_sync_monitor",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 300},  # Retry 3 times with 5min delay
    soft_time_limit=1800,  # 30 minutes soft limit
    time_limit=2400  # 40 minutes hard limit
)
def cdn_sync_monitor_task(self) -> Dict:
    """
    Periodic task to detect and repair CDN sync gaps

    Scheduled to run every 48 hours to minimize cost impact while ensuring
    sync issues are caught and resolved automatically.
    """
    task_start = datetime.utcnow()
    logger.info("Starting CDN sync monitor task")

    try:
        # Initialize sync repair service
        sync_service = CDNSyncRepairService()

        # Detect sync gaps (only check assets older than 2 hours to avoid interfering with active processing)
        logger.info("Detecting sync gaps...")
        # This function needs database session - we'll need to refactor this properly
        logger.warning("CDN sync monitor task needs database session refactoring")
        return {
            "status": "pending_refactor",
            "message": "Task needs database session injection",
            "execution_time": (datetime.utcnow() - task_start).total_seconds()
        }

        if not gaps:
            logger.info("No sync gaps detected - system healthy")
            return {
                "status": "success",
                "gaps_found": 0,
                "gaps_repaired": 0,
                "execution_time": (datetime.utcnow() - task_start).total_seconds(),
                "message": "No sync gaps detected"
            }

        # Log gap detection results
        logger.warning(f"Found {len(gaps)} CDN sync gaps requiring repair")

        # Log details of gaps found
        for gap in gaps[:5]:  # Log first 5 for debugging
            logger.info(f"Gap detected: {gap['username']}/{gap['media_id']} (created: {gap['created_at']})")

        # Repair gaps automatically
        logger.info("Starting automatic sync gap repair...")
        repair_results = sync_service.repair_sync_gaps(gaps)

        # Log repair results
        logger.info(f"Sync repair completed: {repair_results['repaired']} repaired, {repair_results['failed']} failed")

        # Log any errors
        if repair_results['errors']:
            for error in repair_results['errors'][:3]:  # Log first 3 errors
                logger.error(f"Repair error: {error}")

        # Send alert if there were failures
        if repair_results['failed'] > 0:
            asyncio.create_task(_send_sync_failure_alert(repair_results))

        execution_time = (datetime.utcnow() - task_start).total_seconds()

        return {
            "status": "success" if repair_results['failed'] == 0 else "partial_success",
            "gaps_found": len(gaps),
            "gaps_repaired": repair_results['repaired'],
            "gaps_failed": repair_results['failed'],
            "execution_time": execution_time,
            "errors": repair_results['errors'][:5],  # Limit error list
            "message": f"Repaired {repair_results['repaired']}/{len(gaps)} sync gaps"
        }

    except Exception as e:
        logger.error(f"CDN sync monitor task failed: {str(e)}", exc_info=True)

        # Send critical alert for task failure
        asyncio.create_task(_send_critical_sync_alert(str(e)))

        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e, countdown=300, max_retries=3)


@celery_app.task(name="cdn_sync_health_check")
def cdn_sync_health_check_task() -> Dict:
    """
    Daily health check task for CDN sync system

    Provides comprehensive health metrics without performing repairs.
    Useful for monitoring and alerting purposes.
    """
    logger.info("Starting CDN sync health check")

    try:
        # Run async health check in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            sync_service = CDNSyncRepairService()
            health_report = loop.run_until_complete(sync_service.get_sync_health_report())

            logger.info(f"CDN Sync Health Score: {health_report['health_score']:.1f}%")
            logger.info(f"Potential sync gaps: {health_report['potential_sync_gaps']}")
        finally:
            loop.close()

        # Alert if health score is low
        if health_report['health_score'] < 90:
            asyncio.create_task(_send_health_warning_alert(health_report))

        return {
            "status": "success",
            "health_report": health_report
        }

    except Exception as e:
        logger.error(f"CDN sync health check failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


async def _send_sync_failure_alert(repair_results: Dict):
    """Send alert when sync repair has failures"""
    try:
        # In a real implementation, integrate with your alerting system
        # For now, just log the alert
        logger.critical(
            f"CDN Sync Repair Alert: {repair_results['failed']} failures out of "
            f"{repair_results['repaired'] + repair_results['failed']} attempts. "
            f"Errors: {repair_results['errors'][:3]}"
        )

        # TODO: Integrate with Slack/Discord/Email alerting
        # await send_slack_alert("CDN Sync Repair Failures", repair_results)

    except Exception as e:
        logger.error(f"Failed to send sync failure alert: {str(e)}")


async def _send_critical_sync_alert(error_message: str):
    """Send critical alert when sync monitor task fails completely"""
    try:
        logger.critical(f"CRITICAL: CDN Sync Monitor Task Failed: {error_message}")

        # TODO: Integrate with critical alerting system
        # await send_critical_alert("CDN Sync Monitor Failure", error_message)

    except Exception as e:
        logger.error(f"Failed to send critical sync alert: {str(e)}")


async def _send_health_warning_alert(health_report: Dict):
    """Send warning when CDN sync health score is low"""
    try:
        logger.warning(
            f"CDN Sync Health Warning: Health score {health_report['health_score']:.1f}% "
            f"(Potential gaps: {health_report['potential_sync_gaps']})"
        )

        # TODO: Integrate with warning alerting system
        # await send_warning_alert("CDN Sync Health Low", health_report)

    except Exception as e:
        logger.error(f"Failed to send health warning alert: {str(e)}")


# Task scheduling configuration
def setup_cdn_sync_schedule():
    """
    Setup periodic task schedule for CDN sync monitoring

    Called during application startup to register periodic tasks
    """
    from celery.schedules import crontab

    # Main sync monitor: Every 48 hours at 2 AM UTC (low traffic time)
    celery_app.conf.beat_schedule.update({
        'cdn-sync-monitor': {
            'task': 'cdn_sync_monitor',
            'schedule': crontab(hour=2, minute=0, day_of_week='*/2'),  # Every 2 days at 2 AM
            'options': {
                'expires': 3600,  # Task expires after 1 hour if not picked up
                'priority': 3  # Lower priority to not interfere with user requests
            }
        },

        # Daily health check: Every day at 6 AM UTC
        'cdn-sync-health-check': {
            'task': 'cdn_sync_health_check',
            'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
            'options': {
                'expires': 1800,  # Task expires after 30 minutes
                'priority': 5  # Even lower priority
            }
        }
    })

    logger.info("CDN sync monitoring tasks scheduled successfully")
    logger.info("- Sync monitor: Every 48 hours at 2 AM UTC")
    logger.info("- Health check: Daily at 6 AM UTC")