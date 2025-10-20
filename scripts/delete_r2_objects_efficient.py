#!/usr/bin/env python3
"""
Efficient script to delete all contents from Cloudflare R2 bucket
"""
import requests
import json
import time
from urllib.parse import quote

# Cloudflare credentials
ACCOUNT_ID = "189e3487e64c5c71c8bdae14f475f075"
API_TOKEN = "qBkxKlziYq0pSelqJo4iSYxovnFhCPy5rxTbphCm"
BUCKET_NAME = "thumbnails-prod"

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/r2/buckets/{BUCKET_NAME}/objects"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def list_objects(cursor=None):
    """List objects in the bucket"""
    url = BASE_URL
    if cursor:
        url += f"?cursor={cursor}"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error listing objects: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception listing objects: {e}")
        return None

def delete_object(object_key):
    """Delete a single object"""
    # URL encode the object key to handle special characters
    encoded_key = quote(object_key, safe='')
    url = f"{BASE_URL}/{encoded_key}"

    try:
        response = requests.delete(url, headers=headers, timeout=30)

        if response.status_code in [200, 204]:
            # Check if response indicates success
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("success", False):
                        return True
                except:
                    pass
            elif response.status_code == 204:
                return True

        print(f"Failed to delete {object_key}: {response.status_code}")
        return False

    except Exception as e:
        print(f"Exception deleting {object_key}: {e}")
        return False

def delete_all_objects():
    """Delete all objects in the bucket"""
    total_deleted = 0
    total_failed = 0
    cursor = None
    batch_number = 0

    print(f"Starting deletion of all objects in bucket: {BUCKET_NAME}")
    print("=" * 80)

    while True:
        batch_number += 1
        print(f"Processing batch {batch_number}...")

        # List objects
        result = list_objects(cursor)

        if not result or not result.get("success"):
            print("Failed to list objects or API error")
            break

        objects = result.get("result", [])

        if not objects:
            print("No more objects to delete")
            break

        print(f"Found {len(objects)} objects in this batch")

        # Delete each object in this batch
        batch_deleted = 0
        batch_failed = 0

        for i, obj in enumerate(objects, 1):
            object_key = obj["key"]
            print(f"  [{i}/{len(objects)}] Deleting: {object_key}")

            if delete_object(object_key):
                batch_deleted += 1
                total_deleted += 1
            else:
                batch_failed += 1
                total_failed += 1

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        print(f"Batch {batch_number} complete: {batch_deleted} deleted, {batch_failed} failed")

        # Check if there are more objects
        result_info = result.get("result_info", {})
        if not result_info.get("is_truncated", False):
            print("No more objects (not truncated)")
            break

        cursor = result_info.get("cursor")
        if not cursor:
            print("No cursor for next batch")
            break

        print(f"Moving to next batch...")
        print("-" * 40)

        # Delay between batches
        time.sleep(1)

    print("=" * 80)
    print(f"DELETION SUMMARY:")
    print(f"Successfully deleted: {total_deleted} objects")
    print(f"Failed to delete: {total_failed} objects")

    return total_deleted, total_failed

def verify_empty():
    """Verify the bucket is empty"""
    print("\n" + "=" * 40)
    print("VERIFYING BUCKET IS EMPTY")
    print("=" * 40)

    result = list_objects()

    if result and result.get("success"):
        objects = result.get("result", [])
        if len(objects) == 0:
            print("SUCCESS: Bucket is completely empty!")
            return True
        else:
            print(f"WARNING: Bucket still contains {len(objects)} objects:")
            for obj in objects[:5]:  # Show first 5
                print(f"  - {obj['key']}")
            if len(objects) > 5:
                print(f"  ... and {len(objects) - 5} more")
            return False
    else:
        print("ERROR: Could not verify bucket status")
        return False

if __name__ == "__main__":
    try:
        print("Cloudflare R2 Bucket Cleanup Tool")
        print("=" * 50)

        # Delete all objects
        deleted, failed = delete_all_objects()

        # Verify bucket is empty
        is_empty = verify_empty()

        # Final summary
        print("\n" + "=" * 50)
        print("FINAL RESULTS:")
        print(f"Objects deleted: {deleted}")
        print(f"Failed deletions: {failed}")
        print(f"Bucket empty: {'Yes' if is_empty else 'No'}")

        if failed == 0 and is_empty:
            print("\nSUCCESS: All bucket contents deleted successfully!")
            exit(0)
        else:
            print(f"\nPARTIAL SUCCESS: Check any remaining objects manually")
            exit(1)

    except KeyboardInterrupt:
        print("\n\nINTERRUPTED: Deletion process was stopped by user")
        exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        exit(1)