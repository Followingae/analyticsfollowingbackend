"""
Analyze raw_data JSONB fields to identify unmapped data
"""
import asyncio
import asyncpg
import json
from typing import Dict, Any, Set, List
from app.core.config import settings

async def analyze_raw_data():
    """Analyze raw_data fields in profiles and posts tables to find unmapped data"""
    
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        print("=== ANALYZING PROFILE RAW_DATA ===")
        
        # Get profile raw_data
        profiles = await conn.fetch("""
            SELECT username, raw_data 
            FROM profiles 
            WHERE raw_data IS NOT NULL 
            LIMIT 5
        """)
        
        all_profile_keys = set()
        profile_examples = {}
        
        for profile in profiles:
            username = profile['username']
            raw_data = profile['raw_data']
            
            if raw_data and isinstance(raw_data, dict):
                # Extract all keys from nested structure
                keys = extract_all_keys(raw_data)
                all_profile_keys.update(keys)
                profile_examples[username] = keys
                
                print(f"\n--- Profile: {username} ---")
                print(f"Raw data structure keys: {len(keys)}")
                
                # Show sample of deep keys
                sample_keys = list(keys)[:20]
                for key in sample_keys:
                    print(f"  {key}")
                
                if len(keys) > 20:
                    print(f"  ... and {len(keys) - 20} more keys")
        
        print(f"\n=== PROFILE RAW_DATA SUMMARY ===")
        print(f"Total unique keys across all profiles: {len(all_profile_keys)}")
        
        # Check what columns exist in profiles table
        profile_columns = await get_table_columns(conn, 'profiles')
        print(f"Existing profile columns: {len(profile_columns)}")
        
        # Find potentially unmapped keys
        unmapped_profile_keys = find_potentially_unmapped_keys(all_profile_keys, profile_columns)
        print(f"\nPotentially unmapped profile keys: {len(unmapped_profile_keys)}")
        
        for key in sorted(unmapped_profile_keys)[:30]:  # Show first 30
            print(f"  {key}")
        
        print("\n=== ANALYZING POST RAW_DATA ===")
        
        # Get post raw_data
        posts = await conn.fetch("""
            SELECT shortcode, raw_data 
            FROM posts 
            WHERE raw_data IS NOT NULL 
            LIMIT 5
        """)
        
        all_post_keys = set()
        post_examples = {}
        
        for post in posts:
            shortcode = post['shortcode']
            raw_data = post['raw_data']
            
            if raw_data and isinstance(raw_data, dict):
                keys = extract_all_keys(raw_data)
                all_post_keys.update(keys)
                post_examples[shortcode] = keys
                
                print(f"\n--- Post: {shortcode} ---")
                print(f"Raw data structure keys: {len(keys)}")
                
                # Show sample of deep keys
                sample_keys = list(keys)[:20]
                for key in sample_keys:
                    print(f"  {key}")
                
                if len(keys) > 20:
                    print(f"  ... and {len(keys) - 20} more keys")
        
        print(f"\n=== POST RAW_DATA SUMMARY ===")
        print(f"Total unique keys across all posts: {len(all_post_keys)}")
        
        # Check post columns
        post_columns = await get_table_columns(conn, 'posts')
        print(f"Existing post columns: {len(post_columns)}")
        
        # Find potentially unmapped keys
        unmapped_post_keys = find_potentially_unmapped_keys(all_post_keys, post_columns)
        print(f"\nPotentially unmapped post keys: {len(unmapped_post_keys)}")
        
        for key in sorted(unmapped_post_keys)[:30]:  # Show first 30
            print(f"  {key}")
        
        # Save detailed analysis to files
        analysis_data = {
            'profile_analysis': {
                'total_keys': len(all_profile_keys),
                'all_keys': sorted(list(all_profile_keys)),
                'existing_columns': profile_columns,
                'unmapped_keys': sorted(list(unmapped_profile_keys)),
                'examples_by_profile': profile_examples
            },
            'post_analysis': {
                'total_keys': len(all_post_keys),
                'all_keys': sorted(list(all_post_keys)),
                'existing_columns': post_columns,
                'unmapped_keys': sorted(list(unmapped_post_keys)),
                'examples_by_post': post_examples
            }
        }
        
        with open('raw_data_analysis.json', 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        print(f"\nDetailed analysis saved to: raw_data_analysis.json")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error analyzing raw data: {e}")
        import traceback
        traceback.print_exc()

def extract_all_keys(data: Any, parent_key: str = "") -> Set[str]:
    """Recursively extract all keys from nested dict/list structure"""
    keys = set()
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_key = f"{parent_key}.{key}" if parent_key else key
            keys.add(current_key)
            
            # Recurse into nested structures
            nested_keys = extract_all_keys(value, current_key)
            keys.update(nested_keys)
            
    elif isinstance(data, list) and data:
        # For lists, analyze the first item to understand structure
        current_key = f"{parent_key}[0]" if parent_key else "[0]"
        nested_keys = extract_all_keys(data[0], current_key)
        keys.update(nested_keys)
    
    return keys

async def get_table_columns(conn, table_name: str) -> List[str]:
    """Get column names from a table"""
    columns = await conn.fetch("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = $1 AND table_schema = 'public'
    """, table_name)
    
    return [col['column_name'] for col in columns]

def find_potentially_unmapped_keys(raw_keys: Set[str], existing_columns: List[str]) -> Set[str]:
    """Find raw_data keys that might not be mapped to existing columns"""
    unmapped = set()
    
    # Convert column names to lowercase for comparison
    columns_lower = [col.lower() for col in existing_columns]
    
    for key in raw_keys:
        # Clean the key (remove array indices, convert to snake_case-like)
        clean_key = key.lower().replace('[0]', '').replace('.', '_')
        
        # Skip obviously internal/metadata keys
        if any(skip in clean_key for skip in ['__', 'typename', 'id', '_id']):
            continue
        
        # Check if key might correspond to existing column
        key_mapped = False
        for col in columns_lower:
            if clean_key in col or col in clean_key:
                key_mapped = True
                break
        
        if not key_mapped:
            unmapped.add(key)
    
    return unmapped

if __name__ == '__main__':
    asyncio.run(analyze_raw_data())