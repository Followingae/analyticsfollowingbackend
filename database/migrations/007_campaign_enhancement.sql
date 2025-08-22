-- Migration: Campaign Enhancement - Complete Campaign Management with Deliverables
-- Enhanced campaign system with deliverables tracking, performance metrics, and workflow management

BEGIN;

-- ============================================================================
-- 1. ENHANCE EXISTING CAMPAIGNS TABLE
-- Add advanced campaign management features to existing campaigns
-- ============================================================================

-- Add enhanced campaign fields to existing campaigns table
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_status VARCHAR(50) DEFAULT 'draft';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_type VARCHAR(50) DEFAULT 'influencer_marketing';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_audience JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_goals JSONB DEFAULT '[]'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS kpi_targets JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS brand_guidelines TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS content_requirements JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS approval_workflow JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS budget_allocated INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS budget_spent INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS expected_reach INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS actual_reach INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS expected_engagement INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS actual_engagement INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_start_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_end_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS deliverables_due_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS completion_percentage INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS roi_percentage DECIMAL(5,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;

-- Add constraints for enhanced fields (drop if exists, then create)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_campaign_status') THEN
        ALTER TABLE campaigns ADD CONSTRAINT check_campaign_status 
            CHECK (campaign_status IN ('draft', 'planning', 'active', 'paused', 'completed', 'cancelled'));
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_campaign_type') THEN
        ALTER TABLE campaigns ADD CONSTRAINT check_campaign_type 
            CHECK (campaign_type IN ('influencer_marketing', 'sponsored_content', 'product_placement', 'brand_partnership', 'event_promotion', 'ugc_campaign'));
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_budget_positive') THEN
        ALTER TABLE campaigns ADD CONSTRAINT check_budget_positive 
            CHECK (budget_allocated >= 0 AND budget_spent >= 0);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_completion_percentage') THEN
        ALTER TABLE campaigns ADD CONSTRAINT check_completion_percentage 
            CHECK (completion_percentage >= 0 AND completion_percentage <= 100);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'check_quality_score') THEN
        ALTER TABLE campaigns ADD CONSTRAINT check_quality_score 
            CHECK (quality_score >= 0 AND quality_score <= 10);
    END IF;
END $$;

