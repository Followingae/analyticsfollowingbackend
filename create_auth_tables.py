"""
Create authentication tables in Supabase
"""
import asyncio
import asyncpg
from app.core.config import settings


async def create_auth_tables():
    """
    Create users and user_searches tables for authentication system
    """
    print("Creating authentication tables...")
    
    try:
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
        
        async with pool.acquire() as conn:
            
            print("Step 1: Creating users table...")
            
            # Create users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    supabase_user_id VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255),
                    role VARCHAR(20) DEFAULT 'free' CHECK (role IN ('free', 'premium', 'admin')),
                    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'pending')),
                    profile_picture_url TEXT,
                    preferences JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_login TIMESTAMP WITH TIME ZONE
                )
            """)
            
            # Create indexes for users table
            try:
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_supabase_id ON users(supabase_user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            except Exception as e:
                print(f"Warning: Failed to create some indexes: {e}")
            
            print("✓ Users table created")
            
            print("Step 2: Creating user_searches table...")
            
            # Create user_searches table for tracking user activity
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_searches (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    instagram_username VARCHAR(255) NOT NULL,
                    search_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    analysis_type VARCHAR(50) NOT NULL,
                    search_metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indexes for user_searches table
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_searches_user_id ON user_searches(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_searches_username ON user_searches(instagram_username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_searches_timestamp ON user_searches(search_timestamp)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_searches_type ON user_searches(analysis_type)")
            
            print("✓ User searches table created")
            
            print("Step 3: Creating user_favorites table...")
            
            # Create user_favorites table for favorite profiles
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    instagram_username VARCHAR(255) NOT NULL,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    notes TEXT,
                    UNIQUE(user_id, instagram_username)
                )
            """)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_username ON user_favorites(instagram_username)")
            
            print("✓ User favorites table created")
            
            print("Step 4: Creating api_keys table...")
            
            # Create api_keys table for programmatic access
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key_name VARCHAR(255) NOT NULL,
                    api_key VARCHAR(255) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_used TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    permissions JSONB DEFAULT '{}',
                    usage_count INTEGER DEFAULT 0
                )
            """)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
            
            print("✓ API keys table created")
            
            print("Step 5: Creating user_sessions table...")
            
            # Create user_sessions table for session management
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    refresh_token VARCHAR(255) UNIQUE,
                    ip_address INET,
                    user_agent TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active)")
            
            print("✓ User sessions table created")
            
            print("Step 6: Creating updated_at trigger...")
            
            # Create function to update updated_at timestamp
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            # Create trigger for users table
            await conn.execute("""
                DROP TRIGGER IF EXISTS update_users_updated_at ON users;
                CREATE TRIGGER update_users_updated_at
                    BEFORE UPDATE ON users
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """)
            
            print("✓ Database triggers created")
            
            # Verify table creation
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('users', 'user_searches', 'user_favorites', 'api_keys', 'user_sessions')
                ORDER BY table_name
            """)
            
            table_names = [t['table_name'] for t in tables]
            print(f"\n✅ Authentication tables created: {', '.join(table_names)}")
            
            # Check users table columns
            users_columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position
            """)
            print(f"Users table has {len(users_columns)} columns")
            
            print("\nAuthentication system database setup complete!")
            print("\nNext steps:")
            print("1. Install new dependencies: pip install -r requirements.txt")
            print("2. Add JWT_SECRET_KEY to your .env file")
            print("3. Test authentication endpoints")
            
        await pool.close()
        
    except Exception as e:
        print(f"Failed to create authentication tables: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_auth_tables())