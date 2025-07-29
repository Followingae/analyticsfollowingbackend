"""
Show all datapoints fetched for kyliejenner from Decodo
"""
import asyncio
import json
from app.database.postgres_direct import postgres_direct


async def show_kyliejenner_data():
    """Display all datapoints for kyliejenner from Decodo"""
    try:
        print("Connecting to database...")
        await postgres_direct.init()
        
        print("Fetching kyliejenner data...")
        profile_data = await postgres_direct.get_profile('kyliejenner')
        
        if not profile_data:
            print("No data found for kyliejenner in database")
            return
        
        print("\n" + "="*60)
        print("KYLIEJENNER - ALL DECODO DATAPOINTS")
        print("="*60)
        
        # Basic profile info
        print(f"Username: {profile_data.get('username', 'N/A')}")
        print(f"Full Name: {profile_data.get('full_name', 'N/A')}")
        print(f"Instagram ID: {profile_data.get('instagram_user_id', 'N/A')}")
        print(f"Followers: {profile_data.get('followers_count', 0):,}")
        print(f"Following: {profile_data.get('following_count', 0):,}")
        print(f"Posts: {profile_data.get('posts_count', 0):,}")
        print(f"Verified: {profile_data.get('is_verified', False)}")
        print(f"Private: {profile_data.get('is_private', False)}")
        print(f"Last Updated: {profile_data.get('last_refreshed', 'N/A')}")
        
        print(f"\n" + "-"*60)
        print("ALL STORED DATAPOINTS FROM DECODO")
        print("-"*60)
        
        # Show all populated fields
        populated_fields = []
        for key, value in profile_data.items():
            if value is not None and value != "" and value != 0 and value != {}:
                populated_fields.append((key, value))
        
        for i, (key, value) in enumerate(populated_fields, 1):
            if isinstance(value, str) and len(value) > 100:
                display_value = value[:100] + "..."
            elif isinstance(value, dict):
                display_value = f"Dict with {len(value)} keys"
            elif isinstance(value, list):
                display_value = f"List with {len(value)} items"
            else:
                display_value = value
            
            print(f"{i:2d}. {key}: {display_value}")
        
        print(f"\nTotal populated datapoints: {len(populated_fields)}")
        
        # Show raw Decodo data structure
        raw_data = profile_data.get('raw_data')
        if raw_data:
            print(f"\n" + "-"*60)
            print("RAW DECODO API RESPONSE STRUCTURE")
            print("-"*60)
            
            try:
                if isinstance(raw_data, str):
                    raw_json = json.loads(raw_data)
                else:
                    raw_json = raw_data
                
                print(f"Response type: {type(raw_json).__name__}")
                
                if isinstance(raw_json, dict):
                    print(f"Top-level keys: {list(raw_json.keys())}")
                    
                    # Navigate to the user data in Decodo structure
                    if 'results' in raw_json and raw_json['results']:
                        result = raw_json['results'][0]
                        print(f"First result keys: {list(result.keys())}")
                        
                        if 'content' in result:
                            content = result['content']
                            print(f"Content keys: {list(content.keys())}")
                            
                            if 'data' in content:
                                data = content['data']
                                print(f"Data keys: {list(data.keys())}")
                                
                                if 'user' in data:
                                    user_data = data['user']
                                    print(f"\nUSER DATA FROM DECODO:")
                                    print(f"Total user fields: {len(user_data)}")
                                    
                                    # Show all user data fields
                                    print(f"\nAll user data fields:")
                                    for i, key in enumerate(sorted(user_data.keys()), 1):
                                        value = user_data[key]
                                        if isinstance(value, dict):
                                            if 'count' in value:  # Edge objects with counts
                                                display_val = f"Edge object (count: {value['count']:,})"
                                            else:
                                                display_val = f"Dict with {len(value)} keys"
                                        elif isinstance(value, list):
                                            display_val = f"List with {len(value)} items"
                                        elif isinstance(value, str) and len(value) > 50:
                                            display_val = value[:50] + "..."
                                        else:
                                            display_val = value
                                        
                                        print(f"{i:2d}. {key}: {display_val}")
                                    
                                    # Show specific important metrics
                                    print(f"\nKEY METRICS:")
                                    metrics = {
                                        'edge_followed_by': 'Followers',
                                        'edge_follow': 'Following', 
                                        'edge_owner_to_timeline_media': 'Posts',
                                        'edge_mutual_followed_by': 'Mutual Followers'
                                    }
                                    
                                    for field, label in metrics.items():
                                        if field in user_data and isinstance(user_data[field], dict):
                                            count = user_data[field].get('count', 0)
                                            print(f"{label}: {count:,}")
                
            except json.JSONDecodeError as e:
                print(f"Error parsing raw data as JSON: {e}")
        else:
            print("\nNo raw data available")
            
    except Exception as e:
        print(f"Error retrieving data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(show_kyliejenner_data())