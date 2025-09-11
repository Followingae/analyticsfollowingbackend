#!/usr/bin/env python3
"""
FIXED Celery AI Worker Startup Script
Starts AI analysis worker with proper Windows configuration
"""
import os
import sys

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

if __name__ == "__main__":
    # Kill all existing Celery workers first
    print("🧹 Cleaning up any existing workers...")
    os.system("taskkill /f /im python.exe >nul 2>&1")
    
    print("🚀 Starting FIXED AI Background Worker...")
    
    # Start worker with SOLO pool for Windows compatibility
    # This should fix the "not enough values to unpack" error
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.workers.ai_background_worker",
        "worker",
        "--loglevel=info",
        "--pool=solo",  # CRITICAL: Use solo pool for Windows
        "--concurrency=1",  # Solo pool supports only 1 worker
        "--queues=celery,ai_analysis,health_checks",
        "--without-gossip",  # Disable gossip for Windows
        "--without-mingle",  # Disable mingle for Windows
        "--without-heartbeat"  # Disable heartbeat for Windows
    ]
    
    print(f"🎯 Executing: {' '.join(cmd)}")
    os.execv(sys.executable, cmd)