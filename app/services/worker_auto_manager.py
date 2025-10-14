"""
Worker Auto Manager - Auto-start discovery worker with main app
Manages the discovery worker as a subprocess for seamless operation
"""
import os
import sys
import subprocess
import logging
import asyncio
import psutil
from typing import Optional, Dict, Any
import signal
import time

logger = logging.getLogger(__name__)

class WorkerAutoManager:
    """
    Manages the discovery worker process automatically

    This ensures the discovery worker starts with the main app
    and handles both startup processing and new creator searches.
    """

    def __init__(self):
        self.worker_process: Optional[subprocess.Popen] = None
        self.is_worker_running = False
        self.startup_attempts = 0
        self.max_startup_attempts = 3

    async def start_discovery_worker(self) -> bool:
        """
        Start the discovery worker as a subprocess

        Returns:
            True if worker started successfully
        """
        try:
            if self.is_worker_running and self.worker_process:
                logger.info("🏭 Discovery worker already running")
                return True

            logger.info("🚀 Auto-starting Discovery Worker (Industry Standard)")
            logger.info("📊 Worker will run as separate process with zero impact on main app")

            # Check if Redis is available
            if not await self._check_redis_available():
                logger.error("❌ Redis not available - discovery worker requires Redis")
                return False

            # Prepare worker command
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            worker_cmd = [
                sys.executable, "-m", "celery",
                "-A", "app.workers.discovery_worker",
                "worker",
                "--loglevel=info",
                "--concurrency=1",
                "-n", "discovery_worker@main_app",  # Fixed: proper nodename syntax
                "--queues=celery",
                "--pool=solo"  # Windows compatibility - removed problematic options
            ]

            # Start worker process
            logger.info("🔄 Starting discovery worker subprocess...")

            # Create subprocess with proper error handling
            logger.info(f"📂 Working directory: {project_root}")
            logger.info(f"💻 Command: {' '.join(worker_cmd)}")

            self.worker_process = subprocess.Popen(
                worker_cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout for easier debugging
                text=True,
                bufsize=1,  # Line buffered
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            # Wait a moment to check if it started successfully
            await asyncio.sleep(2)

            if self.worker_process.poll() is None:
                self.is_worker_running = True
                logger.info(f"✅ Discovery worker started successfully (PID: {self.worker_process.pid})")
                logger.info("🏭 Worker is now processing discovery jobs independently")
                logger.info("⚡ Main app remains 100% responsive for users")

                # Start monitoring task
                asyncio.create_task(self._monitor_worker())
                return True
            else:
                logger.error(f"❌ Discovery worker failed to start (exit code: {self.worker_process.returncode})")

                # Get error output
                try:
                    stdout, stderr = self.worker_process.communicate(timeout=1)
                    if stdout:
                        logger.error(f"Worker stdout: {stdout}")
                    if stderr:
                        logger.error(f"Worker stderr: {stderr}")
                except subprocess.TimeoutExpired:
                    logger.error("Could not retrieve worker error output")

                return False

        except Exception as e:
            logger.error(f"💥 Failed to start discovery worker: {e}")
            self.startup_attempts += 1

            if self.startup_attempts < self.max_startup_attempts:
                logger.info(f"🔄 Retrying worker startup (attempt {self.startup_attempts + 1}/{self.max_startup_attempts})")
                await asyncio.sleep(5)
                return await self.start_discovery_worker()
            else:
                logger.error("❌ Max startup attempts exceeded - discovery worker unavailable")
                return False

    async def stop_discovery_worker(self) -> None:
        """Stop the discovery worker gracefully"""
        try:
            if not self.worker_process or not self.is_worker_running:
                return

            logger.info("🛑 Stopping discovery worker...")

            # Graceful shutdown
            if os.name == 'nt':  # Windows
                self.worker_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:  # Unix/Linux
                self.worker_process.send_signal(signal.SIGTERM)

            # Wait for graceful shutdown
            try:
                self.worker_process.wait(timeout=10)
                logger.info("✅ Discovery worker stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                logger.warning("⚠️ Forcing discovery worker shutdown...")
                self.worker_process.kill()
                self.worker_process.wait()
                logger.info("🔨 Discovery worker force stopped")

            self.is_worker_running = False
            self.worker_process = None

        except Exception as e:
            logger.error(f"Error stopping discovery worker: {e}")

    async def _monitor_worker(self) -> None:
        """Monitor worker health and restart if needed"""
        try:
            while self.is_worker_running and self.worker_process:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check if process is still running
                if self.worker_process.poll() is not None:
                    logger.warning("⚠️ Discovery worker process died, attempting restart...")
                    self.is_worker_running = False

                    # Attempt restart
                    await asyncio.sleep(5)
                    await self.start_discovery_worker()
                    break

        except Exception as e:
            logger.error(f"Worker monitoring error: {e}")

    async def _check_redis_available(self) -> bool:
        """Check if Redis is available for Celery"""
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            r.ping()
            return True
        except Exception:
            return False

    def get_worker_status(self) -> Dict[str, Any]:
        """Get current worker status"""
        try:
            status = {
                'worker_running': self.is_worker_running,
                'process_exists': self.worker_process is not None,
                'startup_attempts': self.startup_attempts,
                'architecture': 'industry_standard_subprocess'
            }

            if self.worker_process:
                status.update({
                    'process_id': self.worker_process.pid,
                    'process_alive': self.worker_process.poll() is None
                })

                # Get process info if available
                try:
                    process = psutil.Process(self.worker_process.pid)
                    status.update({
                        'cpu_percent': process.cpu_percent(),
                        'memory_mb': process.memory_info().rss / 1024 / 1024,
                        'status': process.status()
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return status

        except Exception as e:
            return {
                'worker_running': False,
                'error': str(e)
            }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for auto-managed worker"""
        status = self.get_worker_status()

        return {
            'auto_manager': 'healthy' if self.is_worker_running else 'degraded',
            'worker_status': status,
            'redis_available': await self._check_redis_available(),
            'management_type': 'auto_subprocess'
        }

# Global auto manager instance
worker_auto_manager = WorkerAutoManager()

# Cleanup function for graceful shutdown
async def cleanup_worker():
    """Cleanup function to call on app shutdown"""
    await worker_auto_manager.stop_discovery_worker()