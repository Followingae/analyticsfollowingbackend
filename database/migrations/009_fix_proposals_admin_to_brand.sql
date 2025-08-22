-- Migration: Fix Proposals System - Admin to Brand Workflow
-- Corrects the proposal system to be between Admin (us) and Brands (users), not involving influencers

BEGIN;

-- ============================================================================
-- 1. DROP EXISTING TABLES IN CORRECT ORDER (respecting foreign key dependencies)
-- ============================================================================

DROP TABLE IF EXISTS public.proposal_communications CASCADE;
DROP TABLE IF EXISTS public.proposal_analytics CASCADE;
DROP TABLE IF EXISTS public.proposal_deliverables CASCADE;
DROP TABLE IF EXISTS public.proposal_collaborations CASCADE;
DROP TABLE IF EXISTS public.proposal_applications CASCADE;
DROP TABLE IF EXISTS public.proposal_invitations CASCADE;
DROP TABLE IF EXISTS public.brand_proposals CASCADE;

-- ============================================================================
-- 2. ADMIN BRAND PROPOSALS TABLE
-- Core proposal system where Admin creates proposals for Brands
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.admin_brand_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Target brand (user)
    brand_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Admin who created the proposal
    created_by_admin_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Proposal metadata
    proposal_title VARCHAR(300) NOT NULL,
    proposal_description TEXT NOT NULL,
    executive_summary TEXT, -- High-level proposal summary
    
    -- Service offering details
    service_type VARCHAR(100) NOT NULL DEFAULT 'influencer_marketing', -- influencer_marketing, content_creation, brand_strategy, campaign_management
    service_description TEXT NOT NULL,
    deliverables JSONB NOT NULL DEFAULT '[]'::jsonb, -- What we will deliver
    
    -- Proposed timeline
    proposed_start_date DATE,
    proposed_end_date DATE,
    estimated_duration_days INTEGER,
    
    -- Pricing and budget
    proposed_budget_usd INTEGER NOT NULL CHECK (proposed_budget_usd >= 0),
    budget_breakdown JSONB DEFAULT '{}'::jsonb, -- Detailed cost breakdown
    payment_terms VARCHAR(100) DEFAULT 'net_30', -- net_30, net_15, upfront, milestone
    
    -- Campaign specifics (if applicable)
    campaign_objectives JSONB DEFAULT '[]'::jsonb, -- ["brand_awareness", "lead_generation", "sales"]
    target_audience_description TEXT,
    expected_deliverables JSONB DEFAULT '[]'::jsonb, -- Expected campaign outcomes
    
    -- Performance metrics we'll track
    success_metrics JSONB DEFAULT '[]'::jsonb, -- KPIs we'll measure
    expected_results TEXT, -- What results we expect to deliver
    
    -- Proposal status and workflow
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft, sent, under_review, approved, rejected, negotiation, closed
    priority_level VARCHAR(20) DEFAULT 'medium', -- high, medium, low
    
    -- Brand response tracking
    brand_viewed_at TIMESTAMP WITH TIME ZONE,
    brand_response_due_date TIMESTAMP WITH TIME ZONE,
    brand_decision VARCHAR(50), -- approved, rejected, counter_proposal, needs_clarification
    brand_feedback TEXT, -- Brand's feedback/concerns
    brand_counter_proposal JSONB DEFAULT '{}'::jsonb, -- Brand's counter-offer
    
    -- Follow-up and communication
    last_contact_date TIMESTAMP WITH TIME ZONE,
    next_follow_up_date TIMESTAMP WITH TIME ZONE,
    contact_attempts INTEGER DEFAULT 0,
    
    -- Internal admin notes
    admin_notes TEXT, -- Internal notes not visible to brand
    tags JSONB DEFAULT '[]'::jsonb, -- Tags for organization
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE, -- When proposal was sent to brand
    responded_at TIMESTAMP WITH TIME ZONE, -- When brand responded
    closed_at TIMESTAMP WITH TIME ZONE -- When proposal was closed (approved/rejected)
);

