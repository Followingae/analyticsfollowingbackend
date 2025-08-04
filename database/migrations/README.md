# Database Security Migrations

This directory contains SQL migration files to implement Row Level Security (RLS) for the Analytics Following Backend.

## Migration Order

Run these files in Supabase SQL Editor in this exact order:

### 1. `enable_rls.sql` - Enable RLS on Tables
**REQUIRED** - Enables Row Level Security on all user-specific tables
- ✅ Secures user data (users, user_profiles, user_favorites, etc.)
- ✅ Secures campaign data (campaigns, campaign_posts, campaign_profiles)
- ✅ Leaves Instagram data tables public for sharing

### 2. `create_rls_policies.sql` - Create Security Policies  
**REQUIRED** - Creates policies that enforce data access rules
- ✅ Users can only access their own data
- ✅ Campaign data is restricted to campaign owners
- ✅ Proper user identification via auth.uid()

### 3. `optional_public_data_rls.sql` - Optional Instagram Data Security
**OPTIONAL** - Additional security for Instagram data tables
- 📋 Currently commented out (Instagram data remains public)
- 📋 Uncomment if you want to restrict Instagram profile/post access

### 4. `test_rls_policies.sql` - Test Security Implementation
**TESTING** - Verify RLS policies work correctly
- 🧪 Test queries for different user scenarios  
- 🧪 Cross-user access validation
- 🧪 Public data access verification

## Security Architecture

### 🔒 **Private Data** (RLS Enabled)
- `users` - User account data
- `user_profiles` - Extended user profiles  
- `user_favorites` - User's saved profiles
- `user_searches` - User search history
- `search_history` - Additional search tracking
- `user_profile_access` - 30-day access grants
- `campaigns` - User campaign management
- `campaign_posts` - Campaign-specific posts
- `campaign_profiles` - Campaign-specific profiles

### 🌍 **Public Data** (No RLS)
- `profiles` - Instagram profile data (shareable)
- `posts` - Instagram post data (shareable)
- `audience_demographics` - Profile audience analysis
- `creator_metadata` - Enhanced profile analytics
- `comment_sentiment` - Post sentiment analysis
- `mentions` - Profile mention tracking
- `related_profiles` - Profile suggestions

## How It Works

### User Authentication Flow
```
Browser Request → Supabase Auth → auth.uid() → RLS Policy Check → Data Access
```

### Policy Logic
```sql
-- Example: Users can only see their own favorites
CREATE POLICY "user_favorites_own_data" ON public.user_favorites
    FOR ALL USING (
        auth.uid() IN (
            SELECT u.id FROM auth.users u 
            JOIN public.users pu ON u.id::text = pu.supabase_user_id 
            WHERE pu.id = user_favorites.user_id
        )
    );
```

## Implementation Steps

### Step 1: Run Migrations in Supabase
1. Go to Supabase Dashboard → SQL Editor
2. Run `enable_rls.sql` 
3. Run `create_rls_policies.sql`
4. Optionally run `optional_public_data_rls.sql`

### Step 2: Test Implementation  
1. Create test users in Supabase Auth
2. Run queries from `test_rls_policies.sql`
3. Verify users can only access their own data

### Step 3: Update Backend Code
Ensure your FastAPI backend passes the authenticated user's JWT token to Supabase for all database operations.

## Troubleshooting

### Common Issues

**"Row level security is enabled but no policy exists"**
- Solution: Run `create_rls_policies.sql` to create the missing policies

**"Users can see other users' data"**  
- Check: Ensure `auth.uid()` is properly set in your requests
- Check: Verify the user's Supabase JWT token is being passed correctly

**"No data visible after enabling RLS"**
- Check: Confirm user is authenticated (`auth.uid()` returns a value)
- Check: Verify foreign key relationships in policies match your schema

**"Instagram data not accessible"**
- Check: Ensure Instagram data tables (profiles, posts) do NOT have RLS enabled
- Check: If you enabled RLS on them, create appropriate policies

## Security Benefits

✅ **Data Isolation** - Users can only access their own private data  
✅ **Campaign Privacy** - Campaign data is restricted to campaign owners  
✅ **Scalable Security** - Database enforces security at the row level  
✅ **Flexible Sharing** - Instagram data remains shareable across users  
✅ **Audit Trail** - All access is logged and traceable  

## Performance Notes

- RLS policies add minimal overhead to queries
- Consider indexing on `user_id` columns for better performance  
- Monitor query performance after implementation
- Use `EXPLAIN ANALYZE` to optimize policy queries if needed