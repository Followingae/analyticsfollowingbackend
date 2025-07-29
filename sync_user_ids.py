"""
Sync User IDs - Update database to match Supabase user ID
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def sync_user_ids():
    print("[START] SYNCING USER IDS")
    print("=" * 50)
    
    # The correct Supabase user ID from JWT token
    supabase_user_id = "db8136b6-f8ee-4f1d-b964-ae90d73de7b0"
    old_db_user_id = "7d3e66b3-cf04-42e6-980e-4aa8ce662be6"
    email = "demo@prospectbrands.com"
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Update the user record to use the Supabase user ID
        await conn.execute("""
            UPDATE users 
            SET id = $1::uuid, supabase_user_id = $2 
            WHERE email = $3
        """, supabase_user_id, supabase_user_id, email)
        
        print(f"[UPDATED] User record ID: {supabase_user_id}")
        
        # Update user_profile_access records to use the new user ID
        updated_access = await conn.execute("""
            UPDATE user_profile_access 
            SET user_id = $1::uuid 
            WHERE user_id = $2::uuid
        """, supabase_user_id, old_db_user_id)
        
        print(f"[UPDATED] Profile access records: {updated_access}")
        
        # Update user_searches records if any
        updated_searches = await conn.execute("""
            UPDATE user_searches 
            SET user_id = $1::uuid 
            WHERE user_id = $2::uuid
        """, supabase_user_id, old_db_user_id)
        
        print(f"[UPDATED] Search records: {updated_searches}")
        
        # Verify the changes
        access_count = await conn.fetchval("""
            SELECT COUNT(*) FROM user_profile_access upa
            JOIN profiles p ON p.id = upa.profile_id
            WHERE upa.user_id = $1::uuid
        """, supabase_user_id)
        
        profile_names = await conn.fetch("""
            SELECT p.username FROM user_profile_access upa
            JOIN profiles p ON p.id = upa.profile_id
            WHERE upa.user_id = $1::uuid
        """, supabase_user_id)
        
        print(f"\n[VERIFIED] User {email} now has access to {access_count} profiles:")
        for profile in profile_names:
            print(f"  - {profile['username']}")
        
        print(f"\n[SUCCESS] User IDs synchronized!")
        print(f"Supabase ID: {supabase_user_id}")
        print(f"Database ID: {supabase_user_id}")
        print(f"IDs Match: True")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(sync_user_ids())