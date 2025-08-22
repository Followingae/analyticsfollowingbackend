-- Migration: Enhanced Lists System
-- Builds on existing user_lists and user_list_items with advanced features

BEGIN;

-- ============================================================================
-- 1. ENHANCE EXISTING LISTS TABLES
-- Add advanced features to existing list system
-- ============================================================================

-- Enhance user_lists table with new features
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS list_type VARCHAR(50) DEFAULT 'custom'; -- custom, favorites, campaign_ready, proposal_draft
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb; -- User-defined tags
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS shared_with JSONB DEFAULT '[]'::jsonb; -- User IDs for sharing
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS export_settings JSONB DEFAULT '{}'::jsonb; -- Export preferences
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS auto_update_rules JSONB DEFAULT '{}'::jsonb; -- Rules for auto-updating
ALTER TABLE user_lists ADD COLUMN IF NOT EXISTS performance_metrics JSONB DEFAULT '{}'::jsonb; -- List performance data

-- Enhance user_list_items table
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0; -- Priority ranking
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active'; -- active, archived, contacted, rejected
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS contact_status VARCHAR(50) DEFAULT 'not_contacted'; -- not_contacted, pending, responded, declined
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS estimated_cost INTEGER; -- User's estimated cost for this influencer
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS collaboration_notes TEXT; -- Notes about collaboration
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMP WITH TIME ZONE; -- When last contacted
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS response_received_at TIMESTAMP WITH TIME ZONE; -- When response received
ALTER TABLE user_list_items ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}'::jsonb; -- Custom user fields

-- Add performance indexes for enhanced lists
CREATE INDEX IF NOT EXISTS idx_user_lists_type ON user_lists(user_id, list_type);
CREATE INDEX IF NOT EXISTS idx_user_lists_tags ON user_lists USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_user_lists_performance ON user_lists(user_id, items_count DESC);