-- Add enhanced indexes for campaigns
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(campaign_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_type ON campaigns(campaign_type, campaign_status);
CREATE INDEX IF NOT EXISTS idx_campaigns_dates ON campaigns(campaign_start_date, campaign_end_date);
CREATE INDEX IF NOT EXISTS idx_campaigns_budget ON campaigns(budget_allocated, budget_spent);
CREATE INDEX IF NOT EXISTS idx_campaigns_performance ON campaigns(actual_reach DESC, actual_engagement DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_completion ON campaigns(completion_percentage DESC, quality_score DESC);

-- ============================================================================
-- 2. CAMPAIGN DELIVERABLES TABLE
-- Track specific deliverable items and their approval workflow
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_deliverables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Deliverable identification
    deliverable_title VARCHAR(300) NOT NULL,
    deliverable_description TEXT,
    deliverable_type VARCHAR(50) NOT NULL, -- post, story, reel, ugc_video, blog_post, review, event_coverage
    
    -- Assignment and responsibility
    assigned_to_profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    assigned_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Content specifications
    content_specifications JSONB DEFAULT '{}'::jsonb, -- Detailed specs: dimensions, duration, format
    required_hashtags JSONB DEFAULT '[]'::jsonb,
    required_mentions JSONB DEFAULT '[]'::jsonb,
    required_links JSONB DEFAULT '[]'::jsonb,
    content_guidelines TEXT,
    
    -- Submission tracking
    submitted_content_url TEXT, -- Link to submitted content
    submitted_content_text TEXT, -- Text content for posts
    submitted_media_urls JSONB DEFAULT '[]'::jsonb, -- Media files (images, videos)
    submitted_notes TEXT, -- Additional notes from creator
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    -- Approval workflow
    approval_status VARCHAR(50) DEFAULT 'pending', -- pending, submitted, under_review, approved, rejected, revision_requested, published
    reviewed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    approval_deadline TIMESTAMP WITH TIME ZONE,
    
    -- Publication tracking
    published_at TIMESTAMP WITH TIME ZONE,
    published_url TEXT, -- Final published content URL
    published_platform VARCHAR(50), -- instagram, tiktok, youtube, etc.
    
    -- Performance metrics (post-publication)
    performance_metrics JSONB DEFAULT '{}'::jsonb, -- Views, likes, comments, shares, saves
    estimated_reach INTEGER,
    actual_reach INTEGER,
    estimated_engagement INTEGER,
    actual_engagement INTEGER,
    
    -- Timeline and reminders
    due_date TIMESTAMP WITH TIME ZONE,
    reminder_sent_count INTEGER DEFAULT 0,
    last_reminder_at TIMESTAMP WITH TIME ZONE,
    
    -- Quality and feedback
    quality_rating INTEGER CHECK (quality_rating >= 1 AND quality_rating <= 10),
    client_feedback TEXT,
    creator_feedback TEXT,
    
    -- Financial tracking
    compensation_amount_usd INTEGER DEFAULT 0,
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    payment_date TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for campaign deliverables
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_campaign ON campaign_deliverables(campaign_id, approval_status);
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_assigned ON campaign_deliverables(assigned_to_profile_id, due_date);
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_status ON campaign_deliverables(approval_status, due_date);
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_type ON campaign_deliverables(deliverable_type, approval_status);
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_due ON campaign_deliverables(due_date) WHERE approval_status IN ('pending', 'submitted', 'under_review');
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_performance ON campaign_deliverables(actual_reach DESC, actual_engagement DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_deliverables_payment ON campaign_deliverables(payment_status, payment_date);

-- ============================================================================
-- 3. CAMPAIGN COLLABORATORS TABLE
-- Track team members and influencers involved in campaigns
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_collaborators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Collaborator identification (either user or profile)
    collaborator_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    collaborator_profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Collaboration details
    role VARCHAR(50) NOT NULL, -- influencer, content_creator, brand_manager, reviewer, analyst
    collaboration_type VARCHAR(50) DEFAULT 'contributor', -- owner, manager, contributor, viewer
    
    -- Permissions and access
    permissions JSONB DEFAULT '[]'::jsonb, -- ["view", "edit", "approve", "publish", "analytics"]
    can_create_deliverables BOOLEAN DEFAULT false,
    can_approve_content BOOLEAN DEFAULT false,
    can_view_analytics BOOLEAN DEFAULT false,
    can_manage_budget BOOLEAN DEFAULT false,
    
    -- Collaboration agreement
    compensation_type VARCHAR(50) DEFAULT 'fixed', -- fixed, per_deliverable, revenue_share, barter
    compensation_amount_usd INTEGER DEFAULT 0,
    compensation_terms JSONB DEFAULT '{}'::jsonb,
    
    -- Contract and legal
    contract_signed BOOLEAN DEFAULT false,
    contract_signed_at TIMESTAMP WITH TIME ZONE,
    contract_url TEXT,
    
    -- Status and timeline
    collaboration_status VARCHAR(50) DEFAULT 'active', -- active, paused, completed, terminated
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE,
    
    -- Performance tracking
    deliverables_assigned INTEGER DEFAULT 0,
    deliverables_completed INTEGER DEFAULT 0,
    average_quality_rating DECIMAL(3,2),
    total_compensation_earned INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    CHECK ((collaborator_user_id IS NOT NULL AND collaborator_profile_id IS NULL) OR 
           (collaborator_user_id IS NULL AND collaborator_profile_id IS NOT NULL)),
    UNIQUE(campaign_id, collaborator_user_id),
    UNIQUE(campaign_id, collaborator_profile_id)
);

-- Indexes for campaign collaborators
CREATE INDEX IF NOT EXISTS idx_campaign_collaborators_campaign ON campaign_collaborators(campaign_id, collaboration_status);
CREATE INDEX IF NOT EXISTS idx_campaign_collaborators_user ON campaign_collaborators(collaborator_user_id, collaboration_status);
CREATE INDEX IF NOT EXISTS idx_campaign_collaborators_profile ON campaign_collaborators(collaborator_profile_id, collaboration_status);
CREATE INDEX IF NOT EXISTS idx_campaign_collaborators_role ON campaign_collaborators(role, collaboration_status);
CREATE INDEX IF NOT EXISTS idx_campaign_collaborators_performance ON campaign_collaborators(average_quality_rating DESC, deliverables_completed DESC);

-- ============================================================================
-- 4. CAMPAIGN MILESTONES TABLE
-- Track campaign progress with milestone-based workflow
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Milestone details
    milestone_title VARCHAR(200) NOT NULL,
    milestone_description TEXT,
    milestone_type VARCHAR(50) NOT NULL, -- planning, content_creation, review, launch, performance_review
    
    -- Timeline
    target_date TIMESTAMP WITH TIME ZONE,
    actual_date TIMESTAMP WITH TIME ZONE,
    
    -- Status and progress
    milestone_status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, delayed, cancelled
    completion_percentage INTEGER DEFAULT 0 CHECK (completion_percentage >= 0 AND completion_percentage <= 100),
    
    -- Dependencies
    depends_on_milestone_ids JSONB DEFAULT '[]'::jsonb, -- Array of milestone IDs this depends on
    blocks_milestone_ids JSONB DEFAULT '[]'::jsonb, -- Array of milestone IDs this blocks
    
    -- Requirements and deliverables
    required_deliverables JSONB DEFAULT '[]'::jsonb, -- Deliverable IDs required for completion
    success_criteria TEXT,
    acceptance_criteria TEXT,
    
    -- Assignment and responsibility
    assigned_to_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Approval workflow
    requires_approval BOOLEAN DEFAULT false,
    approved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Budget tracking
    budgeted_amount_usd INTEGER DEFAULT 0,
    actual_spent_usd INTEGER DEFAULT 0,
    
    -- Quality and feedback
    quality_rating INTEGER CHECK (quality_rating >= 1 AND quality_rating <= 10),
    milestone_notes TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for campaign milestones
CREATE INDEX IF NOT EXISTS idx_campaign_milestones_campaign ON campaign_milestones(campaign_id, milestone_status);
CREATE INDEX IF NOT EXISTS idx_campaign_milestones_assigned ON campaign_milestones(assigned_to_user_id, target_date);
CREATE INDEX IF NOT EXISTS idx_campaign_milestones_status ON campaign_milestones(milestone_status, target_date);
CREATE INDEX IF NOT EXISTS idx_campaign_milestones_type ON campaign_milestones(milestone_type, milestone_status);
CREATE INDEX IF NOT EXISTS idx_campaign_milestones_timeline ON campaign_milestones(target_date, actual_date);

-- ============================================================================
-- 5. CAMPAIGN PERFORMANCE METRICS TABLE
-- Track detailed campaign performance and ROI metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Time dimension
    date_recorded DATE NOT NULL DEFAULT CURRENT_DATE,
    metric_period VARCHAR(20) DEFAULT 'daily', -- daily, weekly, monthly, campaign_total
    
    -- Reach and impression metrics
    total_impressions BIGINT DEFAULT 0,
    unique_reach BIGINT DEFAULT 0,
    organic_reach BIGINT DEFAULT 0,
    paid_reach BIGINT DEFAULT 0,
    frequency DECIMAL(4,2) DEFAULT 0, -- Average number of times each person saw content
    
    -- Engagement metrics
    total_engagement BIGINT DEFAULT 0,
    likes_count BIGINT DEFAULT 0,
    comments_count BIGINT DEFAULT 0,
    shares_count BIGINT DEFAULT 0,
    saves_count BIGINT DEFAULT 0,
    clicks_count BIGINT DEFAULT 0,
    engagement_rate DECIMAL(5,2) DEFAULT 0,
    
    -- Video-specific metrics
    video_views BIGINT DEFAULT 0,
    video_completion_rate DECIMAL(5,2) DEFAULT 0,
    average_watch_time INTEGER DEFAULT 0, -- in seconds
    
    -- Conversion metrics
    website_clicks BIGINT DEFAULT 0,
    link_clicks BIGINT DEFAULT 0,
    profile_visits BIGINT DEFAULT 0,
    follower_growth INTEGER DEFAULT 0,
    email_signups INTEGER DEFAULT 0,
    app_downloads INTEGER DEFAULT 0,
    
    -- E-commerce metrics
    product_views INTEGER DEFAULT 0,
    add_to_cart INTEGER DEFAULT 0,
    purchases INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5,2) DEFAULT 0,
    revenue_generated DECIMAL(10,2) DEFAULT 0,
    average_order_value DECIMAL(8,2) DEFAULT 0,
    
    -- Cost and ROI metrics
    cost_per_impression DECIMAL(8,4) DEFAULT 0,
    cost_per_click DECIMAL(6,2) DEFAULT 0,
    cost_per_engagement DECIMAL(6,2) DEFAULT 0,
    cost_per_conversion DECIMAL(8,2) DEFAULT 0,
    return_on_ad_spend DECIMAL(6,2) DEFAULT 0, -- ROAS
    return_on_investment DECIMAL(6,2) DEFAULT 0, -- ROI percentage
    
    -- Quality metrics
    sentiment_score DECIMAL(4,2) DEFAULT 0, -- -1 to +1
    brand_mention_sentiment DECIMAL(4,2) DEFAULT 0,
    user_generated_content_count INTEGER DEFAULT 0,
    
    -- Platform breakdown
    platform_metrics JSONB DEFAULT '{}'::jsonb, -- Platform-specific metrics
    demographic_breakdown JSONB DEFAULT '{}'::jsonb, -- Age, gender, location breakdown
    
    -- Metadata
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(campaign_id, date_recorded, metric_period)
);

