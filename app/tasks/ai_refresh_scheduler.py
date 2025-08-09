"""
AI Data Refresh Background Scheduler
Automatically refreshes incomplete/stale AI analysis data
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from app.services.ai_refresh_service import ai_refresh_service

logger = logging.getLogger(__name__)


class AIRefreshScheduler:
    """Background scheduler for AI data refresh tasks"""
    
    def __init__(self):
        self.is_running = False
        self._task = None
        self.stats = {
            'last_run': None,
            'total_runs': 0,
            'total_profiles_refreshed': 0,
            'total_failures': 0,
            'is_active': False
        }
    
    async def start(self):
        """Start the background AI refresh scheduler"""
        if self.is_running:
            logger.warning("AI_SCHEDULER: Already running, skipping start")
            return
        
        self.is_running = True
        self.stats['is_active'] = True
        
        logger.info("AI_SCHEDULER: Starting background AI data refresh scheduler")
        self._task = asyncio.create_task(self._run_scheduler())
    
    async def stop(self):
        """Stop the background AI refresh scheduler"""
        if not self.is_running:
            return
        
        logger.info("AI_SCHEDULER: Stopping background AI data refresh scheduler")
        self.is_running = False
        self.stats['is_active'] = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_scheduler(self):
        """Main scheduler loop"""
        try:
            while self.is_running:
                try:
                    await self._run_ai_refresh_cycle()
                    
                    # Wait 24 hours between runs (daily refresh)
                    await asyncio.sleep(24 * 60 * 60)  # 24 hours
                    
                except asyncio.CancelledError:
                    logger.info("AI_SCHEDULER: Scheduler cancelled")
                    break
                except Exception as e:
                    logger.error(f"AI_SCHEDULER: Error in scheduler cycle: {e}")
                    # Wait 5 minutes before retrying after error
                    await asyncio.sleep(5 * 60)
                    
        except asyncio.CancelledError:
            logger.info("AI_SCHEDULER: Scheduler task cancelled")
        finally:
            self.is_running = False
            self.stats['is_active'] = False
    
    async def _run_ai_refresh_cycle(self):
        """Run a single AI refresh cycle"""
        logger.info("AI_SCHEDULER: Starting daily AI refresh cycle")
        cycle_start = datetime.now()
        
        try:
            # Get current statistics
            stats = await ai_refresh_service.get_ai_refresh_statistics()
            logger.info(f"AI_SCHEDULER: Current stats - {stats['profiles_needing_refresh']} profiles, {stats['posts_needing_refresh']} posts need refresh")
            
            if stats['profiles_needing_refresh'] == 0:
                logger.info("AI_SCHEDULER: No profiles need refresh, skipping cycle")
                return
            
            # Determine batch size based on current load
            if stats['profiles_needing_refresh'] > 100:
                batch_size = 20  # Larger batches for high volume
            elif stats['profiles_needing_refresh'] > 50:
                batch_size = 15  # Medium batches
            else:
                batch_size = 10  # Small batches for low volume
            
            logger.info(f"AI_SCHEDULER: Running batch refresh with batch_size={batch_size}")
            
            # Run batch refresh
            results = await ai_refresh_service.run_batch_ai_refresh(batch_size=batch_size)
            
            # Update stats
            self.stats['last_run'] = cycle_start
            self.stats['total_runs'] += 1
            self.stats['total_profiles_refreshed'] += results['successful']
            self.stats['total_failures'] += results['failed']
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"AI_SCHEDULER: Cycle complete in {cycle_duration:.1f}s - {results['successful']}/{results['attempted']} profiles refreshed")
            
        except Exception as e:
            logger.error(f"AI_SCHEDULER: Error in refresh cycle: {e}")
            self.stats['total_failures'] += 1
    
    async def trigger_manual_refresh(self, batch_size: int = 5) -> Dict[str, Any]:
        """Manually trigger an AI refresh cycle"""
        logger.info(f"AI_SCHEDULER: Manual refresh triggered (batch_size={batch_size})")
        
        try:
            results = await ai_refresh_service.run_batch_ai_refresh(batch_size=batch_size)
            
            # Update manual run stats
            self.stats['total_profiles_refreshed'] += results['successful']
            self.stats['total_failures'] += results['failed']
            
            return {
                'success': True,
                'results': results,
                'message': f"Manual refresh complete - {results['successful']}/{results['attempted']} profiles refreshed"
            }
            
        except Exception as e:
            logger.error(f"AI_SCHEDULER: Manual refresh failed: {e}")
            self.stats['total_failures'] += 1
            
            return {
                'success': False,
                'error': str(e),
                'message': f"Manual refresh failed: {str(e)}"
            }
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status and statistics"""
        current_stats = await ai_refresh_service.get_ai_refresh_statistics()
        
        return {
            'scheduler': {
                'is_running': self.is_running,
                'is_active': self.stats['is_active'],
                'last_run': self.stats['last_run'].isoformat() if self.stats['last_run'] else None,
                'total_runs': self.stats['total_runs'],
                'total_profiles_refreshed': self.stats['total_profiles_refreshed'],
                'total_failures': self.stats['total_failures']
            },
            'current_stats': current_stats,
            'next_run_estimate': (
                datetime.now() + timedelta(hours=24)
            ).isoformat() if self.is_running else None
        }
    
    async def refresh_specific_profile(self, username: str) -> Dict[str, Any]:
        """Refresh AI data for a specific profile by username"""
        try:
            from app.database.connection import SessionLocal
            from app.database.unified_models import Profile
            from sqlalchemy import select
            
            async with SessionLocal() as db:
                # Find profile by username
                result = await db.execute(
                    select(Profile).where(Profile.username.ilike(username))
                )
                profile = result.scalar_one_or_none()
                
                if not profile:
                    return {
                        'success': False,
                        'error': 'profile_not_found',
                        'message': f"Profile '{username}' not found"
                    }
                
                # Check if refresh is needed
                completeness = await ai_refresh_service.check_profile_ai_completeness(profile)
                
                if completeness['profile_ai_complete'] and not completeness['profile_ai_stale']:
                    return {
                        'success': True,
                        'message': f"Profile '{username}' AI data is already complete and fresh",
                        'refresh_needed': False
                    }
                
                # Perform refresh
                logger.info(f"AI_SCHEDULER: Manual refresh for profile '{username}'")
                success = await ai_refresh_service.refresh_profile_ai_data(profile)
                
                if success:
                    return {
                        'success': True,
                        'message': f"Successfully refreshed AI data for profile '{username}'",
                        'refresh_performed': True
                    }
                else:
                    return {
                        'success': False,
                        'error': 'refresh_failed',
                        'message': f"Failed to refresh AI data for profile '{username}'"
                    }
                    
        except Exception as e:
            logger.error(f"AI_SCHEDULER: Error refreshing profile '{username}': {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Error refreshing profile '{username}': {str(e)}"
            }


# Global scheduler instance
ai_refresh_scheduler = AIRefreshScheduler()