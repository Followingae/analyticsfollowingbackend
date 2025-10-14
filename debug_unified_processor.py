#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_unified_processor():
    try:
        from app.database.connection import init_database
        from app.services.unified_background_processor import UnifiedBackgroundProcessor

        print("=== TESTING UNIFIED BACKGROUND PROCESSOR ===")
        print("Initializing database connection...")
        await init_database()

        print("Creating unified processor...")
        processor = UnifiedBackgroundProcessor()

        print("Initializing processor services...")
        init_results = await processor.initialize_system()
        print(f"Initialization results: {init_results}")

        # Test with aishaharib profile
        profile_id = "40b133fb-97c2-4e48-8e95-4b0a990dd3a6"
        username = "aishaharib"

        print(f"\n=== TESTING APIFY VERIFICATION ===")
        apify_verification = await processor._verify_apify_data_complete(profile_id)
        print(f"Apify verification results: {apify_verification}")

        if apify_verification['complete']:
            print("Apify data verification PASSED")

            print(f"\n=== TESTING FULL PIPELINE ===")
            print(f"Starting full processing pipeline for {username}...")

            # Run the full pipeline
            results = await processor.process_profile_complete_pipeline(profile_id, username)
            print(f"Pipeline results: {results}")

        else:
            print(f"Apify data verification FAILED: {apify_verification}")

    except Exception as e:
        print(f"Error testing unified processor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_unified_processor())