-- Indexes for campaign performance metrics
CREATE INDEX IF NOT EXISTS idx_campaign_performance_campaign_date ON campaign_performance_metrics(campaign_id, date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_performance_date ON campaign_performance_metrics(date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_performance_period ON campaign_performance_metrics(metric_period, date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_performance_engagement ON campaign_performance_metrics(engagement_rate DESC, total_engagement DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_performance_roi ON campaign_performance_metrics(return_on_investment DESC, conversion_rate DESC);

-- ============================================================================
-- 6. CAMPAIGN BUDGET TRACKING TABLE
-- Detailed budget allocation and expense tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_budget_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Budget item details
    budget_item_name VARCHAR(200) NOT NULL,
    budget_category VARCHAR(100) NOT NULL, -- influencer_fees, production_costs, advertising_spend, tools_software, misc
    description TEXT,
    
    -- Budget allocation
    budgeted_amount_usd INTEGER NOT NULL CHECK (budgeted_amount_usd >= 0),
    actual_spent_usd INTEGER DEFAULT 0 CHECK (actual_spent_usd >= 0),
    remaining_budget_usd INTEGER GENERATED ALWAYS AS (budgeted_amount_usd - actual_spent_usd) STORED,
    
    -- Timeline
    budget_period_start DATE,
    budget_period_end DATE,
    
    -- Status and approval
    budget_status VARCHAR(50) DEFAULT 'allocated', -- allocated, pending_approval, approved, spent, over_budget
    approved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Related entities
    related_deliverable_id UUID REFERENCES campaign_deliverables(id) ON DELETE SET NULL,
    related_collaborator_id UUID REFERENCES campaign_collaborators(id) ON DELETE SET NULL,
    related_milestone_id UUID REFERENCES campaign_milestones(id) ON DELETE SET NULL,
    
    -- Payment tracking
    payment_method VARCHAR(50), -- credit_card, bank_transfer, paypal, crypto, etc.
    payment_reference VARCHAR(200),
    payment_date TIMESTAMP WITH TIME ZONE,
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    
    -- Vendor/supplier information
    vendor_name VARCHAR(200),
    vendor_contact_info JSONB DEFAULT '{}'::jsonb,
    invoice_number VARCHAR(100),
    invoice_url TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for campaign budget tracking
CREATE INDEX IF NOT EXISTS idx_campaign_budget_campaign ON campaign_budget_tracking(campaign_id, budget_category);
CREATE INDEX IF NOT EXISTS idx_campaign_budget_category ON campaign_budget_tracking(budget_category, budget_status);
CREATE INDEX IF NOT EXISTS idx_campaign_budget_status ON campaign_budget_tracking(budget_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_budget_period ON campaign_budget_tracking(budget_period_start, budget_period_end);
CREATE INDEX IF NOT EXISTS idx_campaign_budget_payment ON campaign_budget_tracking(payment_status, payment_date);
CREATE INDEX IF NOT EXISTS idx_campaign_budget_amounts ON campaign_budget_tracking(budgeted_amount_usd DESC, actual_spent_usd DESC);

-- ============================================================================
-- 7. CAMPAIGN ACTIVITY LOG TABLE
-- Comprehensive audit trail for all campaign activities
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.campaign_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    
    -- Activity details
    activity_type VARCHAR(100) NOT NULL, -- created, updated, status_changed, deliverable_submitted, etc.
    activity_description TEXT NOT NULL,
    
    -- Actor information
    performed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    performed_by_profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    
    -- Related entities
    related_deliverable_id UUID REFERENCES campaign_deliverables(id) ON DELETE SET NULL,
    related_collaborator_id UUID REFERENCES campaign_collaborators(id) ON DELETE SET NULL,
    related_milestone_id UUID REFERENCES campaign_milestones(id) ON DELETE SET NULL,
    related_budget_item_id UUID REFERENCES campaign_budget_tracking(id) ON DELETE SET NULL,
    
    -- Change tracking
    old_values JSONB DEFAULT '{}'::jsonb,
    new_values JSONB DEFAULT '{}'::jsonb,
    affected_fields JSONB DEFAULT '[]'::jsonb,
    
    -- Context and metadata
    activity_context JSONB DEFAULT '{}'::jsonb, -- Additional context data
    ip_address INET,
    user_agent TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    CHECK ((performed_by_user_id IS NOT NULL AND performed_by_profile_id IS NULL) OR 
           (performed_by_user_id IS NULL AND performed_by_profile_id IS NOT NULL) OR
           (performed_by_user_id IS NULL AND performed_by_profile_id IS NULL)) -- System activities
);

-- Indexes for campaign activity log
CREATE INDEX IF NOT EXISTS idx_campaign_activity_campaign ON campaign_activity_log(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_activity_user ON campaign_activity_log(performed_by_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_activity_profile ON campaign_activity_log(performed_by_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_activity_type ON campaign_activity_log(activity_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_activity_deliverable ON campaign_activity_log(related_deliverable_id, created_at DESC);

-- ============================================================================
-- 8. DATABASE FUNCTIONS FOR CAMPAIGN MANAGEMENT
-- Optimized functions for common campaign operations
-- ============================================================================

-- Function to calculate campaign completion percentage
CREATE OR REPLACE FUNCTION public.calculate_campaign_completion(p_campaign_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total_deliverables INTEGER;
    v_completed_deliverables INTEGER;
    v_total_milestones INTEGER;
    v_completed_milestones INTEGER;
    v_completion_percentage INTEGER;
BEGIN
    -- Count total and completed deliverables
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE approval_status = 'published')
    INTO v_total_deliverables, v_completed_deliverables
    FROM campaign_deliverables 
    WHERE campaign_id = p_campaign_id;
    
    -- Count total and completed milestones
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE milestone_status = 'completed')
    INTO v_total_milestones, v_completed_milestones
    FROM campaign_milestones 
    WHERE campaign_id = p_campaign_id;
    
    -- Calculate weighted completion percentage
    -- 70% weight for deliverables, 30% weight for milestones
    IF v_total_deliverables > 0 OR v_total_milestones > 0 THEN
        v_completion_percentage := (
            COALESCE((v_completed_deliverables::DECIMAL / NULLIF(v_total_deliverables, 0)) * 70, 0) +
            COALESCE((v_completed_milestones::DECIMAL / NULLIF(v_total_milestones, 0)) * 30, 0)
        )::INTEGER;
    ELSE
        v_completion_percentage := 0;
    END IF;
    
    -- Update campaign completion percentage
    UPDATE campaigns 
    SET completion_percentage = v_completion_percentage,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_campaign_id;
    
    RETURN v_completion_percentage;
END;
$$;

-- Function to get campaign summary with key metrics
CREATE OR REPLACE FUNCTION public.get_campaign_summary(p_campaign_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_summary JSONB;
BEGIN
    SELECT jsonb_build_object(
        'campaign_id', c.id,
        'name', c.name,
        'campaign_status', c.campaign_status,
        'campaign_type', c.campaign_type,
        'budget_allocated', c.budget_allocated,
        'budget_spent', c.budget_spent,
        'budget_remaining', c.budget_allocated - c.budget_spent,
        'completion_percentage', c.completion_percentage,
        'expected_reach', c.expected_reach,
        'actual_reach', c.actual_reach,
        'roi_percentage', c.roi_percentage,
        'quality_score', c.quality_score,
        'campaign_start_date', c.campaign_start_date,
        'campaign_end_date', c.campaign_end_date,
        
        -- Deliverable metrics
        'total_deliverables', COALESCE(deliverable_metrics.total_count, 0),
        'completed_deliverables', COALESCE(deliverable_metrics.completed_count, 0),
        'pending_deliverables', COALESCE(deliverable_metrics.pending_count, 0),
        'overdue_deliverables', COALESCE(deliverable_metrics.overdue_count, 0),
        
        -- Collaborator metrics
        'total_collaborators', COALESCE(collaborator_metrics.total_count, 0),
        'active_collaborators', COALESCE(collaborator_metrics.active_count, 0),
        
        -- Milestone metrics
        'total_milestones', COALESCE(milestone_metrics.total_count, 0),
        'completed_milestones', COALESCE(milestone_metrics.completed_count, 0),
        
        -- Latest performance metrics
        'latest_engagement_rate', COALESCE(latest_performance.engagement_rate, 0),
        'latest_conversion_rate', COALESCE(latest_performance.conversion_rate, 0),
        'latest_roi', COALESCE(latest_performance.return_on_investment, 0)
    ) INTO v_summary
    FROM campaigns c
    LEFT JOIN (
        SELECT 
            campaign_id,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE approval_status = 'published') as completed_count,
            COUNT(*) FILTER (WHERE approval_status IN ('pending', 'submitted', 'under_review')) as pending_count,
            COUNT(*) FILTER (WHERE due_date < CURRENT_TIMESTAMP AND approval_status NOT IN ('published', 'approved')) as overdue_count
        FROM campaign_deliverables 
        WHERE campaign_id = p_campaign_id
        GROUP BY campaign_id
    ) deliverable_metrics ON c.id = deliverable_metrics.campaign_id
    LEFT JOIN (
        SELECT 
            campaign_id,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE collaboration_status = 'active') as active_count
        FROM campaign_collaborators 
        WHERE campaign_id = p_campaign_id
        GROUP BY campaign_id
    ) collaborator_metrics ON c.id = collaborator_metrics.campaign_id
    LEFT JOIN (
        SELECT 
            campaign_id,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE milestone_status = 'completed') as completed_count
        FROM campaign_milestones 
        WHERE campaign_id = p_campaign_id
        GROUP BY campaign_id
    ) milestone_metrics ON c.id = milestone_metrics.campaign_id
    LEFT JOIN (
        SELECT DISTINCT ON (campaign_id)
            campaign_id,
            engagement_rate,
            conversion_rate,
            return_on_investment
        FROM campaign_performance_metrics 
        WHERE campaign_id = p_campaign_id
        ORDER BY campaign_id, date_recorded DESC
    ) latest_performance ON c.id = latest_performance.campaign_id
    WHERE c.id = p_campaign_id;
    
    RETURN v_summary;
END;
$$;

-- Function to update campaign budget spent
CREATE OR REPLACE FUNCTION public.update_campaign_budget_spent(p_campaign_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total_spent INTEGER;
BEGIN
    -- Calculate total spent from budget tracking
    SELECT COALESCE(SUM(actual_spent_usd), 0)
    INTO v_total_spent
    FROM campaign_budget_tracking
    WHERE campaign_id = p_campaign_id;
    
    -- Update campaign budget spent
    UPDATE campaigns 
    SET budget_spent = v_total_spent,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_campaign_id;
END;
$$;

-- ============================================================================
-- 9. TRIGGERS FOR AUTOMATIC UPDATES
-- Maintain data consistency and automatic calculations
-- ============================================================================

-- Function to update campaign timestamp
CREATE OR REPLACE FUNCTION update_campaign_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to auto-update campaign completion on deliverable changes
CREATE OR REPLACE FUNCTION update_campaign_completion_on_deliverable()
RETURNS TRIGGER AS $$
BEGIN
    -- Update campaign completion percentage when deliverable status changes
    IF (TG_OP = 'UPDATE' AND OLD.approval_status != NEW.approval_status) OR TG_OP = 'INSERT' OR TG_OP = 'DELETE' THEN
        PERFORM calculate_campaign_completion(COALESCE(NEW.campaign_id, OLD.campaign_id));
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function to auto-update campaign budget on budget tracking changes
CREATE OR REPLACE FUNCTION update_campaign_budget_on_tracking()
RETURNS TRIGGER AS $$
BEGIN
    -- Update campaign budget spent when budget tracking changes
    IF (TG_OP = 'UPDATE' AND OLD.actual_spent_usd != NEW.actual_spent_usd) OR TG_OP = 'INSERT' OR TG_OP = 'DELETE' THEN
        PERFORM update_campaign_budget_spent(COALESCE(NEW.campaign_id, OLD.campaign_id));
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER trigger_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_campaign_timestamp();

CREATE TRIGGER trigger_campaign_deliverables_updated_at
    BEFORE UPDATE ON campaign_deliverables
    FOR EACH ROW EXECUTE FUNCTION update_campaign_timestamp();

CREATE TRIGGER trigger_campaign_collaborators_updated_at
    BEFORE UPDATE ON campaign_collaborators
    FOR EACH ROW EXECUTE FUNCTION update_campaign_timestamp();

CREATE TRIGGER trigger_campaign_milestones_updated_at
    BEFORE UPDATE ON campaign_milestones
    FOR EACH ROW EXECUTE FUNCTION update_campaign_timestamp();

CREATE TRIGGER trigger_campaign_budget_tracking_updated_at
    BEFORE UPDATE ON campaign_budget_tracking
    FOR EACH ROW EXECUTE FUNCTION update_campaign_timestamp();

-- Auto-update triggers
CREATE TRIGGER trigger_update_campaign_completion
    AFTER INSERT OR UPDATE OR DELETE ON campaign_deliverables
    FOR EACH ROW EXECUTE FUNCTION update_campaign_completion_on_deliverable();

CREATE TRIGGER trigger_update_campaign_budget
    AFTER INSERT OR UPDATE OR DELETE ON campaign_budget_tracking
    FOR EACH ROW EXECUTE FUNCTION update_campaign_budget_on_tracking();

-- ============================================================================
-- 10. ROW LEVEL SECURITY (RLS) POLICIES
-- Secure access to campaign data
-- ============================================================================

-- Enable RLS on new campaign tables (campaigns table RLS already exists)
ALTER TABLE campaign_deliverables ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_collaborators ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_budget_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_activity_log ENABLE ROW LEVEL SECURITY;

-- Campaign Deliverables Policies
CREATE POLICY "campaign_deliverables_user_policy" ON campaign_deliverables
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id FROM campaign_collaborators 
            WHERE campaign_id = campaign_deliverables.campaign_id AND collaboration_status = 'active'
        )
    );

CREATE POLICY "campaign_deliverables_service_policy" ON campaign_deliverables
    FOR ALL TO service_role USING (true);

-- Campaign Collaborators Policies
CREATE POLICY "campaign_collaborators_user_policy" ON campaign_collaborators
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id
        )
    );

CREATE POLICY "campaign_collaborators_service_policy" ON campaign_collaborators
    FOR ALL TO service_role USING (true);

-- Campaign Milestones Policies
CREATE POLICY "campaign_milestones_user_policy" ON campaign_milestones
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id FROM campaign_collaborators 
            WHERE campaign_id = campaign_milestones.campaign_id AND collaboration_status = 'active'
        )
    );

