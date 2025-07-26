import asyncio
import logging
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.scrapers.smartproxy_client import SmartProxyClient, SmartProxyAPIError

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_smartproxy_connection():
    """Test SmartProxy API connection and response format"""
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        print("❌ SmartProxy credentials not configured in .env file")
        return
    
    print(f"🔑 Using credentials: {settings.SMARTPROXY_USERNAME[:5]}...")
    print(f"🌐 API URL: {settings.SMARTPROXY_BASE_URL}")
    
    try:
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            print("\n🧪 Testing Instagram profile API...")
            
            # Test with a simple username
            test_username = "instagram"
            print(f"Testing with username: {test_username}")
            
            response = await client.scrape_instagram_profile(test_username)
            
            print("✅ API call successful!")
            print(f"📋 Response type: {type(response)}")
            
            if isinstance(response, dict):
                print(f"📊 Response keys: {list(response.keys())}")
                
                # Log a sample of the response structure
                import json
                print("\n📄 Response sample (first 500 chars):")
                response_str = json.dumps(response, indent=2)[:500]
                print(response_str + "..." if len(response_str) == 500 else response_str)
                
            else:
                print(f"📄 Response content: {str(response)[:200]}...")
                
    except SmartProxyAPIError as e:
        print(f"❌ SmartProxy API Error: {e}")
    except Exception as e:
        logger.exception("Unexpected error during test")
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_smartproxy_connection())