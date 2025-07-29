import asyncio
import json
import logging
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.scrapers.smartproxy_client import SmartProxyClient, SmartProxyAPIError

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_decodo_comprehensive():
    """Test Decodo API comprehensively with mkbhd to analyze all available data points"""
    
    print("Testing Decodo API with mkbhd...")
    print("=" * 60)
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        print("SmartProxy credentials not configured!")
        return
    
    try:
        async with SmartProxyClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            
            print("Testing Instagram GraphQL Profile...")
            profile_response = await client.scrape_instagram_profile("mkbhd")
            
            print("\nFULL DECODO RESPONSE ANALYSIS:")
            print("=" * 60)
            print(f"Response Type: {type(profile_response)}")
            print(f"Response Keys: {list(profile_response.keys()) if isinstance(profile_response, dict) else 'Not a dict'}")
            
            # Save full response to file for analysis
            with open('decodo_mkbhd_response.json', 'w') as f:
                json.dump(profile_response, f, indent=2, default=str)
            
            print(f"\nFull response saved to 'decodo_mkbhd_response.json'")
            
            # Analyze response structure
            if isinstance(profile_response, dict):
                print("\nRESPONSE STRUCTURE ANALYSIS:")
                print("=" * 60)
                
                def analyze_nested_dict(data, prefix="", level=0):
                    indent = "  " * level
                    for key, value in data.items():
                        key_path = f"{prefix}.{key}" if prefix else key
                        value_type = type(value).__name__
                        
                        if isinstance(value, dict):
                            print(f"{indent}{key} ({value_type}) -> {len(value)} keys")
                            if level < 3:  # Limit depth to avoid too much output
                                analyze_nested_dict(value, key_path, level + 1)
                        elif isinstance(value, list):
                            list_length = len(value)
                            print(f"{indent}{key} ({value_type}) -> {list_length} items")
                            if list_length > 0 and isinstance(value[0], dict):
                                print(f"{indent}  First item keys: {list(value[0].keys())}")
                        else:
                            # Truncate long values for readability
                            display_value = str(value)
                            if len(display_value) > 100:
                                display_value = display_value[:100] + "..."
                            print(f"{indent}{key} ({value_type}): {display_value}")
                
                analyze_nested_dict(profile_response)
                
                # Look for specific Instagram data points
                print("\nINSTAGRAM DATA POINTS FOUND:")
                print("=" * 60)
                
                # Common Instagram fields to look for
                instagram_fields = [
                    'username', 'full_name', 'biography', 'bio', 'followers', 'following',
                    'posts_count', 'media_count', 'is_verified', 'verified', 'is_private', 'private',
                    'profile_pic_url', 'profile_pic_url_hd', 'external_url', 'website',
                    'edge_followed_by', 'edge_follow', 'edge_owner_to_timeline_media',
                    'business_category_name', 'category_name', 'should_show_category',
                    'highlight_reel_count', 'has_ar_effects', 'has_clips', 'has_guides',
                    'has_channel', 'has_blocked_viewer', 'blocked_by_viewer',
                    'country_block', 'restricted_by_viewer', 'follows_viewer',
                    'followed_by_viewer', 'requested_by_viewer', 'has_requested_viewer'
                ]
                
                def find_fields_recursive(data, fields_to_find, current_path=""):
                    found_fields = {}
                    
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_key_path = f"{current_path}.{key}" if current_path else key
                            
                            if key in fields_to_find:
                                found_fields[current_key_path] = {
                                    'value': value,
                                    'type': type(value).__name__
                                }
                            
                            # Recursively search nested dictionaries
                            if isinstance(value, dict):
                                nested_fields = find_fields_recursive(value, fields_to_find, current_key_path)
                                found_fields.update(nested_fields)
                            elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                for i, item in enumerate(value[:3]):  # Check first 3 items
                                    nested_fields = find_fields_recursive(item, fields_to_find, f"{current_key_path}[{i}]")
                                    found_fields.update(nested_fields)
                    
                    return found_fields
                
                found_instagram_fields = find_fields_recursive(profile_response, instagram_fields)
                
                if found_instagram_fields:
                    for field_path, field_info in found_instagram_fields.items():
                        value_display = str(field_info['value'])
                        if len(value_display) > 200:
                            value_display = value_display[:200] + "..."
                        print(f"FOUND: {field_path} ({field_info['type']}): {value_display}")
                else:
                    print("No standard Instagram fields found")
                
                # Check for error messages
                print("\nERROR ANALYSIS:")
                print("=" * 60)
                
                error_fields = ['error', 'errors', 'message', 'status', 'status_code', 'detail']
                found_errors = find_fields_recursive(profile_response, error_fields)
                
                if found_errors:
                    for error_path, error_info in found_errors.items():
                        print(f"ERROR: {error_path}: {error_info['value']}")
                else:
                    print("No error fields detected")
            
            print(f"\nTest completed successfully!")
            print(f"Check 'decodo_mkbhd_response.json' for full response details")
            
    except SmartProxyAPIError as e:
        print(f"SmartProxy API Error: {str(e)}")
        logger.error(f"SmartProxy API error during comprehensive test: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error during comprehensive test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_decodo_comprehensive())