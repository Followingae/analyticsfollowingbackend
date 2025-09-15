#!/usr/bin/env python3
"""
Start Fixed CDN Worker - Correctly configured worker with MCP integration
"""
import sys
import os

def start_fixed_cdn_worker():
    print("Starting FIXED CDN Worker...")
    print("✅ Uses correct database schema")
    print("✅ Integrates with Cloudflare R2 via MCP")
    print("✅ Properly handles stuck jobs")
    print()
    print("Configuration:")
    print("- Broker: redis://localhost:6379/0")
    print("- Backend: redis://localhost:6379/0")
    print("- Concurrency: 2")
    print("- Queue: cdn_processing")
    print()

    try:
        # Import the fixed CDN worker
        from app.workers.fixed_cdn_worker import celery_app

        # Start the worker
        celery_app.worker_main([
            'worker',
            '--loglevel=info',
            '--concurrency=2',
            '--max-tasks-per-child=50',
            '--queues=cdn_processing,health_checks',
            '--hostname=fixed-cdn-worker@%h'
        ])

    except KeyboardInterrupt:
        print("Fixed CDN Worker stopped by user")
    except Exception as e:
        print(f"Error starting fixed CDN worker: {e}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(start_fixed_cdn_worker())