"""
Check Laurazaraa CDN Profile Picture Issue

This script checks the CDN and profile picture data for laurazaraa
to identify why the frontend can't display the profile picture.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session, init_database

async def check_laurazaraa_cdn():
    """Check CDN and profile picture data for laurazaraa"""
    print("Checking Laurazaraa CDN Profile Picture Issue")
    print("=" * 50)

    async with get_session() as db:
        try:
            from sqlalchemy import text

            # First, check what columns exist in the profiles table
            schema_query = text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'profiles'
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)

            schema_result = await db.execute(schema_query)
            schema_records = schema_result.fetchall()

            print("PROFILES TABLE SCHEMA:")
            available_columns = []
            for column_name, data_type in schema_records:
                available_columns.append(column_name)
                print(f"  {column_name} ({data_type})")
            print()

            # Build dynamic query based on available columns
            base_columns = ['username', 'created_at', 'updated_at']
            image_columns = []

            # Check for profile picture related columns
            possible_image_columns = [
                'profile_pic_url', 'profile_pic_url_hd', 'profile_image_url',
                'profile_images', 'profile_thumbnails', 'cdn_profile_image_url',
                'proxied_profile_pic_url', 'image_urls', 'thumbnail_urls'
            ]

            for col in possible_image_columns:
                if col in available_columns:
                    image_columns.append(col)

            all_columns = base_columns + image_columns
            columns_str = ', '.join(all_columns)

            print(f"QUERYING COLUMNS: {columns_str}")
            print()

            # Check profile picture URLs and CDN data
            profile_query = text(f"""
                SELECT {columns_str}
                FROM profiles
                WHERE username = 'laurazaraa'
            """)

            profile_result = await db.execute(profile_query)
            profile_record = profile_result.fetchone()

            if profile_record:
                # Create a dict from the result
                profile_data = dict(zip(all_columns, profile_record))

                print(f"Profile: @{profile_data['username']}")
                print(f"Created: {profile_data['created_at']}")
                print(f"Updated: {profile_data['updated_at']}")
                print()

                print("PROFILE DATA:")
                for col in image_columns:
                    value = profile_data.get(col)
                    print(f"  {col}: {value}")

                # Check for JSONB data
                import json
                jsonb_columns = [col for col in image_columns if col in ['profile_images', 'profile_thumbnails', 'image_urls', 'thumbnail_urls']]

                if jsonb_columns:
                    print("\nJSONB DATA:")
                    for col in jsonb_columns:
                        value = profile_data.get(col)
                        if value:
                            try:
                                data = json.loads(value) if isinstance(value, str) else value
                                print(f"  {col}: {json.dumps(data, indent=4)}")
                            except:
                                print(f"  {col} (raw): {value}")
                        else:
                            print(f"  {col}: None")

            else:
                print("Profile 'laurazaraa' not found!")
                return

            # Check CDN image assets for this profile
            print("\n" + "="*50)
            print("CDN IMAGE ASSETS CHECK")
            print("="*50)

            cdn_assets_query = text("""
                SELECT
                    id,
                    asset_type,
                    original_url,
                    cdn_url,
                    status,
                    file_size,
                    dimensions,
                    created_at,
                    updated_at,
                    metadata
                FROM cdn_image_assets
                WHERE original_url LIKE '%laurazaraa%'
                   OR metadata::text LIKE '%laurazaraa%'
                ORDER BY created_at DESC
            """)

            cdn_result = await db.execute(cdn_assets_query)
            cdn_records = cdn_result.fetchall()

            if cdn_records:
                print(f"Found {len(cdn_records)} CDN assets:")
                for i, record in enumerate(cdn_records):
                    (asset_id, asset_type, original_url, cdn_url, status,
                     file_size, dimensions, created_at, updated_at, metadata) = record

                    print(f"\n  Asset {i+1}:")
                    print(f"    ID: {asset_id}")
                    print(f"    Type: {asset_type}")
                    print(f"    Original URL: {original_url}")
                    print(f"    CDN URL: {cdn_url}")
                    print(f"    Status: {status}")
                    print(f"    File Size: {file_size}")
                    print(f"    Dimensions: {dimensions}")
                    print(f"    Created: {created_at}")
                    print(f"    Updated: {updated_at}")
                    if metadata:
                        import json
                        try:
                            meta_data = json.loads(metadata) if isinstance(metadata, str) else metadata
                            print(f"    Metadata: {json.dumps(meta_data, indent=6)}")
                        except:
                            print(f"    Raw metadata: {metadata}")
            else:
                print("No CDN assets found for laurazaraa")

            # Check CDN processing jobs
            print("\n" + "="*50)
            print("CDN PROCESSING JOBS CHECK")
            print("="*50)

            jobs_query = text("""
                SELECT
                    id,
                    job_type,
                    status,
                    profile_username,
                    input_data,
                    result_data,
                    error_message,
                    created_at,
                    completed_at
                FROM cdn_image_jobs
                WHERE profile_username = 'laurazaraa'
                ORDER BY created_at DESC
                LIMIT 10
            """)

            jobs_result = await db.execute(jobs_query)
            jobs_records = jobs_result.fetchall()

            if jobs_records:
                print(f"Found {len(jobs_records)} CDN processing jobs:")
                for i, record in enumerate(jobs_records):
                    (job_id, job_type, status, profile_username, input_data,
                     result_data, error_message, created_at, completed_at) = record

                    print(f"\n  Job {i+1}:")
                    print(f"    ID: {job_id}")
                    print(f"    Type: {job_type}")
                    print(f"    Status: {status}")
                    print(f"    Profile: {profile_username}")
                    print(f"    Created: {created_at}")
                    print(f"    Completed: {completed_at}")
                    if error_message:
                        print(f"    Error: {error_message}")

                    if input_data:
                        import json
                        try:
                            input_json = json.loads(input_data) if isinstance(input_data, str) else input_data
                            print(f"    Input: {json.dumps(input_json, indent=6)}")
                        except:
                            print(f"    Raw input: {input_data}")

                    if result_data:
                        import json
                        try:
                            result_json = json.loads(result_data) if isinstance(result_data, str) else result_data
                            print(f"    Result: {json.dumps(result_json, indent=6)}")
                        except:
                            print(f"    Raw result: {result_data}")
            else:
                print("No CDN processing jobs found for laurazaraa")

        except Exception as e:
            print(f"ERROR during check: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    print("Starting Laurazaraa CDN Check...")
    await init_database()
    await check_laurazaraa_cdn()
    print("\nLaurazaraa CDN Check Complete")

if __name__ == "__main__":
    asyncio.run(main())