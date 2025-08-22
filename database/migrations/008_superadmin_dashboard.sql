-- Migration 008: Superadmin Dashboard System
-- Complete superadmin dashboard for managing all platform systems
-- Author: Claude
-- Date: 2025-01-21

-- Note: RLS is already enabled on auth.users by Supabase

-- 1. Admin Users System
CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    admin_role VARCHAR(50) NOT NULL DEFAULT 'support', -- superadmin, admin, support, analyst
    permissions JSONB DEFAULT '{}', -- Specific permissions
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- 2. System Analytics Table
CREATE TABLE IF NOT EXISTS system_analytics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    total_profiles INTEGER DEFAULT 0,
    profiles_analyzed INTEGER DEFAULT 0,
    api_requests INTEGER DEFAULT 0,
    ai_analysis_jobs INTEGER DEFAULT 0,
    successful_ai_jobs INTEGER DEFAULT 0,
    credits_consumed INTEGER DEFAULT 0,
    revenue_generated DECIMAL(10,2) DEFAULT 0.00,
    total_campaigns INTEGER DEFAULT 0,
    active_campaigns INTEGER DEFAULT 0,
    total_proposals INTEGER DEFAULT 0,
    active_proposals INTEGER DEFAULT 0,
    system_uptime_percentage DECIMAL(5,2) DEFAULT 100.00,
    average_response_time_ms INTEGER DEFAULT 0,
    error_rate_percentage DECIMAL(5,2) DEFAULT 0.00,
    cache_hit_rate_percentage DECIMAL(5,2) DEFAULT 0.00,
    analytics_data JSONB DEFAULT '{}', -- Additional metrics
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date)
);

-- 3. System Configurations Table
CREATE TABLE IF NOT EXISTS system_configurations (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50) DEFAULT 'general', -- general, ai, credits, performance, security
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    requires_restart BOOLEAN DEFAULT false,
    created_by UUID REFERENCES auth.users(id),
    updated_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Platform Notifications for Admin
CREATE TABLE IF NOT EXISTS admin_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL, -- system_alert, user_activity, performance, security
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info', -- critical, warning, info, success
    data JSONB DEFAULT '{}', -- Additional notification data
    is_read BOOLEAN DEFAULT false,
    is_dismissed BOOLEAN DEFAULT false,
    target_admin_role VARCHAR(50), -- If null, visible to all admins
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITH TIME ZONE,
    dismissed_at TIMESTAMP WITH TIME ZONE
);

-- 5. System Audit Logs
CREATE TABLE IF NOT EXISTS system_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL, -- user, campaign, proposal, config, system
    resource_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    result VARCHAR(20) DEFAULT 'success', -- success, failure, partial
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. System Maintenance Jobs
CREATE TABLE IF NOT EXISTS system_maintenance_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL, -- cleanup, backup, analytics, optimization
    job_status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, running, completed, failed
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    job_config JSONB DEFAULT '{}',
    job_result JSONB DEFAULT '{}',
    error_message TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Feature Flags System
CREATE TABLE IF NOT EXISTS feature_flags (
    id BIGSERIAL PRIMARY KEY,
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    flag_description TEXT,
    is_enabled BOOLEAN DEFAULT false,
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),
    target_users JSONB DEFAULT '[]', -- Array of user IDs for targeted rollout
    conditions JSONB DEFAULT '{}', -- Conditions for enabling the flag
    created_by UUID REFERENCES auth.users(id),
    updated_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. User Management Admin Views
