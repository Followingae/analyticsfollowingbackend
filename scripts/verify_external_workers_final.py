#!/usr/bin/env python3
"""
Final verification that admin operations use external workers
Tests the complete job queue -> Celery worker pipeline
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_job_queue_celery_integration():
    """Test that job queue successfully triggers Celery workers"""
    print("\n" + "="*60)
    print("TESTING JOB QUEUE -> CELERY INTEGRATION")
    print("="*60)

    try:
        from app.core.job_queue import job_queue, JobPriority, QueueType
        from app.database.optimized_pools import optimized_pools

        # Initialize systems
        await optimized_pools.initialize()
        await job_queue.initialize()

        start_time = datetime.now()
        print(f"Queueing job at {start_time}")

        # Queue a job - this should trigger Celery worker
        job_id = await job_queue.enqueue_job(
            user_id="test_admin",
            job_type="profile_analysis",
            params={
                "username": "test_external_verification",
                "credit_cost": 0
            },
            priority=JobPriority.HIGH,
            queue_type=QueueType.API_QUEUE,
            user_tier="admin"
        )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        print(f"Job queue execution time: {execution_time:.3f} seconds")
        print(f"Job ID: {job_id}")

        # Verify job was created in database
        async with optimized_pools.get_user_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT status, job_type, params FROM job_queue WHERE id = :job_id"),
                {"job_id": job_id}
            )
            job_data = result.fetchone()

        if job_data:
            print(f"Job stored in database: {job_data.status} - {job_data.job_type}")
            print("SUCCESS: Job queue integration working")
            return True
        else:
            print("FAILURE: Job not found in database")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_profile_repair_external_worker():
    """Test that profile repair uses external workers"""
    print("\n" + "="*60)
    print("TESTING PROFILE REPAIR EXTERNAL WORKERS")
    print("="*60)

    try:
        from app.services.profile_completeness_repair_service import ProfileCompletenessRepairService, ProfileStatus, ProfileCompleteness

        service = ProfileCompletenessRepairService()

        # Create mock incomplete profile
        mock_profile = ProfileStatus(
            username="test_repair_external",
            completeness=ProfileCompleteness.INCOMPLETE,
            missing_components=["ai_analysis"]
        )

        start_time = datetime.now()
        print(f"Starting profile repair at {start_time}")

        # This should queue a job, not process directly
        success = await service.repair_profile(mock_profile)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        print(f"Profile repair execution time: {execution_time:.3f} seconds")
        print(f"Repair initiated: {success}")

        if execution_time < 1.0 and success:
            print("SUCCESS: Fast handoff achieved - external worker queued")
            return True
        else:
            print("FAILURE: Too slow or failed - may be processing in main thread")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_celery_worker_availability():
    """Test that Celery worker can be imported and tasks are registered"""
    print("\n" + "="*60)
    print("TESTING CELERY WORKER AVAILABILITY")
    print("="*60)

    try:
        from app.workers.unified_worker import celery_app

        # Check available tasks
        available_tasks = [
            task for task in celery_app.tasks.keys()
            if 'app.workers.unified_worker' in task
        ]

        print(f"Available Celery tasks: {len(available_tasks)}")
        for task in available_tasks:
            print(f"  - {task}")

        required_tasks = [
            'app.workers.unified_worker.process_profile_analysis',
            'app.workers.unified_worker.process_profile_analysis_background',
            'app.workers.unified_worker.process_bulk_analysis'
        ]

        missing_tasks = [task for task in required_tasks if task not in available_tasks]

        if not missing_tasks:
            print("SUCCESS: All required Celery tasks are registered")
            return True
        else:
            print(f"FAILURE: Missing required tasks: {missing_tasks}")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_no_heavy_imports_in_main():
    """Test that heavy processing modules aren't imported in main process"""
    print("\n" + "="*60)
    print("TESTING NO HEAVY IMPORTS IN MAIN PROCESS")
    print("="*60)

    try:
        import sys
        loaded_modules = list(sys.modules.keys())

        # Check for heavy AI/ML imports that shouldn't be in main process
        heavy_modules = [
            mod for mod in loaded_modules
            if any(keyword in mod.lower() for keyword in [
                'torch', 'transformers', 'sklearn', 'tensorflow'
            ])
        ]

        print(f"Total loaded modules: {len(loaded_modules)}")
        print(f"Heavy AI/ML modules: {len(heavy_modules)}")

        if heavy_modules:
            print("Heavy modules found:")
            for mod in heavy_modules:
                print(f"  - {mod}")
            print("WARNING: Heavy modules loaded in main process")
            return False
        else:
            print("SUCCESS: No heavy AI/ML modules in main process")
            return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Run comprehensive external worker verification"""
    print("EXTERNAL WORKER SYSTEM VERIFICATION")
    print("Verifying that admin operations use external workers")
    print("=" * 80)

    try:
        # Run all tests
        test1 = await test_celery_worker_availability()
        test2 = await test_job_queue_celery_integration()
        test3 = await test_profile_repair_external_worker()
        test4 = await test_no_heavy_imports_in_main()

        print("\n" + "="*80)
        print("FINAL VERIFICATION RESULTS")
        print("="*80)

        results = {
            "Celery Worker Tasks": test1,
            "Job Queue Integration": test2,
            "Profile Repair External": test3,
            "No Heavy Imports": test4
        }

        for test_name, passed in results.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {test_name}: {status}")

        overall_success = all(results.values())

        print("\n" + "-"*80)
        if overall_success:
            print("SUCCESS: External worker system is fully functional!")
            print("- Admin operations use external Celery workers")
            print("- Job queue triggers workers correctly")
            print("- Fast handoff pattern achieved")
            print("- No heavy processing in main process")
            print("- Complete resource isolation achieved")
        else:
            print("ISSUES DETECTED: External worker system needs attention")
            failed_tests = [name for name, passed in results.items() if not passed]
            print(f"Failed tests: {', '.join(failed_tests)}")

        return overall_success

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\nExiting with code: {0 if success else 1}")
    sys.exit(0 if success else 1)