-- Indexes for admin brand proposals
CREATE INDEX idx_admin_brand_proposals_brand_user ON admin_brand_proposals(brand_user_id, created_at DESC);
CREATE INDEX idx_admin_brand_proposals_admin ON admin_brand_proposals(created_by_admin_id, created_at DESC);
CREATE INDEX idx_admin_brand_proposals_status ON admin_brand_proposals(status, priority_level, created_at DESC);
CREATE INDEX idx_admin_brand_proposals_service_type ON admin_brand_proposals(service_type, status);
CREATE INDEX idx_admin_brand_proposals_budget ON admin_brand_proposals(proposed_budget_usd, status);
CREATE INDEX idx_admin_brand_proposals_timeline ON admin_brand_proposals(proposed_start_date, proposed_end_date);
CREATE INDEX idx_admin_brand_proposals_follow_up ON admin_brand_proposals(next_follow_up_date) WHERE next_follow_up_date IS NOT NULL;

-- ============================================================================
-- 3. PROPOSAL VERSIONS TABLE
-- Track different versions/iterations of proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES admin_brand_proposals(id) ON DELETE CASCADE,
    
    -- Version information
    version_number INTEGER NOT NULL DEFAULT 1,
    version_description TEXT, -- What changed in this version
    created_by_admin_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Snapshot of proposal data at this version
    proposal_data JSONB NOT NULL, -- Complete proposal data snapshot
    changes_made JSONB DEFAULT '[]'::jsonb, -- List of changes made
    
    -- Version metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_current_version BOOLEAN DEFAULT false,
    
    -- Constraints
    UNIQUE(proposal_id, version_number)
);

-- Indexes for proposal versions
CREATE INDEX idx_proposal_versions_proposal ON proposal_versions(proposal_id, version_number DESC);
CREATE INDEX idx_proposal_versions_admin ON proposal_versions(created_by_admin_id, created_at DESC);
CREATE INDEX idx_proposal_versions_current ON proposal_versions(proposal_id) WHERE is_current_version = true;

-- ============================================================================
-- 4. PROPOSAL COMMUNICATIONS TABLE
-- Track all communications between admin and brand regarding proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_communications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES admin_brand_proposals(id) ON DELETE CASCADE,
    
    -- Communication participants
    sender_admin_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    sender_is_brand BOOLEAN DEFAULT false, -- true if brand sent this communication
    
    -- Communication details
    communication_type VARCHAR(50) NOT NULL, -- email, phone_call, meeting, message, document_shared
    subject VARCHAR(300),
    message_content TEXT NOT NULL,
    
    -- Meeting/call specifics
    meeting_type VARCHAR(50), -- video_call, phone_call, in_person, presentation
    meeting_duration_minutes INTEGER,
    meeting_attendees JSONB DEFAULT '[]'::jsonb,
    
    -- Document/file sharing
    shared_documents JSONB DEFAULT '[]'::jsonb, -- Links to shared documents
    
    -- Follow-up actions
    action_items JSONB DEFAULT '[]'::jsonb, -- Action items from this communication
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date TIMESTAMP WITH TIME ZONE,
    
    -- Communication status
    delivery_status VARCHAR(50) DEFAULT 'sent', -- sent, delivered, read, responded
    brand_response_required BOOLEAN DEFAULT false,
    brand_responded BOOLEAN DEFAULT false,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    scheduled_for TIMESTAMP WITH TIME ZONE, -- For scheduled communications
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for proposal communications
CREATE INDEX idx_proposal_communications_proposal ON proposal_communications(proposal_id, created_at DESC);
CREATE INDEX idx_proposal_communications_admin ON proposal_communications(sender_admin_id, created_at DESC);
CREATE INDEX idx_proposal_communications_type ON proposal_communications(communication_type, created_at DESC);
CREATE INDEX idx_proposal_communications_follow_up ON proposal_communications(follow_up_date) WHERE follow_up_required = true;

