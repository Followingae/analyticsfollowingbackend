#!/usr/bin/env python3
"""
Fix user sync issue - sync missing users from auth.users to public.users
This fixes the foreign key violation error preventing cached data serving
"""
import asyncio
import asyncpg
import uuid
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def fix_user_sync():
    """Fix user sync issue by adding missing user to public.users"""
    print("=== FIXING USER SYNC ISSUE ===")
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # The problematic user ID from the error logs
    user_id = '99b1001b-69a0-4d75-9730-3177ba42c642'
    
    try:
        # Check if user exists in auth.users
        auth_user = await conn.fetchrow('SELECT id, email, created_at FROM auth.users WHERE id = $1', user_id)
        print(f"Auth user: {auth_user}")
        
        if not auth_user:
            print("ERROR: User not found in auth.users")
            return False
        
        # Check if user exists in public.users
        public_user = await conn.fetchrow('SELECT id FROM public.users WHERE id = $1 OR supabase_user_id = $2', user_id, user_id)
        print(f"Public user: {public_user}")
        
        if public_user:
            print("User already exists in public.users - sync not needed")
            return True
        
        # Create the user in public.users
        print("Creating user in public.users...")
        
        await conn.execute("""
            INSERT INTO public.users (
                id, supabase_user_id, email, full_name, role, status, 
                credits, credits_used_this_month, subscription_tier, preferences,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, 
                $7, $8, $9, $10,
                $11, $12
            )
        """, 
        user_id,  # id
        user_id,  # supabase_user_id  
        auth_user['email'],  # email
        auth_user['email'].split('@')[0],  # full_name (use email prefix)
        'premium',  # role
        'active',  # status
        5000,  # credits
        0,  # credits_used_this_month
        'professional',  # subscription_tier
        {},  # preferences (empty JSON)
        auth_user['created_at'] or datetime.now(timezone.utc),  # created_at
        datetime.now(timezone.utc)  # updated_at
        )
        
        print("✅ Successfully created user in public.users")
        
        # Verify the creation
        verify_user = await conn.fetchrow('SELECT id, email, role FROM public.users WHERE id = $1', user_id)
        print(f"Verified: {verify_user}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing user sync: {e}")
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(fix_user_sync())
    if success:
        print("\n🎯 User sync fixed! Database should serve cached data now.")
    else:
        print("\n❌ User sync fix failed.")