CREATE INDEX IF NOT EXISTS idx_user_list_items_priority ON user_list_items(list_id, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_user_list_items_status ON user_list_items(list_id, status);
CREATE INDEX IF NOT EXISTS idx_user_list_items_contact_status ON user_list_items(list_id, contact_status);
CREATE INDEX IF NOT EXISTS idx_user_list_items_cost ON user_list_items(list_id, estimated_cost) WHERE estimated_cost IS NOT NULL;

-- ============================================================================
-- 2. LIST TEMPLATES SYSTEM
-- Pre-defined list templates for common use cases
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop table if it exists to ensure clean creation with proper defaults
DROP TABLE IF EXISTS public.list_templates CASCADE;

CREATE TABLE public.list_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Template metadata
    template_name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL, -- campaign, discovery, analysis, outreach
    
    -- Template configuration
    default_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_fields JSONB DEFAULT '[]'::jsonb, -- Fields that must be filled
    optional_fields JSONB DEFAULT '[]'::jsonb, -- Fields that can be filled
    auto_rules JSONB DEFAULT '{}'::jsonb, -- Automatic population rules
    
    -- Template properties
    is_public BOOLEAN DEFAULT false, -- Available to all users
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    usage_count INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for list templates
CREATE INDEX IF NOT EXISTS idx_list_templates_category ON list_templates(category, is_public);
CREATE INDEX IF NOT EXISTS idx_list_templates_usage ON list_templates(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_list_templates_creator ON list_templates(created_by, created_at DESC);

-- Enable RLS
ALTER TABLE list_templates ENABLE ROW LEVEL SECURITY;

-- RLS Policies for list templates
CREATE POLICY "list_templates_public_read" ON list_templates
    FOR SELECT TO authenticated USING (is_public = true OR created_by = (SELECT auth.uid()));

CREATE POLICY "list_templates_creator_all" ON list_templates
    FOR ALL TO authenticated USING (created_by = (SELECT auth.uid()));

CREATE POLICY "list_templates_service_all" ON list_templates
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 3. LIST COLLABORATION SYSTEM
-- Share lists and collaborate with team members
-- ============================================================================

-- Drop table if it exists to ensure clean creation
DROP TABLE IF EXISTS public.list_collaborations CASCADE;

CREATE TABLE public.list_collaborations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    list_id UUID NOT NULL REFERENCES user_lists(id) ON DELETE CASCADE,
    
    -- Collaboration details
    shared_with_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    shared_by_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Permissions
    permission_level VARCHAR(50) NOT NULL DEFAULT 'view', -- view, comment, edit, admin
    can_add_items BOOLEAN DEFAULT false,
    can_remove_items BOOLEAN DEFAULT false,
    can_edit_items BOOLEAN DEFAULT false,
    can_invite_others BOOLEAN DEFAULT false,
    
    -- Collaboration metadata
    invitation_message TEXT,
    accepted_at TIMESTAMP WITH TIME ZONE,
    last_accessed TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- pending, accepted, declined, revoked
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(list_id, shared_with_user_id)
);

-- Indexes for collaborations
CREATE INDEX IF NOT EXISTS idx_list_collaborations_list ON list_collaborations(list_id, status);
CREATE INDEX IF NOT EXISTS idx_list_collaborations_user ON list_collaborations(shared_with_user_id, status);
CREATE INDEX IF NOT EXISTS idx_list_collaborations_shared_by ON list_collaborations(shared_by_user_id, created_at DESC);

-- Enable RLS
ALTER TABLE list_collaborations ENABLE ROW LEVEL SECURITY;

-- RLS Policies for collaborations
CREATE POLICY "list_collaborations_participants" ON list_collaborations
    FOR ALL TO authenticated USING (
        shared_with_user_id = (SELECT auth.uid()) OR 
        shared_by_user_id = (SELECT auth.uid()) OR
        list_id IN (SELECT id FROM user_lists WHERE user_id = (SELECT auth.uid()))
    );

CREATE POLICY "list_collaborations_service" ON list_collaborations
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 4. LIST ACTIVITY TRACKING
-- Track all actions performed on lists and items
-- ============================================================================

-- Drop table if it exists to ensure clean creation
DROP TABLE IF EXISTS public.list_activity_logs CASCADE;

CREATE TABLE public.list_activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Activity target
    list_id UUID NOT NULL REFERENCES user_lists(id) ON DELETE CASCADE,
    list_item_id UUID REFERENCES user_list_items(id) ON DELETE CASCADE, -- NULL for list-level actions
    
    -- Actor information
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Activity details
    action_type VARCHAR(100) NOT NULL, -- created, updated, deleted, item_added, item_removed, shared, etc.
    action_description TEXT NOT NULL,
    
    -- Change tracking
    old_values JSONB DEFAULT '{}'::jsonb,
    new_values JSONB DEFAULT '{}'::jsonb,
    affected_fields JSONB DEFAULT '[]'::jsonb,
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for activity logs
CREATE INDEX IF NOT EXISTS idx_list_activity_list ON list_activity_logs(list_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_activity_user ON list_activity_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_activity_action ON list_activity_logs(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_activity_item ON list_activity_logs(list_item_id, created_at DESC) WHERE list_item_id IS NOT NULL;

-- Enable RLS
ALTER TABLE list_activity_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy for activity logs
CREATE POLICY "list_activity_logs_list_access" ON list_activity_logs
    FOR SELECT TO authenticated USING (
        list_id IN (
            SELECT id FROM user_lists WHERE user_id = (SELECT auth.uid())
            UNION
            SELECT list_id FROM list_collaborations 
            WHERE shared_with_user_id = (SELECT auth.uid()) AND status = 'accepted'
        )
    );

CREATE POLICY "list_activity_logs_service" ON list_activity_logs
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 5. LIST ANALYTICS AND PERFORMANCE
-- Track list performance and usage analytics
-- ============================================================================

-- Drop table if it exists to ensure clean creation
DROP TABLE IF EXISTS public.list_performance_metrics CASCADE;

CREATE TABLE public.list_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    list_id UUID NOT NULL REFERENCES user_lists(id) ON DELETE CASCADE,
    
    -- Time dimension
    date_recorded DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Performance metrics
    total_items INTEGER DEFAULT 0,
    unlocked_items INTEGER DEFAULT 0,
    contacted_items INTEGER DEFAULT 0,
    responded_items INTEGER DEFAULT 0,
    
    -- Engagement metrics
    views_count INTEGER DEFAULT 0,
    updates_count INTEGER DEFAULT 0,
    collaborator_activity INTEGER DEFAULT 0,
    
    -- Cost tracking
    total_estimated_cost INTEGER DEFAULT 0,
    average_item_cost INTEGER DEFAULT 0,
    
    -- Quality metrics
    completion_rate DECIMAL(5,2) DEFAULT 0, -- Percentage of items with complete data
    response_rate DECIMAL(5,2) DEFAULT 0, -- Percentage of contacted items that responded
    
    -- Metadata
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(list_id, date_recorded)
);

-- Indexes for performance metrics
CREATE INDEX IF NOT EXISTS idx_list_performance_list_date ON list_performance_metrics(list_id, date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_list_performance_metrics ON list_performance_metrics(total_items DESC, completion_rate DESC);

-- Enable RLS
ALTER TABLE list_performance_metrics ENABLE ROW LEVEL SECURITY;

-- RLS Policy for performance metrics
CREATE POLICY "list_performance_metrics_owner" ON list_performance_metrics
    FOR ALL TO authenticated USING (
        list_id IN (SELECT id FROM user_lists WHERE user_id = (SELECT auth.uid()))
    );

CREATE POLICY "list_performance_metrics_service" ON list_performance_metrics
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 6. LIST EXPORT JOBS
-- Track list export operations and downloads
-- ============================================================================

-- Drop table if it exists to ensure clean creation
DROP TABLE IF EXISTS public.list_export_jobs CASCADE;

CREATE TABLE public.list_export_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    list_id UUID NOT NULL REFERENCES user_lists(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Export configuration
    export_format VARCHAR(20) NOT NULL, -- csv, xlsx, json, pdf
    export_fields JSONB NOT NULL DEFAULT '[]'::jsonb, -- Fields to include in export
    include_unlocked_data BOOLEAN DEFAULT false,
    filter_criteria JSONB DEFAULT '{}'::jsonb, -- Filters applied to export
    
    -- Export results
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    file_path TEXT, -- Path to generated file
    file_size_bytes INTEGER,
    download_count INTEGER DEFAULT 0,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Expiration
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days'),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for export jobs
CREATE INDEX IF NOT EXISTS idx_list_export_user ON list_export_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_export_list ON list_export_jobs(list_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_export_status ON list_export_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_export_expires ON list_export_jobs(expires_at) WHERE status = 'completed';

-- Enable RLS
ALTER TABLE list_export_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policy for export jobs
CREATE POLICY "list_export_jobs_owner" ON list_export_jobs
    FOR ALL TO authenticated USING (user_id = (SELECT auth.uid()));

CREATE POLICY "list_export_jobs_service" ON list_export_jobs
    FOR ALL TO service_role USING (true);

-- ============================================================================
-- 7. DATABASE FUNCTIONS FOR ENHANCED LISTS
-- Optimized functions for list operations
-- ============================================================================

-- Function to update list performance metrics
CREATE OR REPLACE FUNCTION public.update_list_performance_metrics(p_list_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_metrics RECORD;
BEGIN
    -- Calculate current metrics for the list
    SELECT 
        COUNT(*) as total_items,
        COUNT(*) FILTER (WHERE profile_id IN (SELECT profile_id FROM unlocked_profiles WHERE user_id = ul.user_id)) as unlocked_items,
        COUNT(*) FILTER (WHERE contact_status IN ('pending', 'responded')) as contacted_items,
        COUNT(*) FILTER (WHERE contact_status = 'responded') as responded_items,
        COALESCE(SUM(estimated_cost), 0) as total_estimated_cost,
        COALESCE(AVG(estimated_cost), 0) as average_item_cost,
        ROUND(
            (COUNT(*) FILTER (WHERE notes IS NOT NULL AND notes != '' AND estimated_cost IS NOT NULL) * 100.0 / NULLIF(COUNT(*), 0)), 
            2
        ) as completion_rate,
        ROUND(
            (COUNT(*) FILTER (WHERE contact_status = 'responded') * 100.0 / NULLIF(COUNT(*) FILTER (WHERE contact_status IN ('pending', 'responded')), 0)), 
            2
        ) as response_rate
    INTO v_metrics
    FROM user_list_items uli
    JOIN user_lists ul ON uli.list_id = ul.id
    WHERE uli.list_id = p_list_id;
    
    -- Insert or update performance metrics
    INSERT INTO list_performance_metrics (
        list_id, date_recorded, total_items, unlocked_items, contacted_items, 
        responded_items, total_estimated_cost, average_item_cost, completion_rate, response_rate
    ) VALUES (
        p_list_id, CURRENT_DATE, v_metrics.total_items, v_metrics.unlocked_items, 
        v_metrics.contacted_items, v_metrics.responded_items, v_metrics.total_estimated_cost, 
        v_metrics.average_item_cost, v_metrics.completion_rate, v_metrics.response_rate
    )
    ON CONFLICT (list_id, date_recorded) DO UPDATE SET
        total_items = EXCLUDED.total_items,
        unlocked_items = EXCLUDED.unlocked_items,
        contacted_items = EXCLUDED.contacted_items,
        responded_items = EXCLUDED.responded_items,
        total_estimated_cost = EXCLUDED.total_estimated_cost,
        average_item_cost = EXCLUDED.average_item_cost,
        completion_rate = EXCLUDED.completion_rate,
        response_rate = EXCLUDED.response_rate,
        recorded_at = CURRENT_TIMESTAMP;
END;
$$;

-- Function to bulk update list item statuses
CREATE OR REPLACE FUNCTION public.bulk_update_list_items(
    p_list_id UUID,
    p_item_ids UUID[],
    p_updates JSONB
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_updated_count INTEGER := 0;
    v_item_id UUID;
BEGIN
    -- Update each item with the provided updates
    FOREACH v_item_id IN ARRAY p_item_ids
    LOOP
        UPDATE user_list_items 
        SET 
            status = COALESCE((p_updates->>'status')::VARCHAR, status),
            contact_status = COALESCE((p_updates->>'contact_status')::VARCHAR, contact_status),
            priority_score = COALESCE((p_updates->>'priority_score')::INTEGER, priority_score),
            estimated_cost = COALESCE((p_updates->>'estimated_cost')::INTEGER, estimated_cost),
            collaboration_notes = COALESCE(p_updates->>'collaboration_notes', collaboration_notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = v_item_id AND list_id = p_list_id;
        
        IF FOUND THEN
            v_updated_count := v_updated_count + 1;
        END IF;
    END LOOP;
    
    -- Update list metrics
    PERFORM update_list_performance_metrics(p_list_id);
    
    RETURN v_updated_count;
END;
$$;

-- ============================================================================
-- 8. TRIGGERS FOR AUTOMATIC UPDATES
-- Automatically maintain list metrics and activity logs
-- ============================================================================

-- Trigger function to log list activities
CREATE OR REPLACE FUNCTION public.log_list_activity()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Log the activity based on the operation
    IF TG_OP = 'INSERT' THEN
        INSERT INTO list_activity_logs (
            list_id, list_item_id, user_id, action_type, action_description, new_values
        ) VALUES (
            NEW.list_id, 
            CASE WHEN TG_TABLE_NAME = 'user_list_items' THEN NEW.id ELSE NULL END,
            NEW.user_id,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'list_created' ELSE 'item_added' END,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'List created: ' || NEW.name ELSE 'Item added to list' END,
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO list_activity_logs (
            list_id, list_item_id, user_id, action_type, action_description, old_values, new_values
        ) VALUES (
            NEW.list_id,
            CASE WHEN TG_TABLE_NAME = 'user_list_items' THEN NEW.id ELSE NULL END,
            NEW.user_id,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'list_updated' ELSE 'item_updated' END,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'List updated: ' || NEW.name ELSE 'Item updated in list' END,
            to_jsonb(OLD),
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO list_activity_logs (
            list_id, list_item_id, user_id, action_type, action_description, old_values
        ) VALUES (
            OLD.list_id,
            CASE WHEN TG_TABLE_NAME = 'user_list_items' THEN OLD.id ELSE NULL END,
            OLD.user_id,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'list_deleted' ELSE 'item_removed' END,
            CASE WHEN TG_TABLE_NAME = 'user_lists' THEN 'List deleted: ' || OLD.name ELSE 'Item removed from list' END,
            to_jsonb(OLD)
        );
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$;

-- Create triggers for activity logging
DROP TRIGGER IF EXISTS trigger_log_list_activity ON user_lists;
CREATE TRIGGER trigger_log_list_activity
    AFTER INSERT OR UPDATE OR DELETE ON user_lists
    FOR EACH ROW EXECUTE FUNCTION log_list_activity();

DROP TRIGGER IF EXISTS trigger_log_list_item_activity ON user_list_items;
CREATE TRIGGER trigger_log_list_item_activity
    AFTER INSERT OR UPDATE OR DELETE ON user_list_items
    FOR EACH ROW EXECUTE FUNCTION log_list_activity();

-- Trigger to update list items count
CREATE OR REPLACE FUNCTION public.update_list_items_count()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE user_lists 
        SET items_count = items_count + 1, last_updated = CURRENT_TIMESTAMP
        WHERE id = NEW.list_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE user_lists 
        SET items_count = items_count - 1, last_updated = CURRENT_TIMESTAMP
        WHERE id = OLD.list_id;
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$;

-- Create trigger for items count
DROP TRIGGER IF EXISTS trigger_update_list_items_count ON user_list_items;
CREATE TRIGGER trigger_update_list_items_count
    AFTER INSERT OR DELETE ON user_list_items
    FOR EACH ROW EXECUTE FUNCTION update_list_items_count();

-- ============================================================================
-- 9. SEED DEFAULT LIST TEMPLATES
-- Create useful default templates for common use cases
-- ============================================================================

INSERT INTO list_templates (template_name, description, category, default_settings, required_fields, optional_fields, is_public) VALUES
(
    'Campaign Planning',
    'Template for organizing influencers for marketing campaigns',
    'campaign',
    '{"auto_calculate_costs": true, "priority_scoring": true, "contact_tracking": true}',
    '["estimated_cost", "priority_score"]',
    '["collaboration_notes", "contact_status", "custom_fields"]',
    true
),
(
    'Discovery Research',
    'Template for saving and organizing discovered influencers',
    'discovery',
    '{"auto_tag_categories": true, "track_unlock_status": true}',
    '["notes"]',
    '["tags", "priority_score", "estimated_cost"]',
    true
),
(
    'Outreach Tracking',
    'Template for managing influencer outreach and responses',
    'outreach',
    '{"contact_tracking": true, "response_tracking": true, "follow_up_reminders": true}',
    '["contact_status", "collaboration_notes"]',
    '["last_contacted_at", "response_received_at", "estimated_cost"]',
    true
),
(
    'Performance Analysis',
    'Template for analyzing influencer performance and ROI',
    'analysis',
    '{"performance_tracking": true, "cost_analysis": true, "roi_calculation": true}',
    '["estimated_cost", "priority_score"]',
    '["custom_fields", "collaboration_notes"]',
    true
);

COMMIT;

-- Verification queries (for manual checking)
/*
-- Check enhanced lists structure
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'user_lists' AND table_schema = 'public'
ORDER BY ordinal_position;

-- Check list templates
SELECT * FROM list_templates ORDER BY category, template_name;

-- Check performance metrics structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'list_performance_metrics' AND table_schema = 'public';
*/