-- ============================================================================
-- 5. PROPOSAL ANALYTICS TABLE
-- Track proposal performance and conversion metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES admin_brand_proposals(id) ON DELETE CASCADE,
    
    -- Time dimension
    date_recorded DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Proposal lifecycle metrics
    days_in_draft INTEGER DEFAULT 0,
    days_sent_to_brand INTEGER DEFAULT 0,
    days_under_review INTEGER DEFAULT 0,
    days_in_negotiation INTEGER DEFAULT 0,
    time_to_decision_days INTEGER, -- Time from sent to decision
    
    -- Communication metrics
    total_communications INTEGER DEFAULT 0,
    admin_initiated_communications INTEGER DEFAULT 0,
    brand_initiated_communications INTEGER DEFAULT 0,
    meetings_held INTEGER DEFAULT 0,
    documents_shared INTEGER DEFAULT 0,
    
    -- Engagement metrics
    proposal_views INTEGER DEFAULT 0, -- How many times brand viewed proposal
    time_spent_reviewing_minutes INTEGER DEFAULT 0,
    sections_viewed JSONB DEFAULT '[]'::jsonb, -- Which sections were viewed
    
    -- Conversion funnel
    conversion_stage VARCHAR(50) DEFAULT 'created', -- created, sent, viewed, responded, negotiated, decided
    conversion_probability DECIMAL(5,2), -- Estimated probability of conversion (0-100)
    
    -- Financial metrics
    proposed_value_usd INTEGER DEFAULT 0,
    negotiated_value_usd INTEGER DEFAULT 0,
    discount_amount_usd INTEGER DEFAULT 0,
    discount_percentage DECIMAL(5,2),
    
    -- Outcome metrics (if closed)
    final_decision VARCHAR(50), -- approved, rejected, withdrawn
    rejection_reason VARCHAR(100), -- budget, timeline, services, competition, internal_decision
    win_reason VARCHAR(100), -- price, services, relationship, expertise, timeline
    
    -- Metadata
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(proposal_id, date_recorded)
);

-- Indexes for proposal analytics
CREATE INDEX idx_proposal_analytics_proposal_date ON proposal_analytics(proposal_id, date_recorded DESC);
CREATE INDEX idx_proposal_analytics_stage ON proposal_analytics(conversion_stage, date_recorded DESC);
CREATE INDEX idx_proposal_analytics_probability ON proposal_analytics(conversion_probability DESC);
CREATE INDEX idx_proposal_analytics_value ON proposal_analytics(proposed_value_usd DESC);

-- ============================================================================
-- 6. PROPOSAL TEMPLATES TABLE
-- Store reusable proposal templates for different service types
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Template metadata
    template_name VARCHAR(200) NOT NULL,
    template_description TEXT,
    service_type VARCHAR(100) NOT NULL,
    
    -- Template content
    template_structure JSONB NOT NULL, -- Complete proposal template structure
    default_budget_range JSONB DEFAULT '{}'::jsonb, -- {"min": 5000, "max": 25000}
    default_timeline_days INTEGER,
    
    -- Template settings
    is_active BOOLEAN DEFAULT true,
    usage_count INTEGER DEFAULT 0,
    created_by_admin_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Template categories and tags
    category VARCHAR(100), -- standard, premium, enterprise, custom
    tags JSONB DEFAULT '[]'::jsonb,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for proposal templates
CREATE INDEX idx_proposal_templates_service_type ON proposal_templates(service_type, is_active);
CREATE INDEX idx_proposal_templates_category ON proposal_templates(category, is_active);
CREATE INDEX idx_proposal_templates_usage ON proposal_templates(usage_count DESC);
CREATE INDEX idx_proposal_templates_creator ON proposal_templates(created_by_admin_id, created_at DESC);

-- ============================================================================
-- 7. DATABASE FUNCTIONS FOR ADMIN-BRAND PROPOSALS
-- ============================================================================

