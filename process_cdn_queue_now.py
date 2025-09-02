#!/usr/bin/env python3
"""
Process all queued CDN jobs immediately
"""
import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def process_cdn_queue():
    """Process all queued CDN jobs"""
    try:
        print("Starting CDN queue processing...")
        
        # Import services
        from app.services.cdn_queue_manager import cdn_queue_manager
        from app.services.image_transcoder_service import initialize_transcoder_service
        from app.infrastructure.r2_storage_client import initialize_r2_client
        
        # Initialize services
        initialize_r2_client()
        initialize_transcoder_service()
        
        print("Services initialized, processing queue...")
        result = await cdn_queue_manager.process_queue()
        
        print(f"Queue processing completed: {result}")
        return result
        
    except Exception as e:
        print(f"Error processing CDN queue: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(process_cdn_queue())
    print(f"Final result: {result}")