#!/usr/bin/env python3
"""
Script to delete all contents from Cloudflare R2 bucket
"""
import requests
import json
import sys
import time

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

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error listing objects: {response.status_code} - {response.text}")
        return None

def delete_object(object_key):
    """Delete a single object"""
    url = f"{BASE_URL}/{object_key}"

    response = requests.delete(url, headers=headers)

    if response.status_code in [200, 204]:
        # Check if response indicates success
        try:
            result = response.json()
            if result.get("success", False):
                print(f"[SUCCESS] Deleted: {object_key}")
                return True
        except:
            # If no JSON, assume 204 is success
            if response.status_code == 204:
                print(f"[SUCCESS] Deleted: {object_key}")
                return True

        print(f"[FAILED] Failed to delete {object_key}: {response.status_code} - {response.text}")
        return False
    else:
        print(f"[FAILED] Failed to delete {object_key}: {response.status_code} - {response.text}")
        return False

def delete_all_objects():
    """Delete all objects in the bucket"""
    total_deleted = 0
    total_failed = 0
    cursor = None

    print(f"Starting deletion of all objects in bucket: {BUCKET_NAME}")
    print("=" * 80)

    while True:
        # List objects
        result = list_objects(cursor)

        if not result or not result.get("success"):
            print("Failed to list objects or no more objects")
            break

        objects = result.get("result", [])

        if not objects:
            print("No more objects to delete")
            break

        print(f"Found {len(objects)} objects in this batch")

        # Delete each object
        for obj in objects:
            object_key = obj["key"]

            if delete_object(object_key):
                total_deleted += 1
            else:
                total_failed += 1

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        # Check if there are more objects
        result_info = result.get("result_info", {})
        if not result_info.get("is_truncated", False):
            print("No more objects (not truncated)")
            break

        cursor = result_info.get("cursor")
        if not cursor:
            print("No cursor for next batch")
            break

        print(f"Moving to next batch (cursor: {cursor[:50]}...)")
        print("-" * 40)

    print("=" * 80)
    print(f"DELETION SUMMARY:")
    print(f"[SUCCESS] Successfully deleted: {total_deleted} objects")
    if total_failed > 0:
        print(f"[FAILED] Failed to delete: {total_failed} objects")
    else:
        print("[SUCCESS] Failed to delete: 0 objects")

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
            print("[SUCCESS] Bucket is completely empty!")
            return True
        else:
            print(f"[WARNING] Bucket still contains {len(objects)} objects:")
            for obj in objects[:5]:  # Show first 5
                print(f"  - {obj['key']}")
            if len(objects) > 5:
                print(f"  ... and {len(objects) - 5} more")
            return False
    else:
        print("[ERROR] Could not verify bucket status")
        return False

if __name__ == "__main__":
    try:
        # Delete all objects
        deleted, failed = delete_all_objects()

        # Verify bucket is empty
        is_empty = verify_empty()

        # Exit with appropriate code
        if failed == 0 and is_empty:
            print("\n[SUCCESS] All bucket contents deleted successfully!")
            sys.exit(0)
        else:
            print(f"\n[PARTIAL] PARTIAL SUCCESS: {deleted} deleted, {failed} failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Deletion process was stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)