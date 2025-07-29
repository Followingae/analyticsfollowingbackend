"""
Check what tables exist in Supabase database and create missing ones
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

def check_and_create_tables():
    """Check existing tables and create missing ones"""
    try:
        print("Connecting to Supabase...")
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # Check what tables exist
        print("\n1. Checking existing tables...")
        try:
            # Try to query existing tables
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
            
            result = supabase.rpc('exec_sql', {'sql': tables_query}).execute()
            print(f"Existing tables: {result.data}")
            
        except Exception as e:
            print(f"Could not query tables directly: {e}")
            
            # Try to check if users table exists by querying it
            try:
                users_result = supabase.table("users").select("*").limit(1).execute()
                print("users table exists and accessible")
            except Exception as users_error:
                print(f"users table does not exist: {users_error}")
                
            # Try user_searches table
            try:
                searches_result = supabase.table("user_searches").select("*").limit(1).execute()
                print("user_searches table exists and accessible")
            except Exception as searches_error:
                print(f"user_searches table does not exist: {searches_error}")
        
        # Create missing tables
        print("\n2. Creating missing tables...")
        
        # Create users table
        try:
            users_sql = """
            CREATE TABLE IF NOT EXISTS users (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                supabase_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'free',
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_login TIMESTAMP WITH TIME ZONE,
                profile_picture_url TEXT,
                preferences JSONB DEFAULT '{}'::jsonb
            );
            
            -- Create index on supabase_user_id for faster lookups
            CREATE INDEX IF NOT EXISTS idx_users_supabase_user_id ON users(supabase_user_id);
            """
            
            # Use RPC to execute SQL if available
            result = supabase.rpc('exec_sql', {'sql': users_sql}).execute()
            print("users table created successfully")
            
        except Exception as users_create_error:
            print(f"Could not create users table: {users_create_error}")
        
        # Create user_searches table
        try:
            searches_sql = """
            CREATE TABLE IF NOT EXISTS user_searches (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                instagram_username VARCHAR(255) NOT NULL,
                search_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                analysis_type VARCHAR(100) DEFAULT 'comprehensive',
                search_metadata JSONB DEFAULT '{}'::jsonb
            );
            
            -- Create indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_user_searches_user_id ON user_searches(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_searches_timestamp ON user_searches(search_timestamp DESC);
            """
            
            result = supabase.rpc('exec_sql', {'sql': searches_sql}).execute()
            print("user_searches table created successfully")
            
        except Exception as searches_create_error:
            print(f"Could not create user_searches table: {searches_create_error}")
        
        print("\n3. Testing table access...")
        
        # Test users table
        try:
            users_test = supabase.table("users").select("*").limit(1).execute()
            print(f"users table accessible - found {len(users_test.data)} records")
        except Exception as e:
            print(f"users table not accessible: {e}")
        
        # Test user_searches table
        try:
            searches_test = supabase.table("user_searches").select("*").limit(1).execute()
            print(f"user_searches table accessible - found {len(searches_test.data)} records")
        except Exception as e:
            print(f"user_searches table not accessible: {e}")
            
        return True
        
    except Exception as e:
        print(f"Database check failed: {e}")
        return False

if __name__ == "__main__":
    success = check_and_create_tables()
    if success:
        print("\nDatabase tables check completed!")
    else:
        print("\nDatabase tables check failed!")