CREATE POLICY "campaign_milestones_service_policy" ON campaign_milestones
    FOR ALL TO service_role USING (true);

-- Campaign Performance Metrics Policies (Campaign owners and managers only)
CREATE POLICY "campaign_performance_user_policy" ON campaign_performance_metrics
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id FROM campaign_collaborators 
            WHERE campaign_id = campaign_performance_metrics.campaign_id 
            AND collaboration_status = 'active' 
            AND can_view_analytics = true
        )
    );

CREATE POLICY "campaign_performance_service_policy" ON campaign_performance_metrics
    FOR ALL TO service_role USING (true);

-- Campaign Budget Tracking Policies (Campaign owners and budget managers only)
CREATE POLICY "campaign_budget_user_policy" ON campaign_budget_tracking
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id FROM campaign_collaborators 
            WHERE campaign_id = campaign_budget_tracking.campaign_id 
            AND collaboration_status = 'active' 
            AND can_manage_budget = true
        )
    );

CREATE POLICY "campaign_budget_service_policy" ON campaign_budget_tracking
    FOR ALL TO service_role USING (true);

-- Campaign Activity Log Policies
CREATE POLICY "campaign_activity_user_policy" ON campaign_activity_log
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM campaigns WHERE id = campaign_id
            UNION
            SELECT collaborator_user_id FROM campaign_collaborators 
            WHERE campaign_id = campaign_activity_log.campaign_id AND collaboration_status = 'active'
        )
    );

CREATE POLICY "campaign_activity_service_policy" ON campaign_activity_log
    FOR ALL TO service_role USING (true);

COMMIT;

-- Verification queries (for manual checking)
/*
-- Check campaign enhancement structure
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name LIKE 'campaign%'
ORDER BY table_name, ordinal_position;

-- Test campaign summary function
SELECT get_campaign_summary('00000000-0000-0000-0000-000000000000'::UUID);

-- Check campaign completion calculation
SELECT calculate_campaign_completion('00000000-0000-0000-0000-000000000000'::UUID);

-- Check RLS policies
SELECT schemaname, tablename, policyname, roles, cmd, qual 
FROM pg_policies 
WHERE tablename LIKE 'campaign%';
*/