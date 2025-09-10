#!/usr/bin/env python3
"""
Start CDN Worker - Simple script to start CDN background processing
"""
import sys
import os

def start_cdn_worker():
    print("Starting CDN worker...")
    print("Configuration:")
    print("- Broker: redis://localhost:6379/0")
    print("- Backend: redis://localhost:6379/0")
    print("- Concurrency: 2")
    print("- Max tasks per child: 50")
    print()
    
    try:
        # Import and start the CDN worker
        from app.workers.cdn_background_worker import celery_app
        
        # Start the worker with specific queues
        celery_app.worker_main([
            'worker',
            '--loglevel=info',
            '--concurrency=2',
            '--max-tasks-per-child=50',
            '--queues=cdn_processing,celery'
        ])
        
    except KeyboardInterrupt:
        print("CDN Worker stopped by user")
    except Exception as e:
        print(f"Error starting CDN worker: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(start_cdn_worker())