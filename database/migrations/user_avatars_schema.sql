-- =====================================================================
-- USER AVATARS SCHEMA MIGRATION
-- Adds user avatar upload functionality with Supabase storage integration
-- =====================================================================

-- Add avatar_url column to existing users table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'avatar_url'
    ) THEN
        ALTER TABLE public.users ADD COLUMN avatar_url TEXT NULL;
    END IF;
END $$;

-- Create user_avatars table for tracking uploaded avatars
CREATE TABLE IF NOT EXISTS public.user_avatars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    original_filename TEXT,
    processed_size TEXT, -- e.g., "400x400"
    
    CONSTRAINT unique_active_avatar_per_user 
    UNIQUE (user_id, is_active) 
    DEFERRABLE INITIALLY DEFERRED
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_avatars_user_id ON public.user_avatars(user_id);
CREATE INDEX IF NOT EXISTS idx_user_avatars_active ON public.user_avatars(user_id, is_active) WHERE is_active = true;

-- Enable RLS on user_avatars table
ALTER TABLE public.user_avatars ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own avatars" ON public.user_avatars;
DROP POLICY IF EXISTS "Users can insert their own avatars" ON public.user_avatars;
DROP POLICY IF EXISTS "Users can update their own avatars" ON public.user_avatars;
DROP POLICY IF EXISTS "Users can delete their own avatars" ON public.user_avatars;
DROP POLICY IF EXISTS "Service role can manage all avatars" ON public.user_avatars;

-- Create RLS policies for user_avatars
CREATE POLICY "Users can view their own avatars" ON public.user_avatars
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own avatars" ON public.user_avatars
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own avatars" ON public.user_avatars
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own avatars" ON public.user_avatars
    FOR DELETE USING (auth.uid() = user_id);

-- Allow service role to manage all avatars (for backend operations)
CREATE POLICY "Service role can manage all avatars" ON public.user_avatars
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for updated_at on user_avatars
DROP TRIGGER IF EXISTS update_user_avatars_updated_at ON public.user_avatars;
CREATE TRIGGER update_user_avatars_updated_at
    BEFORE UPDATE ON public.user_avatars
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create function to get user's current avatar URL
CREATE OR REPLACE FUNCTION get_user_avatar_url(target_user_id UUID)
RETURNS TEXT AS $$
DECLARE
    avatar_path TEXT;
    base_url TEXT := 'https://your-supabase-project.supabase.co/storage/v1/object/public/avatars/';
BEGIN
    SELECT file_path INTO avatar_path
    FROM public.user_avatars
    WHERE user_id = target_user_id AND is_active = true
    ORDER BY uploaded_at DESC
    LIMIT 1;
    
    IF avatar_path IS NOT NULL THEN
        RETURN base_url || avatar_path;
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON public.user_avatars TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_avatar_url(UUID) TO authenticated;

-- Add comment for documentation
COMMENT ON TABLE public.user_avatars IS 'Stores user uploaded avatar metadata with Supabase storage integration';
COMMENT ON COLUMN public.user_avatars.file_path IS 'Path to avatar file in Supabase storage bucket';
COMMENT ON COLUMN public.user_avatars.is_active IS 'Only one active avatar per user allowed';
COMMENT ON FUNCTION get_user_avatar_url(UUID) IS 'Returns full public URL for users active avatar';

-- Migration complete
SELECT 'User avatars schema migration completed successfully' as status;