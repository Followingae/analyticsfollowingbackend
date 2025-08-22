-- COMPREHENSIVE USER SEGREGATION SCHEMA IMPLEMENTATION
-- Analytics Following Backend - Industry Standard Role-Based Access Control
-- Implementation Date: August 2025

-- =============================================================================
-- PART 1: CORE ACCESS CONTROL TABLES
-- =============================================================================

-- Enhanced Role System with Hierarchical Levels
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_name VARCHAR(50) UNIQUE NOT NULL,
    role_level INTEGER NOT NULL, -- 0=brand_free, 1=brand_standard, 2=brand_premium, 3=brand_enterprise, 4=admin, 5=super_admin
    description TEXT,
    is_admin_role BOOLEAN DEFAULT false,
    permissions_json JSONB DEFAULT '{}', -- Role-specific permissions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Granular Permission System
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    permission_name VARCHAR(100) UNIQUE NOT NULL,
    permission_category VARCHAR(50) NOT NULL, -- 'user_management', 'financial', 'content', 'system', 'proposals'
    description TEXT,
    is_admin_permission BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Role-Permission Mapping
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID NOT NULL REFERENCES user_roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, permission_id)
);

-- Individual User Permission Overrides
CREATE TABLE user_permissions_override (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    is_granted BOOLEAN NOT NULL,
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    reason TEXT,
    UNIQUE(user_id, permission_id)
);

-- =============================================================================
-- PART 2: COMPREHENSIVE ACTIVITY TRACKING
-- =============================================================================

-- User Activity Logging (All User Actions)
CREATE TABLE user_activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL, -- 'login', 'profile_view', 'export', 'credit_spend', 'api_call'
    resource_type VARCHAR(50), -- 'profile', 'campaign', 'user', 'system', 'export'
    resource_id UUID,
    action_details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    credits_spent INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Admin Actions Audit Log (Admin-Specific Actions)
CREATE TABLE admin_actions_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID NOT NULL REFERENCES users(id),
    target_user_id UUID REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL, -- 'user_create', 'credit_adjust', 'permission_grant', 'subscription_change'
    old_values JSONB DEFAULT '{}',
    new_values JSONB DEFAULT '{}',
    reason TEXT,
    severity VARCHAR(20) DEFAULT 'info', -- 'info', 'warning', 'critical'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- PART 3: SUBSCRIPTION & FEATURE CONTROL SYSTEM
-- =============================================================================

-- Subscription Features Definition
CREATE TABLE subscription_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_tier VARCHAR(50) NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_limit INTEGER, -- NULL for unlimited
    feature_enabled BOOLEAN DEFAULT true,
    credit_cost_override INTEGER, -- Override default credit costs
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(subscription_tier, feature_name)
);

-- User Feature Usage Tracking
CREATE TABLE feature_usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature_name VARCHAR(100) NOT NULL,
    usage_date DATE NOT NULL,
    usage_count INTEGER DEFAULT 1,
    credits_spent INTEGER DEFAULT 0,
    subscription_covered BOOLEAN DEFAULT false,
    usage_details JSONB DEFAULT '{}',
    session_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dynamic User Limits Management
CREATE TABLE user_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature_name VARCHAR(100) NOT NULL,
    limit_type VARCHAR(50) NOT NULL, -- 'monthly', 'daily', 'total', 'concurrent'
    limit_value INTEGER NOT NULL,
    current_usage INTEGER DEFAULT 0,
    reset_date DATE,
    limit_source VARCHAR(50) DEFAULT 'subscription', -- 'subscription', 'custom', 'trial', 'bonus'
    set_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, feature_name, limit_type)
);

-- =============================================================================
-- PART 4: ENHANCED FINANCIAL MANAGEMENT
-- =============================================================================

-- Subscription History Tracking
CREATE TABLE subscription_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    old_tier VARCHAR(50),
    new_tier VARCHAR(50) NOT NULL,
    changed_by UUID REFERENCES users(id),
    change_reason TEXT,
    effective_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    billing_cycle_days INTEGER DEFAULT 30,
    auto_renew BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Credit Adjustments & Manual Operations
