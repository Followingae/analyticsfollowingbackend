#!/usr/bin/env python3
"""
Start Celery worker for background AI processing
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.workers.ai_background_worker import celery_app
    
    print("Starting Celery worker...")
    print("Configuration:")
    print(f"- Broker: {celery_app.conf.broker_url}")
    print(f"- Backend: {celery_app.conf.result_backend}")
    print(f"- Concurrency: {celery_app.conf.worker_concurrency}")
    print(f"- Max tasks per child: {celery_app.conf.worker_max_tasks_per_child}")
    
    # Start the worker - Windows compatible
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1',
        '--max-tasks-per-child=50',
        '--pool=solo',
        '--queues=celery,ai_analysis,health_checks'
    ])
    
except KeyboardInterrupt:
    print("\nCelery worker stopped by user")
except Exception as e:
    print(f"Failed to start Celery worker: {e}")
    import traceback
    traceback.print_exc()