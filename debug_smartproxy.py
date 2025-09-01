#!/usr/bin/env python3
"""
Debug SmartProxy Configuration
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.config import settings

print("SmartProxy Configuration Debug")
print("-" * 40)
print(f"SmartProxy Username: {settings.SMARTPROXY_USERNAME}")
print(f"SmartProxy Password: {'*' * len(settings.SMARTPROXY_PASSWORD) if settings.SMARTPROXY_PASSWORD else 'NOT SET'}")
print(f"Use SmartProxy: {bool(settings.SMARTPROXY_USERNAME and settings.SMARTPROXY_PASSWORD)}")
print()

# Test Instagram URL detection
from app.services.image_transcoder_service import ImageTranscoderService
from app.infrastructure.r2_storage_client import R2StorageClient

r2_client = R2StorageClient(
    account_id=settings.CF_ACCOUNT_ID,
    access_key=settings.R2_ACCESS_KEY_ID,
    secret_key=settings.R2_SECRET_ACCESS_KEY,
    bucket_name=settings.R2_BUCKET_NAME
)

transcoder = ImageTranscoderService(r2_client)

test_url = "https://scontent-ist1-2.cdninstagram.com/v/t51.2885-15/test.jpg"
print(f"Test URL: {test_url}")
print(f"Is Instagram URL: {transcoder._is_instagram_url(test_url)}")
print(f"Has SmartProxy credentials: {transcoder.use_smartproxy}")
print()

if transcoder.use_smartproxy:
    print("SmartProxy should be used for Instagram URLs")
else:
    print("SmartProxy will NOT be used - missing credentials")