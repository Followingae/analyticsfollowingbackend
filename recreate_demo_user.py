"""
Recreate Demo User with Correct Supabase ID
"""
import asyncio
import asyncpg
import uuid
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def recreate_demo_user():
    print("[START] RECREATING DEMO USER WITH CORRECT ID")
    print("=" * 50)
    
    # The correct Supabase user ID from JWT token
    supabase_user_id = "db8136b6-f8ee-4f1d-b964-ae90d73de7b0"
    old_db_user_id = "7d3e66b3-cf04-42e6-980e-4aa8ce662be6"
    email = "demo@prospectbrands.com"
    
    # Profile usernames to reconnect
    profile_usernames = ["lifestyle_emma", "fitness_ahmed", "food_maya"]
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Get profile IDs
        profile_ids = await conn.fetch("""
            SELECT id, username FROM profiles 
            WHERE username = ANY($1)
        """, profile_usernames)
        
        print(f"[FOUND] {len(profile_ids)} profiles to reconnect")
        
        # Delete existing user_profile_access records
        await conn.execute("""
            DELETE FROM user_profile_access 
            WHERE user_id = $1::uuid
        """, old_db_user_id)
        
        print(f"[DELETED] Old profile access records")
        
        # Delete existing user_searches records (user_id is VARCHAR in this table)
        await conn.execute("""
            DELETE FROM user_searches 
            WHERE user_id = $1
        """, str(old_db_user_id))
        
        print(f"[DELETED] Old search records")
        
        # Delete old user record
        await conn.execute("""
            DELETE FROM users 
            WHERE id = $1::uuid
        """, old_db_user_id)
        
        print(f"[DELETED] Old user record")
        
        # Create new user record with correct Supabase ID
        await conn.execute("""
            INSERT INTO users (
                id, email, hashed_password, role, credits, 
                full_name, status, supabase_user_id, last_login, created_at
            ) VALUES (
                $1::uuid, $2, 'supabase_managed', 'premium', 5000,
                'Sarah Marketing Manager', 'active', $3, NOW(), NOW()
            )
        """, supabase_user_id, email, supabase_user_id)
        
        print(f"[CREATED] New user record with ID: {supabase_user_id}")
        
        # Recreate profile access records
        access_created = 0
        for profile in profile_ids:
            profile_id = profile['id']
            username = profile['username']
            
            await conn.execute("""
                INSERT INTO user_profile_access (id, user_id, profile_id, last_accessed)
                VALUES ($1::uuid, $2::uuid, $3::uuid, NOW())
            """, str(uuid.uuid4()), supabase_user_id, profile_id)
            
            print(f"[CREATED] Access to {username}")
            access_created += 1
        
        # Create some sample search records
        sample_searches = [
            {"username": "lifestyle_emma", "term": "lifestyle influencer dubai"},
            {"username": "fitness_ahmed", "term": "fitness coach uae"},
            {"username": "food_maya", "term": "food blogger kuwait"}
        ]
        
        for search in sample_searches:
            await conn.execute("""
                INSERT INTO user_searches (
                    id, user_id, instagram_username, search_timestamp,
                    analysis_type, search_metadata
                ) VALUES (
                    $1, $2, $3, NOW() - INTERVAL '1 day',
                    'profile_analysis', $4::jsonb
                )
            """, str(uuid.uuid4()), str(supabase_user_id), search['username'],
                 '{"search_term": "' + search['term'] + '", "mock_data": true}')
        
        print(f"[CREATED] {len(sample_searches)} sample search records")
        
        # Verify everything
        user_check = await conn.fetchrow("""
            SELECT id, email, role, supabase_user_id FROM users 
            WHERE id = $1::uuid
        """, supabase_user_id)
        
        access_count = await conn.fetchval("""
            SELECT COUNT(*) FROM user_profile_access 
            WHERE user_id = $1::uuid
        """, supabase_user_id)
        
        search_count = await conn.fetchval("""
            SELECT COUNT(*) FROM user_searches 
            WHERE user_id = $1
        """, str(supabase_user_id))
        
        print(f"\n[VERIFICATION]")
        print(f"User ID: {user_check['id']}")
        print(f"Email: {user_check['email']}")
        print(f"Role: {user_check['role']}")
        print(f"Supabase ID: {user_check['supabase_user_id']}")
        print(f"Profile Access: {access_count} records")
        print(f"Search History: {search_count} records")
        
        print(f"\n[SUCCESS] Demo user recreated successfully!")
        print(f"Supabase ID matches Database ID: {user_check['id'] == user_check['supabase_user_id']}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(recreate_demo_user())