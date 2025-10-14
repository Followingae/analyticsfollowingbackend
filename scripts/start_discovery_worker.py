#!/usr/bin/env python3
"""
Start Discovery Worker - Industry Standard Background Processing

This script starts the Celery discovery worker that processes profiles
in a completely separate process from the main application.

Usage:
    python scripts/start_discovery_worker.py
"""
import os
import sys
import subprocess
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_discovery_worker():
    """Start the discovery worker process"""
    try:
        logger.info("🏭 Starting Discovery Worker (Industry Standard)")
        logger.info("📊 This worker runs completely separate from the main app")
        logger.info("⚡ Main app will remain 100% responsive while this processes profiles")

        # Change to project directory
        os.chdir(project_root)

        # Command to start the worker
        cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.workers.discovery_worker",
            "worker",
            "--loglevel=info",
            "--concurrency=1",  # Process one profile at a time
            "--hostname=discovery_worker@%h",
            "--queues=celery",  # Listen to default queue
            "--pool=solo"  # Single process pool for Windows compatibility
        ]

        logger.info(f"🚀 Starting worker with command: {' '.join(cmd)}")

        # Start the worker
        subprocess.run(cmd, check=True)

    except KeyboardInterrupt:
        logger.info("🛑 Discovery worker stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Worker failed to start: {e}")
        logger.error("💡 Make sure Redis is running and accessible")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🏭 ANALYTICS FOLLOWING - DISCOVERY WORKER")
    print("=" * 60)
    print("📊 Industry Standard Background Processing")
    print("⚡ Zero Impact on Main Application")
    print("🔄 Processing Profiles for Database Building")
    print("=" * 60)
    print()

    start_discovery_worker()