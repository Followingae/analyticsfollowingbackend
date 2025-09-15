#!/usr/bin/env python3
"""
Start MCP CDN Worker - Worker with real Cloudflare R2 MCP integration
"""
import sys

def start_mcp_cdn_worker():
    print("Starting MCP CDN Worker...")
    print("+ Real Cloudflare R2 upload via MCP")
    print("+ Correct database schema")
    print("+ Processes queued jobs")
    print()

    try:
        from app.workers.mcp_cdn_worker import celery_app

        # FIXED: Proper worker startup without problematic config
        celery_app.worker_main([
            'worker',
            '--loglevel=info',
            '--concurrency=2',
            '--queues=cdn_processing',
            '--hostname=mcp-cdn-worker@%h',
            '--pool=prefork'
        ])

    except KeyboardInterrupt:
        print("MCP CDN Worker stopped")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(start_mcp_cdn_worker())