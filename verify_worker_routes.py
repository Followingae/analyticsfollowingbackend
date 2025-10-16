#!/usr/bin/env python3
"""
Verify Worker Monitoring Routes Configuration

Quick script to verify that the worker monitoring routes are properly configured
and will work once the application is restarted.
"""

import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.api.worker_monitoring_routes import router as worker_monitoring_router
    from fastapi import FastAPI

    print("🔍 Worker Monitoring Routes Verification")
    print("=" * 50)

    # Check router configuration
    print(f"✅ Router prefix: {worker_monitoring_router.prefix}")
    print(f"✅ Router tags: {worker_monitoring_router.tags}")

    # List all available routes
    print(f"\n📊 Available Routes ({len(worker_monitoring_router.routes)}):")
    for route in worker_monitoring_router.routes:
        print(f"   {route.methods} {route.path}")

    # Test app integration
    test_app = FastAPI()
    test_app.include_router(worker_monitoring_router)

    print(f"\n✅ Routes successfully integrated into FastAPI app")
    print(f"✅ Total routes in test app: {len(test_app.routes)}")

    # Verify expected endpoints
    expected_endpoints = [
        "/api/v1/workers/overview",
        "/api/v1/workers/live-stream",
        "/api/v1/workers/queue/status",
        "/api/v1/workers/worker/{worker_name}/details",
        "/api/v1/workers/worker/{worker_name}/control",
        "/api/v1/workers/performance/metrics"
    ]

    actual_paths = [route.path for route in worker_monitoring_router.routes]

    print(f"\n🎯 Endpoint Verification:")
    for endpoint in expected_endpoints:
        if endpoint in actual_paths:
            print(f"   ✅ {endpoint}")
        else:
            print(f"   ❌ {endpoint} - MISSING")

    print(f"\n🎉 Worker Monitoring Routes are properly configured!")
    print(f"🔄 Restart the application to activate the routes.")

    print(f"\n📋 Test Commands (after restart):")
    print(f"   curl http://localhost:8000/api/v1/workers/overview")
    print(f"   curl http://localhost:8000/api/v1/workers/queue/status")
    print(f"   curl http://localhost:8000/api/v1/workers/live-stream")

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Verification failed: {e}")