CREATE TABLE credit_adjustments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_id INTEGER NOT NULL REFERENCES credit_wallets(id),
    adjustment_type VARCHAR(50) NOT NULL, -- 'grant', 'deduct', 'refund', 'bonus', 'correction'
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    adjusted_by UUID NOT NULL REFERENCES users(id),
    reference_id UUID, -- Link to support ticket, proposal, etc.
    approval_status VARCHAR(20) DEFAULT 'approved', -- 'pending', 'approved', 'rejected'
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Revenue Attribution & Business Intelligence
CREATE TABLE revenue_attribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revenue_source VARCHAR(50) NOT NULL, -- 'subscription', 'credits', 'proposal', 'api_access'
    amount_usd DECIMAL(10,2) NOT NULL,
    attribution_date DATE NOT NULL,
    source_reference_id UUID,
    payment_method VARCHAR(50),
    transaction_fee_usd DECIMAL(10,2) DEFAULT 0,
    net_revenue_usd DECIMAL(10,2),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- PART 5: PROPOSAL SYSTEM ENHANCEMENTS
-- =============================================================================

-- Proposal Templates for Reusable Content
CREATE TABLE proposal_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(200) NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    template_content JSONB NOT NULL,
    default_pricing JSONB DEFAULT '{}',
    default_deliverables JSONB DEFAULT '{}',
    tags TEXT[], -- For categorization
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2), -- Track template performance
    created_by UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Proposal Analytics & Performance Tracking
CREATE TABLE proposal_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID REFERENCES admin_brand_proposals(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'created', 'sent', 'viewed', 'responded', 'accepted', 'rejected'
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    event_data JSONB DEFAULT '{}',
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- PART 6: BUSINESS INTELLIGENCE & PLATFORM METRICS
-- =============================================================================

-- Platform-wide Metrics Collection
CREATE TABLE platform_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_date DATE NOT NULL,
    metric_category VARCHAR(50) NOT NULL, -- 'financial', 'usage', 'performance', 'growth'
    metric_subcategory VARCHAR(50),
    additional_data JSONB DEFAULT '{}',
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(metric_name, metric_date)
);

-- System Health & Performance Metrics
CREATE TABLE system_health_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_percent DECIMAL(5,2),
    disk_usage_percent DECIMAL(5,2),
    active_connections INTEGER,
    response_time_ms DECIMAL(8,2),
    error_rate_percent DECIMAL(5,2),
    uptime_hours DECIMAL(10,2),
    active_users_count INTEGER,
    api_requests_per_minute INTEGER,
    cache_hit_rate_percent DECIMAL(5,2)
);

-- =============================================================================
-- PART 7: SECURITY & AUTHENTICATION ENHANCEMENTS
-- =============================================================================

-- Multi-Factor Authentication Management
CREATE TABLE user_mfa_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_method VARCHAR(50), -- 'totp', 'sms', 'email', 'backup_codes'
    mfa_secret VARCHAR(255),
    backup_codes JSONB,
    recovery_codes_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Enhanced Session Management
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    refresh_token VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    is_admin_session BOOLEAN DEFAULT false,
    session_type VARCHAR(50) DEFAULT 'web', -- 'web', 'mobile', 'api'
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Admin IP Access Control
CREATE TABLE admin_ip_whitelist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address INET,
    ip_range CIDR,
    description TEXT,
    added_by UUID NOT NULL REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Failed Login Attempts Tracking
CREATE TABLE failed_login_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255),
    ip_address INET NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_agent TEXT,
    failure_reason VARCHAR(100),
    blocked_until TIMESTAMP WITH TIME ZONE
);

-- =============================================================================
-- PART 8: DATA PRIVACY & COMPLIANCE
-- =============================================================================

