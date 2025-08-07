-- Migration: Add My Lists Module Tables
-- Description: Create user_lists and user_list_items tables for organizing unlocked creators into custom lists
-- Dependencies: Requires existing users and profiles tables

-- Create user_lists table
CREATE TABLE IF NOT EXISTS public.user_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    
    -- List metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#3B82F6', -- Hex color for UI customization
    icon VARCHAR(50) DEFAULT 'list', -- Icon identifier for UI
    
    -- List settings
    is_public BOOLEAN NOT NULL DEFAULT FALSE, -- Future: allow public list sharing
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE, -- Mark important lists
    sort_order INTEGER DEFAULT 0, -- User-defined list ordering
    
    -- List statistics (computed)
    items_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT user_lists_name_not_empty CHECK (LENGTH(TRIM(name)) > 0),
    CONSTRAINT user_lists_color_valid CHECK (color ~ '^#[0-9A-Fa-f]{6}$')
);

-- Create user_list_items table (junction table)
CREATE TABLE IF NOT EXISTS public.user_list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES public.user_lists(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE, -- Denormalized for RLS
    
    -- Item metadata
    position INTEGER NOT NULL DEFAULT 0, -- Order within the list
    notes TEXT, -- User notes for this profile in this list
    tags TEXT[], -- User-defined tags for this item
    
    -- Item settings
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE, -- Pin to top of list
    color_label VARCHAR(7), -- Optional color label for this item
    
    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(list_id, profile_id), -- Prevent duplicate profiles in same list
    CONSTRAINT user_list_items_position_non_negative CHECK (position >= 0)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_lists_user_id ON public.user_lists(user_id);
CREATE INDEX IF NOT EXISTS idx_user_lists_created_at ON public.user_lists(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_lists_updated ON public.user_lists(last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_user_lists_public ON public.user_lists(is_public) WHERE is_public = true;

CREATE INDEX IF NOT EXISTS idx_user_list_items_list_id ON public.user_list_items(list_id);
CREATE INDEX IF NOT EXISTS idx_user_list_items_profile_id ON public.user_list_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_user_list_items_user_id ON public.user_list_items(user_id);
CREATE INDEX IF NOT EXISTS idx_user_list_items_position ON public.user_list_items(list_id, position);
CREATE INDEX IF NOT EXISTS idx_user_list_items_added_at ON public.user_list_items(added_at DESC);

-- Enable Row Level Security
ALTER TABLE public.user_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_list_items ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist, then recreate them
DO $$ 
BEGIN
    -- Drop existing policies for user_lists
    DROP POLICY IF EXISTS "Users can view their own lists" ON public.user_lists;
    DROP POLICY IF EXISTS "Users can insert their own lists" ON public.user_lists;
    DROP POLICY IF EXISTS "Users can update their own lists" ON public.user_lists;
    DROP POLICY IF EXISTS "Users can delete their own lists" ON public.user_lists;
    
    -- Drop existing policies for user_list_items
    DROP POLICY IF EXISTS "Users can view their own list items" ON public.user_list_items;
    DROP POLICY IF EXISTS "Users can insert their own list items" ON public.user_list_items;
    DROP POLICY IF EXISTS "Users can update their own list items" ON public.user_list_items;
    DROP POLICY IF EXISTS "Users can delete their own list items" ON public.user_list_items;
END $$;

-- RLS Policies for user_lists
CREATE POLICY "Users can view their own lists" ON public.user_lists
    FOR SELECT USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can insert their own lists" ON public.user_lists
    FOR INSERT WITH CHECK (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can update their own lists" ON public.user_lists
    FOR UPDATE USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can delete their own lists" ON public.user_lists
    FOR DELETE USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

-- RLS Policies for user_list_items
CREATE POLICY "Users can view their own list items" ON public.user_list_items
    FOR SELECT USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can insert their own list items" ON public.user_list_items
    FOR INSERT WITH CHECK (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can update their own list items" ON public.user_list_items
    FOR UPDATE USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

CREATE POLICY "Users can delete their own list items" ON public.user_list_items
    FOR DELETE USING (auth.uid()::text = (SELECT supabase_user_id FROM public.users WHERE id = user_id));

-- Create function to update items_count on user_lists
CREATE OR REPLACE FUNCTION update_user_list_items_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE public.user_lists 
        SET items_count = items_count + 1, 
            last_updated = NOW()
        WHERE id = NEW.list_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE public.user_lists 
        SET items_count = GREATEST(items_count - 1, 0), 
            last_updated = NOW()
        WHERE id = OLD.list_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to maintain items_count
DROP TRIGGER IF EXISTS trigger_update_list_count_on_insert ON public.user_list_items;
CREATE TRIGGER trigger_update_list_count_on_insert
    AFTER INSERT ON public.user_list_items
    FOR EACH ROW EXECUTE FUNCTION update_user_list_items_count();

DROP TRIGGER IF EXISTS trigger_update_list_count_on_delete ON public.user_list_items;
CREATE TRIGGER trigger_update_list_count_on_delete
    AFTER DELETE ON public.user_list_items
    FOR EACH ROW EXECUTE FUNCTION update_user_list_items_count();

-- Create function to auto-update updated_at timestamps (if not exists)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
DROP TRIGGER IF EXISTS trigger_user_lists_updated_at ON public.user_lists;
CREATE TRIGGER trigger_user_lists_updated_at
    BEFORE UPDATE ON public.user_lists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_user_list_items_updated_at ON public.user_list_items;
CREATE TRIGGER trigger_user_list_items_updated_at
    BEFORE UPDATE ON public.user_list_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_lists TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_list_items TO authenticated;

-- Create initial system lists for existing users (optional)
-- This would create a "Favorites" list for all existing users
-- INSERT INTO public.user_lists (user_id, name, description, color, icon, is_favorite)
-- SELECT id, 'My Favorites', 'Automatically created favorites list', '#F59E0B', 'star', true
-- FROM public.users;

COMMENT ON TABLE public.user_lists IS 'User-created lists for organizing Instagram profiles';
COMMENT ON TABLE public.user_list_items IS 'Junction table linking lists to Instagram profiles with user customization';