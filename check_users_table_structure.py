"""
Check the actual users table structure in Supabase
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

async def check_table_structure():
    """Check users table structure"""
    try:
        print("CHECKING USERS TABLE STRUCTURE")
        print("=" * 40)
        
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Try to get one record to see structure
        try:
            result = supabase.table("users").select("*").limit(1).execute()
            if result.data:
                print("[SUCCESS] Users table exists with columns:")
                for key in result.data[0].keys():
                    print(f"  - {key}")
            else:
                print("[INFO] Users table exists but is empty")
                
                # Try to insert a test record to see what columns are expected
                print("\n[TEST] Trying to insert test record to see required columns...")
                test_record = {
                    "id": "test-id",
                    "email": "test@test.com"
                }
                
                try:
                    insert_result = supabase.table("users").insert(test_record).execute()
                except Exception as insert_error:
                    error_msg = str(insert_error)
                    print(f"[ERROR] Insert failed: {error_msg}")
                    
                    if "column" in error_msg and "does not exist" in error_msg:
                        print("[INFO] This tells us what columns exist")
                    
        except Exception as e:
            print(f"[ERROR] Cannot access users table: {e}")
        
        # Check if we need to create the table
        print("\n[CHECK] Checking if users table needs to be created...")
        
        # Based on your models, the users table should have these columns:
        expected_columns = [
            "id", "email", "hashed_password", "role", "credits", "created_at"
        ]
        
        print("Expected columns from models.py:")
        for col in expected_columns:
            print(f"  - {col}")
            
    except Exception as e:
        print(f"[ERROR] Table structure check failed: {e}")

async def create_simple_user_record():
    """Create user record with simple structure"""
    try:
        print("\n[CREATE] Attempting to create user record with basic structure...")
        
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Based on your original models.py structure
        user_record = {
            "id": "743cb2c4-4015-4842-a595-6f07eab10134",  # Use the Auth user ID directly
            "email": "zzain.ali@outlook.com",
            "hashed_password": "dummy_hash",  # Not used since we use Supabase Auth
            "role": "user",
            "credits": 100
        }
        
        result = supabase.table("users").insert(user_record).execute()
        
        if result.data:
            print("[SUCCESS] User record created!")
            print(f"Created user: {result.data[0]}")
            return True
        else:
            print("[ERROR] User creation failed")
            return False
            
    except Exception as e:
        print(f"[ERROR] User creation failed: {e}")
        
        # Try with minimal structure
        try:
            print("[RETRY] Trying with minimal structure...")
            minimal_record = {
                "id": "743cb2c4-4015-4842-a595-6f07eab10134",
                "email": "zzain.ali@outlook.com"
            }
            
            result = supabase.table("users").insert(minimal_record).execute()
            if result.data:
                print("[SUCCESS] Minimal user record created!")
                return True
                
        except Exception as retry_error:
            print(f"[ERROR] Minimal creation also failed: {retry_error}")
        
        return False

async def main():
    """Main function"""
    await check_table_structure()
    await create_simple_user_record()

if __name__ == "__main__":
    asyncio.run(main())