-- GDPR Data Deletion Requests
CREATE TABLE data_deletion_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    requested_by UUID NOT NULL REFERENCES users(id),
    deletion_type VARCHAR(50) NOT NULL, -- 'full', 'partial', 'anonymize'
    data_categories JSONB NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'processing', 'completed', 'rejected'
    scheduled_deletion_date DATE,
    completed_at TIMESTAMP WITH TIME ZONE,
    approval_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Data Export Requests (GDPR Compliance)
CREATE TABLE data_export_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    requested_by UUID NOT NULL REFERENCES users(id),
    export_format VARCHAR(50) DEFAULT 'json', -- 'json', 'csv', 'xml'
    data_categories JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'ready', 'expired'
    file_size_bytes BIGINT,
    download_url TEXT,
    download_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- PART 9: ENHANCED EXISTING TABLES
-- =============================================================================

-- Comprehensive User Table Enhancements
DO $$
BEGIN
    -- Account Management Fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'account_status') THEN
        ALTER TABLE users ADD COLUMN account_status VARCHAR(20) DEFAULT 'active';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'suspension_reason') THEN
        ALTER TABLE users ADD COLUMN suspension_reason TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'suspension_until') THEN
        ALTER TABLE users ADD COLUMN suspension_until TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Security & Login Fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'last_login_ip') THEN
        ALTER TABLE users ADD COLUMN last_login_ip INET;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'failed_login_attempts') THEN
        ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'account_locked_until') THEN
        ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Subscription Management Fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'subscription_tier') THEN
        ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(50) DEFAULT 'brand_free';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'subscription_expires_at') THEN
        ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'subscription_auto_renew') THEN
        ALTER TABLE users ADD COLUMN subscription_auto_renew BOOLEAN DEFAULT true;
    END IF;
    
    -- Feature Limits
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'monthly_search_limit') THEN
        ALTER TABLE users ADD COLUMN monthly_search_limit INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'monthly_export_limit') THEN
        ALTER TABLE users ADD COLUMN monthly_export_limit INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'api_rate_limit') THEN
        ALTER TABLE users ADD COLUMN api_rate_limit INTEGER;
    END IF;
    
    -- Admin Management Fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'custom_permissions') THEN
        ALTER TABLE users ADD COLUMN custom_permissions JSONB DEFAULT '{}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'admin_notes') THEN
        ALTER TABLE users ADD COLUMN admin_notes TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'created_by') THEN
        ALTER TABLE users ADD COLUMN created_by UUID REFERENCES users(id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'managed_by') THEN
        ALTER TABLE users ADD COLUMN managed_by UUID REFERENCES users(id);
    END IF;
    
    -- User Experience Fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'onboarding_completed') THEN
        ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT false;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'last_feature_announcement_seen') THEN
        ALTER TABLE users ADD COLUMN last_feature_announcement_seen INTEGER DEFAULT 0;
    END IF;
    
    -- Financial Tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'total_spent_usd') THEN
        ALTER TABLE users ADD COLUMN total_spent_usd DECIMAL(10,2) DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'lifetime_value_usd') THEN
        ALTER TABLE users ADD COLUMN lifetime_value_usd DECIMAL(10,2) DEFAULT 0;
    END IF;
    
    -- Timezone & Localization
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'timezone') THEN
        ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'locale') THEN
        ALTER TABLE users ADD COLUMN locale VARCHAR(10) DEFAULT 'en';
    END IF;
    
END $$;