-- Function to get comprehensive proposal metrics
CREATE OR REPLACE FUNCTION public.get_admin_proposal_metrics(p_proposal_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_metrics JSONB;
BEGIN
    SELECT jsonb_build_object(
        'proposal_id', abp.id,
        'proposal_title', abp.proposal_title,
        'status', abp.status,
        'proposed_budget_usd', abp.proposed_budget_usd,
        'service_type', abp.service_type,
        'created_at', abp.created_at,
        'sent_at', abp.sent_at,
        'responded_at', abp.responded_at,
        
        -- Timeline metrics
        'days_since_created', COALESCE(DATE_PART('day', CURRENT_TIMESTAMP - abp.created_at), 0),
        'days_since_sent', CASE 
            WHEN abp.sent_at IS NOT NULL 
            THEN DATE_PART('day', CURRENT_TIMESTAMP - abp.sent_at)
            ELSE NULL 
        END,
        'days_to_response', CASE 
            WHEN abp.sent_at IS NOT NULL AND abp.responded_at IS NOT NULL 
            THEN DATE_PART('day', abp.responded_at - abp.sent_at)
            ELSE NULL 
        END,
        
        -- Communication metrics
        'total_communications', COALESCE(comm_metrics.total_comms, 0),
        'admin_communications', COALESCE(comm_metrics.admin_comms, 0),
        'brand_communications', COALESCE(comm_metrics.brand_comms, 0),
        'last_communication_date', comm_metrics.last_comm_date,
        
        -- Engagement metrics
        'proposal_viewed', abp.brand_viewed_at IS NOT NULL,
        'brand_viewed_at', abp.brand_viewed_at,
        'versions_created', COALESCE(version_metrics.version_count, 1),
        
        -- Status flags
        'is_overdue', CASE 
            WHEN abp.brand_response_due_date IS NOT NULL AND abp.brand_response_due_date < CURRENT_TIMESTAMP 
            THEN true 
            ELSE false 
        END,
        'needs_follow_up', abp.next_follow_up_date IS NOT NULL AND abp.next_follow_up_date <= CURRENT_TIMESTAMP
        
    ) INTO v_metrics
    FROM admin_brand_proposals abp
    LEFT JOIN (
        SELECT 
            proposal_id,
            COUNT(*) as total_comms,
            COUNT(*) FILTER (WHERE sender_is_brand = false) as admin_comms,
            COUNT(*) FILTER (WHERE sender_is_brand = true) as brand_comms,
            MAX(created_at) as last_comm_date
        FROM proposal_communications 
        WHERE proposal_id = p_proposal_id
        GROUP BY proposal_id
    ) comm_metrics ON abp.id = comm_metrics.proposal_id
    LEFT JOIN (
        SELECT 
            proposal_id,
            COUNT(*) as version_count
        FROM proposal_versions 
        WHERE proposal_id = p_proposal_id
        GROUP BY proposal_id
    ) version_metrics ON abp.id = version_metrics.proposal_id
    WHERE abp.id = p_proposal_id;
    
    RETURN v_metrics;
END;
$$;

-- Function to get proposal pipeline summary
CREATE OR REPLACE FUNCTION public.get_proposal_pipeline_summary()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_summary JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_proposals', COUNT(*),
        'draft_proposals', COUNT(*) FILTER (WHERE status = 'draft'),
        'sent_proposals', COUNT(*) FILTER (WHERE status = 'sent'),
        'under_review', COUNT(*) FILTER (WHERE status = 'under_review'),
        'in_negotiation', COUNT(*) FILTER (WHERE status = 'negotiation'),
        'approved_proposals', COUNT(*) FILTER (WHERE status = 'approved'),
        'rejected_proposals', COUNT(*) FILTER (WHERE status = 'rejected'),
        
        -- Financial metrics
        'total_proposed_value', SUM(proposed_budget_usd) FILTER (WHERE status IN ('sent', 'under_review', 'negotiation')),
        'approved_value', SUM(proposed_budget_usd) FILTER (WHERE status = 'approved'),
        
        -- Conversion metrics
        'conversion_rate', CASE 
            WHEN COUNT(*) FILTER (WHERE status IN ('sent', 'under_review', 'negotiation', 'approved', 'rejected')) > 0
            THEN ROUND(
                COUNT(*) FILTER (WHERE status = 'approved')::decimal / 
                COUNT(*) FILTER (WHERE status IN ('sent', 'under_review', 'negotiation', 'approved', 'rejected'))::decimal * 100, 2
            )
            ELSE 0 
        END,
        
        -- Activity metrics
        'proposals_sent_this_month', COUNT(*) FILTER (WHERE sent_at >= DATE_TRUNC('month', CURRENT_TIMESTAMP)),
        'responses_received_this_month', COUNT(*) FILTER (WHERE responded_at >= DATE_TRUNC('month', CURRENT_TIMESTAMP)),
        
        -- Follow-up metrics
        'proposals_needing_follow_up', COUNT(*) FILTER (WHERE next_follow_up_date IS NOT NULL AND next_follow_up_date <= CURRENT_TIMESTAMP),
        'overdue_responses', COUNT(*) FILTER (WHERE brand_response_due_date IS NOT NULL AND brand_response_due_date < CURRENT_TIMESTAMP AND status IN ('sent', 'under_review'))
        
    ) INTO v_summary
    FROM admin_brand_proposals;
    
    RETURN v_summary;