CREATE TABLE IF NOT EXISTS admin_user_actions (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    target_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL, -- suspend, unsuspend, delete, update_credits, reset_password
    reason TEXT,
    action_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_admin_role ON admin_users(admin_role);
CREATE INDEX IF NOT EXISTS idx_admin_users_active ON admin_users(is_active);

CREATE INDEX IF NOT EXISTS idx_system_analytics_date ON system_analytics(date DESC);
CREATE INDEX IF NOT EXISTS idx_system_analytics_date_range ON system_analytics(date, created_at);

CREATE INDEX IF NOT EXISTS idx_system_configurations_key ON system_configurations(config_key);
CREATE INDEX IF NOT EXISTS idx_system_configurations_type_active ON system_configurations(config_type, is_active);

CREATE INDEX IF NOT EXISTS idx_admin_notifications_type ON admin_notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_severity ON admin_notifications(severity);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_unread ON admin_notifications(is_read, created_at DESC) WHERE is_read = false;
CREATE INDEX IF NOT EXISTS idx_admin_notifications_target_role ON admin_notifications(target_admin_role, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_audit_logs_admin_user ON system_audit_logs(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_audit_logs_resource ON system_audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_system_audit_logs_action ON system_audit_logs(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_audit_logs_created ON system_audit_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_maintenance_jobs_status ON system_maintenance_jobs(job_status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_system_maintenance_jobs_type ON system_maintenance_jobs(job_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feature_flags_name ON feature_flags(flag_name);
CREATE INDEX IF NOT EXISTS idx_feature_flags_enabled ON feature_flags(is_enabled);

CREATE INDEX IF NOT EXISTS idx_admin_user_actions_admin_user ON admin_user_actions(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_user_actions_target_user ON admin_user_actions(target_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_user_actions_action ON admin_user_actions(action, created_at DESC);

-- Database functions for admin analytics
CREATE OR REPLACE FUNCTION get_platform_summary()
RETURNS JSON
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
    SELECT json_build_object(
        'total_users', (SELECT COUNT(*) FROM auth.users),
        'active_users', (SELECT COUNT(*) FROM auth.users WHERE last_sign_in_at > NOW() - INTERVAL '30 days'),
        'total_profiles', (SELECT COUNT(*) FROM profiles),
        'total_campaigns', (SELECT COUNT(*) FROM campaigns),
        'active_campaigns', (SELECT COUNT(*) FROM campaigns WHERE campaign_status = 'active'),
        'total_proposals', (SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'brand_proposals') THEN (SELECT COUNT(*) FROM brand_proposals) ELSE 0 END),
        'pending_proposals', (SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'brand_proposals') THEN (SELECT COUNT(*) FROM brand_proposals WHERE status = 'pending') ELSE 0 END),
        'total_credits_consumed', (SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE transaction_type = 'debit'),
        'ai_jobs_processed', (SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_analysis_jobs') THEN (SELECT COUNT(*) FROM ai_analysis_jobs WHERE status = 'completed') ELSE 0 END),
        'last_updated', NOW()
    );
$$;

CREATE OR REPLACE FUNCTION get_user_activity_summary(days INTEGER DEFAULT 7)
RETURNS JSON
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
    SELECT json_build_object(
        'new_users', (
            SELECT COUNT(*) 
            FROM auth.users 
            WHERE created_at > NOW() - INTERVAL '1 day' * days
        ),
        'active_users', (
            SELECT COUNT(DISTINCT user_id) 
            FROM user_profile_access 
            WHERE created_at > NOW() - INTERVAL '1 day' * days
        ),
        'profile_searches', 0, -- TODO: Implement when search_history table is available
        'credits_purchased', (
            SELECT COALESCE(SUM(amount), 0) 
            FROM credit_transactions 
            WHERE transaction_type = 'credit' AND created_at > NOW() - INTERVAL '1 day' * days
        ),
        'period_days', days,
        'generated_at', NOW()
    );
$$;

CREATE OR REPLACE FUNCTION get_system_performance_metrics()
RETURNS JSON
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
    WITH recent_analytics AS (
        SELECT * FROM system_analytics 
        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY date DESC
        LIMIT 7
    )
    SELECT json_build_object(
        'avg_response_time', (SELECT AVG(average_response_time_ms) FROM recent_analytics),
        'avg_error_rate', (SELECT AVG(error_rate_percentage) FROM recent_analytics),
        'avg_cache_hit_rate', (SELECT AVG(cache_hit_rate_percentage) FROM recent_analytics),
        'avg_uptime', (SELECT AVG(system_uptime_percentage) FROM recent_analytics),
        'total_api_requests', (SELECT SUM(api_requests) FROM recent_analytics),
        'successful_ai_jobs_rate', (
            SELECT CASE 
                WHEN SUM(ai_analysis_jobs) > 0 
                THEN (SUM(successful_ai_jobs)::FLOAT / SUM(ai_analysis_jobs)::FLOAT * 100)
                ELSE 0 
            END
            FROM recent_analytics
        ),
        'period', '7_days',
        'generated_at', NOW()
    );
$$;

-- Trigger to update system analytics daily
CREATE OR REPLACE FUNCTION update_daily_system_analytics()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
BEGIN
    INSERT INTO system_analytics (
        date,
        total_users,
        active_users,
        new_users,
        total_profiles,
        profiles_analyzed,
        total_campaigns,
        active_campaigns,
        total_proposals,
        active_proposals,
        credits_consumed
    ) VALUES (
        CURRENT_DATE,
        (SELECT COUNT(*) FROM auth.users),
        (SELECT COUNT(*) FROM auth.users WHERE last_sign_in_at > NOW() - INTERVAL '30 days'),
        (SELECT COUNT(*) FROM auth.users WHERE created_at::DATE = CURRENT_DATE),
        (SELECT COUNT(*) FROM profiles),
        (SELECT COUNT(*) FROM profiles WHERE ai_analyzed_at IS NOT NULL),
        (SELECT COUNT(*) FROM campaigns),
        (SELECT COUNT(*) FROM campaigns WHERE campaign_status = 'active'),
        (SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'brand_proposals') THEN (SELECT COUNT(*) FROM brand_proposals) ELSE 0 END),
        (SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'brand_proposals') THEN (SELECT COUNT(*) FROM brand_proposals WHERE status IN ('pending', 'approved', 'in_progress')) ELSE 0 END),
        (SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE transaction_type = 'debit' AND created_at::DATE = CURRENT_DATE)
    )
    ON CONFLICT (date) 
    DO UPDATE SET
        total_users = EXCLUDED.total_users,
        active_users = EXCLUDED.active_users,
        new_users = EXCLUDED.new_users,
        total_profiles = EXCLUDED.total_profiles,
        profiles_analyzed = EXCLUDED.profiles_analyzed,
        total_campaigns = EXCLUDED.total_campaigns,
        active_campaigns = EXCLUDED.active_campaigns,
        total_proposals = EXCLUDED.total_proposals,
        active_proposals = EXCLUDED.active_proposals,
        credits_consumed = EXCLUDED.credits_consumed,
        updated_at = CURRENT_TIMESTAMP;
END;
$$;

-- Row Level Security Policies

-- Admin Users - Only superadmins can manage other admins
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Superadmins can view all admin users" ON admin_users
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE admin_role = 'superadmin' AND is_active = true
        )
    );

CREATE POLICY "Superadmins can manage admin users" ON admin_users
    FOR ALL USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE admin_role = 'superadmin' AND is_active = true
        )
    );

-- System Analytics - Admin read access
ALTER TABLE system_analytics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view system analytics" ON system_analytics
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

-- System Configurations - Admin access with role restrictions
ALTER TABLE system_configurations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view configurations" ON system_configurations
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

CREATE POLICY "Superadmins and admins can manage configurations" ON system_configurations
    FOR ALL USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE admin_role IN ('superadmin', 'admin') AND is_active = true
        )
    );