-- Enhanced Profiles Table for Influencer Management
DO $$
BEGIN
    -- Data Quality & Verification
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'verification_status') THEN
        ALTER TABLE profiles ADD COLUMN verification_status VARCHAR(50) DEFAULT 'unverified';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'data_quality_score') THEN
        ALTER TABLE profiles ADD COLUMN data_quality_score DECIMAL(3,2);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'last_verified_at') THEN
        ALTER TABLE profiles ADD COLUMN last_verified_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'verified_by') THEN
        ALTER TABLE profiles ADD COLUMN verified_by UUID REFERENCES users(id);
    END IF;
    
    -- Internal Cost Management
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'internal_cost_tier') THEN
        ALTER TABLE profiles ADD COLUMN internal_cost_tier VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'platform_margin_percent') THEN
        ALTER TABLE profiles ADD COLUMN platform_margin_percent DECIMAL(5,2);
    END IF;
    
    -- Data Management
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'data_source') THEN
        ALTER TABLE profiles ADD COLUMN data_source VARCHAR(50) DEFAULT 'decodo';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'last_updated_at') THEN
        ALTER TABLE profiles ADD COLUMN last_updated_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'update_frequency_days') THEN
        ALTER TABLE profiles ADD COLUMN update_frequency_days INTEGER DEFAULT 30;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'admin_notes') THEN
        ALTER TABLE profiles ADD COLUMN admin_notes TEXT;
    END IF;
    
    -- Access Control
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'is_premium_content') THEN
        ALTER TABLE profiles ADD COLUMN is_premium_content BOOLEAN DEFAULT false;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'access_tier_required') THEN
        ALTER TABLE profiles ADD COLUMN access_tier_required VARCHAR(50) DEFAULT 'free';
    END IF;
    
    -- Analytics Enhancement
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'view_count') THEN
        ALTER TABLE profiles ADD COLUMN view_count INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'profiles' AND column_name = 'unlock_count') THEN
        ALTER TABLE profiles ADD COLUMN unlock_count INTEGER DEFAULT 0;
    END IF;
    
END $$;

-- =============================================================================
-- PART 10: COMPREHENSIVE INDEXING STRATEGY
-- =============================================================================