END;
$$;

-- ============================================================================
-- 8. TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Function to update proposal updated_at timestamp
CREATE OR REPLACE FUNCTION update_admin_proposal_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for timestamp updates
CREATE TRIGGER trigger_admin_brand_proposals_updated_at
    BEFORE UPDATE ON admin_brand_proposals
    FOR EACH ROW EXECUTE FUNCTION update_admin_proposal_timestamp();

CREATE TRIGGER trigger_proposal_versions_updated_at
    BEFORE UPDATE ON proposal_templates
    FOR EACH ROW EXECUTE FUNCTION update_admin_proposal_timestamp();

-- ============================================================================
-- 9. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE admin_brand_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_communications ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_templates ENABLE ROW LEVEL SECURITY;

-- Admin Brand Proposals Policies (Brands can see their own proposals)
CREATE POLICY "admin_brand_proposals_brand_policy" ON admin_brand_proposals
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = brand_user_id);

CREATE POLICY "admin_brand_proposals_admin_policy" ON admin_brand_proposals
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT id FROM auth.users 
            WHERE raw_user_meta_data->>'role' = 'admin' 
               OR raw_user_meta_data->>'role' = 'superadmin'
        )
    );

CREATE POLICY "admin_brand_proposals_service_policy" ON admin_brand_proposals
    FOR ALL TO service_role USING (true);

-- Proposal Versions Policies (Admin only)
CREATE POLICY "proposal_versions_admin_policy" ON proposal_versions
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT id FROM auth.users 
            WHERE raw_user_meta_data->>'role' = 'admin' 
               OR raw_user_meta_data->>'role' = 'superadmin'
        )
    );

CREATE POLICY "proposal_versions_service_policy" ON proposal_versions
    FOR ALL TO service_role USING (true);

-- Proposal Communications Policies (Both admin and brand can see)
CREATE POLICY "proposal_communications_participant_policy" ON proposal_communications
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT brand_user_id FROM admin_brand_proposals WHERE id = proposal_id
            UNION
            SELECT sender_admin_id
            UNION
            SELECT id FROM auth.users 
            WHERE raw_user_meta_data->>'role' = 'admin' 
               OR raw_user_meta_data->>'role' = 'superadmin'
        )
    );

CREATE POLICY "proposal_communications_service_policy" ON proposal_communications
    FOR ALL TO service_role USING (true);

-- Proposal Analytics Policies (Admin only)
CREATE POLICY "proposal_analytics_admin_policy" ON proposal_analytics
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT id FROM auth.users 
            WHERE raw_user_meta_data->>'role' = 'admin' 
               OR raw_user_meta_data->>'role' = 'superadmin'
        )
    );

CREATE POLICY "proposal_analytics_service_policy" ON proposal_analytics
    FOR ALL TO service_role USING (true);

-- Proposal Templates Policies (Admin only)
CREATE POLICY "proposal_templates_admin_policy" ON proposal_templates
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT id FROM auth.users 
            WHERE raw_user_meta_data->>'role' = 'admin' 
               OR raw_user_meta_data->>'role' = 'superadmin'
        )
    );

CREATE POLICY "proposal_templates_service_policy" ON proposal_templates
    FOR ALL TO service_role USING (true);

COMMIT;

-- Verification queries (for manual checking)
/*
-- Check new proposals system structure
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name LIKE '%proposal%' OR table_name LIKE 'admin_brand_proposals'
ORDER BY table_name, ordinal_position;

-- Test proposal metrics function
SELECT get_admin_proposal_metrics('00000000-0000-0000-0000-000000000000'::UUID);

-- Test pipeline summary function
SELECT get_proposal_pipeline_summary();

-- Check RLS policies
SELECT schemaname, tablename, policyname, roles, cmd, qual 
FROM pg_policies 
WHERE tablename LIKE '%proposal%' OR tablename LIKE 'admin_brand_proposals';
*/