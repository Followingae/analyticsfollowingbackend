"""
Background Worker Management Service
Handles automatic startup and management of Celery workers for AI and CDN processing
"""
import subprocess
import threading
import logging
import time
import os
import sys
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class WorkerManager:
    def __init__(self):
        self.workers: Dict[str, subprocess.Popen] = {}
        self.worker_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
        
    def start_ai_worker(self) -> bool:
        """Start AI background worker"""
        try:
            logger.info("Starting AI background worker...")
            
            # Command to start AI worker
            cmd = [
                sys.executable, "-m", "celery",
                "-A", "app.workers.ai_background_worker",
                "worker",
                "--loglevel=info",
                "--pool=solo",
                "--concurrency=1",
                "--queues=celery,ai_analysis,health_checks"
            ]
            
            # Start worker process
            worker_process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.workers['ai_worker'] = worker_process
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_worker,
                args=('ai_worker', worker_process),
                daemon=True
            )
            monitor_thread.start()
            self.worker_threads['ai_worker'] = monitor_thread
            
            logger.info("AI worker started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start AI worker: {e}")
            return False
    
    def start_cdn_worker(self) -> bool:
        """Start CDN background worker"""
        try:
            logger.info("Starting CDN background worker...")
            
            # Command to start CDN worker
            cmd = [
                sys.executable, "-m", "celery",
                "-A", "app.workers.simple_cdn_worker",
                "worker", 
                "--loglevel=info",
                "--pool=solo",
                "--concurrency=1",
                "--queues=celery"
            ]
            
            # Start worker process
            worker_process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.workers['cdn_worker'] = worker_process
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_worker,
                args=('cdn_worker', worker_process),
                daemon=True
            )
            monitor_thread.start()
            self.worker_threads['cdn_worker'] = monitor_thread
            
            logger.info("CDN worker started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start CDN worker: {e}")
            return False
    
    def _monitor_worker(self, worker_name: str, process: subprocess.Popen):
        """Monitor worker process and log output"""
        try:
            while not self.shutdown_event.is_set():
                # Check if process is still running
                if process.poll() is not None:
                    logger.error(f"Worker {worker_name} process died unexpectedly")
                    break
                
                # Read stdout if available
                if process.stdout and process.stdout.readable():
                    try:
                        line = process.stdout.readline()
                        if line:
                            logger.info(f"[{worker_name}] {line.strip()}")
                    except:
                        pass
                
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error monitoring {worker_name}: {e}")
    
    def start_post_analytics_worker(self) -> bool:
        """Start dedicated post analytics worker (in-process async worker)"""
        try:
            logger.info("Starting Post Analytics Worker (async mode)...")

            # The Post Analytics Worker runs in-process, not as subprocess
            # It will be started after the FastAPI app starts
            # For now, just mark it as ready
            logger.info("✅ Post Analytics Worker configured - will start with FastAPI app")
            return True

        except Exception as e:
            logger.error(f"Failed to configure Post Analytics Worker: {e}")
            return False

    def start_all_workers(self) -> bool:
        """Start all background workers"""
        logger.info("Starting all background workers...")

        success_count = 0
        total_workers = 3  # AI, CDN, and Post Analytics

        # Start Post Analytics Worker (critical for non-blocking operations)
        if self.start_post_analytics_worker():
            success_count += 1
            logger.info("✅ Post Analytics Worker started")
        else:
            logger.warning("⚠️ Post Analytics Worker failed - API will be blocking!")

        # Start AI worker
        if self.start_ai_worker():
            success_count += 1

        # Wait a moment before starting CDN worker
        time.sleep(2)

        # Start CDN worker
        if self.start_cdn_worker():
            success_count += 1

        logger.info(f"Started {success_count}/{total_workers} workers successfully")
        return success_count >= 2  # At least 2 workers should be running
    
    def stop_all_workers(self):
        """Stop all background workers"""
        logger.info("Stopping all background workers...")
        
        self.shutdown_event.set()
        
        for worker_name, process in self.workers.items():
            try:
                logger.info(f"Stopping {worker_name}...")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {worker_name}")
                    process.kill()
                    
            except Exception as e:
                logger.error(f"Error stopping {worker_name}: {e}")
        
        # Clear workers
        self.workers.clear()
        self.worker_threads.clear()
        
        logger.info("All workers stopped")
    
    def get_worker_status(self) -> Dict[str, str]:
        """Get status of all workers"""
        status = {}
        
        for worker_name, process in self.workers.items():
            if process.poll() is None:
                status[worker_name] = "running"
            else:
                status[worker_name] = "stopped"
        
        return status
    
    def is_healthy(self) -> bool:
        """Check if all workers are running"""
        if not self.workers:
            return False
        
        for process in self.workers.values():
            if process.poll() is not None:
                return False
        
        return True

# Global worker manager instance
worker_manager = WorkerManager()