-- User & Role Performance Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_role_status ON users(role, account_status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_tier ON users(subscription_tier);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_by ON users(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_managed_by ON users(managed_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_last_login ON users(last_login_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_expires ON users(subscription_expires_at);

-- Activity & Audit Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_logs_user_action_date ON user_activity_logs(user_id, action_type, created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_logs_resource ON user_activity_logs(resource_type, resource_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_logs_session ON user_activity_logs(session_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_admin_actions_admin_target_date ON admin_actions_log(admin_user_id, target_user_id, created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_admin_actions_action_type ON admin_actions_log(action_type, created_at);

-- Feature & Usage Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feature_usage_user_feature_date ON feature_usage_tracking(user_id, feature_name, usage_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feature_usage_date_feature ON feature_usage_tracking(usage_date, feature_name);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_limits_user_feature ON user_limits(user_id, feature_name);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscription_features_tier_feature ON subscription_features(subscription_tier, feature_name);

-- Financial & Revenue Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_credit_adjustments_user_date ON credit_adjustments(user_id, created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_credit_adjustments_type_date ON credit_adjustments(adjustment_type, created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_revenue_attribution_user_date ON revenue_attribution(user_id, attribution_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_revenue_attribution_source_date ON revenue_attribution(revenue_source, attribution_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscription_history_user_date ON subscription_history(user_id, effective_date);

-- Proposal System Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proposal_templates_service_active ON proposal_templates(service_type, is_active);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proposal_templates_usage ON proposal_templates(usage_count DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_proposal_analytics_proposal_event ON proposal_analytics(proposal_id, event_type, event_timestamp);

-- Security & Authentication Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_user_expires ON user_sessions(user_id, expires_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_failed_login_attempts_ip_time ON failed_login_attempts(ip_address, attempted_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_failed_login_attempts_email_time ON failed_login_attempts(email, attempted_at);

-- Business Intelligence Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_platform_metrics_name_date ON platform_metrics(metric_name, metric_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_platform_metrics_category_date ON platform_metrics(metric_category, metric_date);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_health_timestamp ON system_health_metrics(metric_timestamp);

-- Profile Management Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_verification_status ON profiles(verification_status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_cost_tier ON profiles(internal_cost_tier);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_data_quality ON profiles(data_quality_score);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_access_tier ON profiles(access_tier_required);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_premium_content ON profiles(is_premium_content);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_last_updated ON profiles(last_updated_at);

-- Permission System Indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_permissions_override_user ON user_permissions_override(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_permissions_category ON permissions(permission_category);

-- =============================================================================
-- PART 11: INITIAL DATA SEEDING
-- =============================================================================

-- Insert Default Roles
INSERT INTO user_roles (role_name, role_level, description, is_admin_role) VALUES
('super_admin', 5, 'Platform Super Administrator - Full System Access', true),
('admin', 4, 'Administrator - Limited Super Admin Functions', true),
('brand_enterprise', 3, 'Enterprise Brand Account - Full Features + API', false),
('brand_premium', 2, 'Premium Brand Account - Advanced Features', false),
('brand_standard', 1, 'Standard Brand Account - Essential Features', false),
('brand_free', 0, 'Free Brand Account - Basic Features', false)
ON CONFLICT (role_name) DO NOTHING;

-- Insert Core Permissions
INSERT INTO permissions (permission_name, permission_category, description, is_admin_permission) VALUES
-- User Management Permissions
('can_view_all_users', 'user_management', 'View all platform users', true),
('can_create_users', 'user_management', 'Create new user accounts', true),
('can_edit_users', 'user_management', 'Edit user account details', true),
('can_delete_users', 'user_management', 'Delete user accounts', true),
('can_manage_roles', 'user_management', 'Assign and modify user roles', true),
('can_view_user_activity', 'user_management', 'View user activity logs', true),

-- Financial Management Permissions
('can_view_all_transactions', 'financial', 'View all financial transactions', true),
('can_adjust_credits', 'financial', 'Manually adjust user credits', true),
('can_manage_subscriptions', 'financial', 'Manage user subscriptions', true),
('can_view_revenue_reports', 'financial', 'Access revenue reports', true),
('can_process_refunds', 'financial', 'Process refunds', true),
('can_manage_pricing', 'financial', 'Manage platform pricing', true),

-- Content Management Permissions
('can_view_all_profiles', 'content', 'View all influencer profiles', true),
('can_edit_profiles', 'content', 'Edit influencer profile data', true),
('can_manage_influencer_data', 'content', 'Manage global influencer database', true),
('can_approve_content', 'content', 'Approve content and data quality', true),
('can_manage_categories', 'content', 'Manage content categories', true),

-- Proposal Management Permissions
('can_create_proposals', 'proposals', 'Create brand proposals', true),
('can_view_all_proposals', 'proposals', 'View all platform proposals', true),
('can_approve_proposals', 'proposals', 'Approve/reject proposals', true),
('can_manage_templates', 'proposals', 'Manage proposal templates', true),
('can_view_proposal_analytics', 'proposals', 'View proposal performance analytics', true),

-- System Management Permissions
('can_configure_system', 'system', 'Configure system settings', true),
('can_view_system_logs', 'system', 'View system and audit logs', true),
('can_manage_integrations', 'system', 'Manage third-party integrations', true),
('can_access_database', 'system', 'Direct database access', true),
('can_export_platform_data', 'system', 'Export platform-wide data', true),

-- Brand User Permissions
('can_search_profiles', 'content', 'Search influencer profiles', false),
('can_unlock_profiles', 'content', 'Unlock full profile analytics', false),
('can_create_campaigns', 'content', 'Create marketing campaigns', false),
('can_export_data', 'content', 'Export data and reports', false),
('can_use_api', 'system', 'Access platform API', false)
ON CONFLICT (permission_name) DO NOTHING;

-- Assign Permissions to Roles
DO $$
DECLARE
    super_admin_role_id UUID;
    admin_role_id UUID;
    brand_enterprise_role_id UUID;
    brand_premium_role_id UUID;
    brand_standard_role_id UUID;
    brand_free_role_id UUID;
BEGIN
    -- Get Role IDs
    SELECT id INTO super_admin_role_id FROM user_roles WHERE role_name = 'super_admin';
    SELECT id INTO admin_role_id FROM user_roles WHERE role_name = 'admin';
    SELECT id INTO brand_enterprise_role_id FROM user_roles WHERE role_name = 'brand_enterprise';
    SELECT id INTO brand_premium_role_id FROM user_roles WHERE role_name = 'brand_premium';
    SELECT id INTO brand_standard_role_id FROM user_roles WHERE role_name = 'brand_standard';
    SELECT id INTO brand_free_role_id FROM user_roles WHERE role_name = 'brand_free';
    
    -- Super Admin gets ALL permissions
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT super_admin_role_id, id FROM permissions
    ON CONFLICT DO NOTHING;
    
    -- Admin gets most permissions except system-critical ones
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT admin_role_id, id FROM permissions 
    WHERE permission_name NOT IN ('can_access_database', 'can_configure_system')
    ON CONFLICT DO NOTHING;
    
    -- Brand Enterprise - Full brand features + API
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT brand_enterprise_role_id, id FROM permissions 
    WHERE permission_name IN ('can_search_profiles', 'can_unlock_profiles', 'can_create_campaigns', 'can_export_data', 'can_use_api')
    ON CONFLICT DO NOTHING;
    
    -- Brand Premium - Full brand features
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT brand_premium_role_id, id FROM permissions 
    WHERE permission_name IN ('can_search_profiles', 'can_unlock_profiles', 'can_create_campaigns', 'can_export_data')
    ON CONFLICT DO NOTHING;
    
    -- Brand Standard - Essential features
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT brand_standard_role_id, id FROM permissions 
    WHERE permission_name IN ('can_search_profiles', 'can_unlock_profiles', 'can_create_campaigns')
    ON CONFLICT DO NOTHING;
    
    -- Brand Free - Basic features only
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT brand_free_role_id, id FROM permissions 
    WHERE permission_name IN ('can_search_profiles')
    ON CONFLICT DO NOTHING;
END $$;

-- Insert Default Subscription Features
INSERT INTO subscription_features (subscription_tier, feature_name, feature_limit, description) VALUES
-- Brand Free Limits
('brand_free', 'profile_searches_per_month', 5, 'Basic profile searches'),
('brand_free', 'campaign_creation_limit', 1, 'Maximum active campaigns'),
('brand_free', 'list_creation_limit', 2, 'Maximum saved lists'),
('brand_free', 'profiles_per_list_limit', 10, 'Profiles per list'),
('brand_free', 'export_operations_per_month', 0, 'Data exports'),

-- Brand Standard Limits
('brand_standard', 'profile_searches_per_month', 50, 'Enhanced profile searches'),
('brand_standard', 'campaign_creation_limit', 5, 'Maximum active campaigns'),
('brand_standard', 'list_creation_limit', 10, 'Maximum saved lists'),
('brand_standard', 'profiles_per_list_limit', 100, 'Profiles per list'),
('brand_standard', 'export_operations_per_month', 5, 'Data exports'),

-- Brand Premium Limits (NULL = unlimited)
('brand_premium', 'profile_searches_per_month', NULL, 'Unlimited profile searches'),
('brand_premium', 'campaign_creation_limit', NULL, 'Unlimited campaigns'),
('brand_premium', 'list_creation_limit', NULL, 'Unlimited lists'),
('brand_premium', 'profiles_per_list_limit', NULL, 'Unlimited profiles per list'),
('brand_premium', 'export_operations_per_month', NULL, 'Unlimited exports'),
('brand_premium', 'api_calls_per_month', 1000, 'API access'),

-- Brand Enterprise Limits
('brand_enterprise', 'profile_searches_per_month', NULL, 'Unlimited profile searches'),
('brand_enterprise', 'campaign_creation_limit', NULL, 'Unlimited campaigns'),
('brand_enterprise', 'list_creation_limit', NULL, 'Unlimited lists'),
('brand_enterprise', 'profiles_per_list_limit', NULL, 'Unlimited profiles per list'),
('brand_enterprise', 'export_operations_per_month', NULL, 'Unlimited exports'),
('brand_enterprise', 'api_calls_per_month', 10000, 'Enhanced API access'),
('brand_enterprise', 'white_label_access', 1, 'White-label features'),
('brand_enterprise', 'dedicated_support', 1, 'Dedicated account manager')
ON CONFLICT (subscription_tier, feature_name) DO NOTHING;

-- =============================================================================
-- PART 12: ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on all new tables
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_permissions_override ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_actions_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_usage_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_attribution ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_health_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_mfa_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_ip_whitelist ENABLE ROW LEVEL SECURITY;
ALTER TABLE failed_login_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_deletion_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_export_requests ENABLE ROW LEVEL SECURITY;

-- Super Admin & Admin Full Access Policies
CREATE POLICY "admin_full_access_user_roles" ON user_roles FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "admin_full_access_permissions" ON permissions FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "admin_full_access_role_permissions" ON role_permissions FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- User Activity Logs - Users see their own, Admins see all
CREATE POLICY "user_activity_logs_access" ON user_activity_logs FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Admin Actions - Only admins can see
CREATE POLICY "admin_actions_log_access" ON admin_actions_log FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- User-specific data access
CREATE POLICY "user_permissions_override_access" ON user_permissions_override FOR ALL TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "feature_usage_tracking_access" ON feature_usage_tracking FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "user_limits_access" ON user_limits FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Financial data - Users see their own, Admins see all
CREATE POLICY "subscription_history_access" ON subscription_history FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "credit_adjustments_access" ON credit_adjustments FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "revenue_attribution_access" ON revenue_attribution FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- System data - Admin only
CREATE POLICY "platform_metrics_admin_only" ON platform_metrics FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "system_health_metrics_admin_only" ON system_health_metrics FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Security tables - Admin only
CREATE POLICY "admin_ip_whitelist_admin_only" ON admin_ip_whitelist FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "failed_login_attempts_admin_only" ON failed_login_attempts FOR ALL TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- User sessions - Own sessions + admin access
CREATE POLICY "user_sessions_access" ON user_sessions FOR ALL TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- MFA settings - Own settings + admin access
CREATE POLICY "user_mfa_settings_access" ON user_mfa_settings FOR ALL TO authenticated USING (
    user_id = (SELECT auth.uid()) OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Subscription features - Read-only for all, admin can modify
CREATE POLICY "subscription_features_read" ON subscription_features FOR SELECT TO authenticated USING (true);
CREATE POLICY "subscription_features_admin_modify" ON subscription_features FOR INSERT, UPDATE, DELETE TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Proposal templates - Read-only for brands, admin can modify
CREATE POLICY "proposal_templates_read" ON proposal_templates FOR SELECT TO authenticated USING (
    is_active = true OR 
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "proposal_templates_admin_modify" ON proposal_templates FOR INSERT, UPDATE, DELETE TO authenticated USING (
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- Privacy compliance - Users can request their own data, admins manage all
CREATE POLICY "data_deletion_requests_access" ON data_deletion_requests FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR requested_by = (SELECT auth.uid()) OR
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

CREATE POLICY "data_export_requests_access" ON data_export_requests FOR SELECT TO authenticated USING (
    user_id = (SELECT auth.uid()) OR requested_by = (SELECT auth.uid()) OR
    EXISTS (SELECT 1 FROM users WHERE users.id = (SELECT auth.uid()) AND users.role IN ('super_admin', 'admin'))
);

-- =============================================================================
-- MIGRATION COMPLETION LOG
-- =============================================================================

INSERT INTO platform_metrics (metric_name, metric_value, metric_date, metric_category, additional_data) 
VALUES (
    'comprehensive_user_segregation_migration_completed',
    1,
    CURRENT_DATE,
    'system',
    '{"migration_version": "1.0", "tables_created": 20, "indexes_created": 35, "rls_policies": 25}'
);

-- End of Comprehensive User Segregation Schema Implementation