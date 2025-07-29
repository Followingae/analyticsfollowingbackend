"""
Check User Profile Access Data
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def check_access():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Get current demo user
    user = await conn.fetchrow(
        "SELECT id, email FROM users WHERE email = $1",
        "demo@prospectbrands.com"
    )
    
    print(f"Demo User: {user['email']}")
    print(f"User ID: {user['id']}")
    print(f"User ID Type: {type(user['id'])}")
    
    # Check user profile access with exact user ID
    access_records = await conn.fetch("""
        SELECT upa.user_id, upa.profile_id, p.username, p.full_name
        FROM user_profile_access upa
        JOIN profiles p ON p.id = upa.profile_id
        WHERE upa.user_id = $1
    """, user['id'])
    
    print(f"\nFound {len(access_records)} access records:")
    for record in access_records:
        print(f"  - {record['username']} ({record['full_name']})")
        print(f"    User ID: {record['user_id']}")
        print(f"    Profile ID: {record['profile_id']}")
    
    # Check all access records for this email (in case of ID mismatch)
    all_users = await conn.fetch(
        "SELECT id FROM users WHERE email = $1",
        "demo@prospectbrands.com"
    )
    
    print(f"\nAll users with this email: {len(all_users)}")
    for u in all_users:
        print(f"  User ID: {u['id']}")
        
        access_for_user = await conn.fetch("""
            SELECT p.username FROM user_profile_access upa
            JOIN profiles p ON p.id = upa.profile_id
            WHERE upa.user_id = $1
        """, u['id'])
        
        print(f"    Access records: {len(access_for_user)}")
        for a in access_for_user:
            print(f"      - {a['username']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_access())