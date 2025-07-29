"""
Fix Demo User Access to Existing Creators
Links the new demo user ID to existing influencer profiles
"""
import asyncio
import asyncpg
import logging
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DEMO_EMAIL = "demo@prospectbrands.com"

# Existing influencer usernames
INFLUENCER_USERNAMES = [
    "lifestyle_emma",
    "fitness_ahmed", 
    "food_maya"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_demo_user_access():
    """Fix demo user access to existing creators"""
    print("[START] FIXING DEMO USER ACCESS TO CREATORS")
    print("=" * 60)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Get current demo user ID
        user_row = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1",
            DEMO_EMAIL
        )
        
        if not user_row:
            print(f"[ERROR] Demo user not found: {DEMO_EMAIL}")
            return False
        
        user_id = user_row['id']
        print(f"[FOUND] Demo user ID: {user_id}")
        
        # Get existing creator profile IDs
        profile_rows = await conn.fetch(
            "SELECT id, username FROM profiles WHERE username = ANY($1)",
            INFLUENCER_USERNAMES
        )
        
        print(f"[FOUND] {len(profile_rows)} existing creator profiles")
        
        access_granted = 0
        
        for profile in profile_rows:
            profile_id = profile['id']
            username = profile['username']
            
            try:
                # Insert or update user access to this profile
                await conn.execute("""
                    INSERT INTO user_profile_access (id, user_id, profile_id, last_accessed)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, NOW())
                    ON CONFLICT (user_id, profile_id) DO UPDATE SET 
                        last_accessed = NOW()
                """, str(uuid.uuid4()), user_id, profile_id)
                
                print(f"[GRANTED] Access to {username}")
                access_granted += 1
                
            except Exception as e:
                print(f"[ERROR] Failed to grant access to {username}: {e}")
        
        await conn.close()
        
        print(f"\n[SUCCESS] Granted access to {access_granted} creators")
        print(f"[USER] {DEMO_EMAIL} can now access all demo creators!")
        
        return access_granted > 0
        
    except Exception as e:
        print(f"[ERROR] Failed to fix user access: {e}")
        return False

async def test_user_access():
    """Test that user now has access to creators"""
    print(f"\n[TEST] TESTING USER ACCESS TO CREATORS")
    print("-" * 40)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Get demo user ID
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            DEMO_EMAIL
        )
        
        # Get accessible profiles
        accessible_profiles = await conn.fetch("""
            SELECT p.username, p.full_name, p.followers_count, upa.last_accessed
            FROM user_profile_access upa
            JOIN profiles p ON p.id = upa.profile_id
            WHERE upa.user_id = $1
            ORDER BY upa.last_accessed DESC
        """, user_id)
        
        print(f"[ACCESSIBLE] {len(accessible_profiles)} creators unlocked:")
        
        for profile in accessible_profiles:
            print(f"  - {profile['username']} ({profile['full_name']})")
            print(f"    {profile['followers_count']:,} followers")
            print(f"    Last accessed: {profile['last_accessed']}")
        
        await conn.close()
        
        return len(accessible_profiles) > 0
        
    except Exception as e:
        print(f"[ERROR] Failed to test access: {e}")
        return False

async def main():
    """Fix demo user access and test"""
    success = await fix_demo_user_access()
    
    if success:
        await test_user_access()
        
        print(f"\n" + "=" * 60)
        print("[COMPLETE] DEMO USER ACCESS FIXED!")
        print("=" * 60)
        print(f"Demo User: {DEMO_EMAIL}")
        print(f"Password: ProspectDemo2024!")
        print("The user now has access to all demo creators!")
    else:
        print(f"\n[FAILED] Could not fix demo user access")

if __name__ == "__main__":
    asyncio.run(main())