-- Admin Notifications - Role-based access
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view relevant notifications" ON admin_notifications
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE is_active = true 
            AND (admin_notifications.target_admin_role IS NULL OR admin_role = admin_notifications.target_admin_role)
        )
    );

CREATE POLICY "Admins can update notification read status" ON admin_notifications
    FOR UPDATE USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

-- System Audit Logs - Admin read access
ALTER TABLE system_audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view audit logs" ON system_audit_logs
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

-- System Maintenance Jobs - Admin management
ALTER TABLE system_maintenance_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view maintenance jobs" ON system_maintenance_jobs
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

CREATE POLICY "Admins can manage maintenance jobs" ON system_maintenance_jobs
    FOR ALL USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE admin_role IN ('superadmin', 'admin') AND is_active = true
        )
    );

-- Feature Flags - Admin management
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view feature flags" ON feature_flags
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

CREATE POLICY "Superadmins and admins can manage feature flags" ON feature_flags
    FOR ALL USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users 
            WHERE admin_role IN ('superadmin', 'admin') AND is_active = true
        )
    );

-- Admin User Actions - Admin tracking
ALTER TABLE admin_user_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view user actions" ON admin_user_actions
    FOR SELECT USING (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

CREATE POLICY "Admins can record user actions" ON admin_user_actions
    FOR INSERT WITH CHECK (
        auth.uid() IN (
            SELECT user_id FROM admin_users WHERE is_active = true
        )
    );

-- Insert default system configurations
INSERT INTO system_configurations (config_key, config_value, config_type, description) VALUES
    ('ai_analysis_enabled', 'true', 'ai', 'Enable AI analysis for profiles and posts'),
    ('ai_batch_size', '16', 'ai', 'Batch size for AI processing'),
    ('ai_max_workers', '2', 'ai', 'Maximum AI processing workers'),
    ('default_user_credits', '10', 'credits', 'Default credits for new users'),
    ('profile_analysis_cost', '1', 'credits', 'Credits cost for profile analysis'),
    ('cache_ttl_profiles', '86400', 'performance', 'Cache TTL for profiles in seconds'),
    ('cache_ttl_ai_results', '604800', 'performance', 'Cache TTL for AI results in seconds'),
    ('api_rate_limit_per_minute', '100', 'security', 'API rate limit per user per minute'),
    ('max_profiles_per_list', '1000', 'general', 'Maximum profiles allowed per user list'),
    ('system_maintenance_window', '{"start": "02:00", "end": "04:00", "timezone": "UTC"}', 'general', 'System maintenance window')
ON CONFLICT (config_key) DO NOTHING;

-- Insert default superadmin (will need to be updated with actual user ID)
-- INSERT INTO admin_users (user_id, admin_role, permissions) VALUES
--     ('your-superadmin-user-id', 'superadmin', '{"all": true}')
-- ON CONFLICT DO NOTHING;

COMMENT ON TABLE admin_users IS 'Admin users with role-based permissions for platform management';
COMMENT ON TABLE system_analytics IS 'Daily system analytics and performance metrics';
COMMENT ON TABLE system_configurations IS 'System-wide configuration settings';
COMMENT ON TABLE admin_notifications IS 'Administrative notifications and alerts';
COMMENT ON TABLE system_audit_logs IS 'Comprehensive audit trail for admin actions';
COMMENT ON TABLE system_maintenance_jobs IS 'System maintenance and background jobs';
COMMENT ON TABLE feature_flags IS 'Feature flag system for controlled rollouts';
COMMENT ON TABLE admin_user_actions IS 'Admin actions performed on user accounts';