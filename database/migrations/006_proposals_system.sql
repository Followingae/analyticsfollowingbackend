-- Migration: Proposals System - Brand Approval Workflow for Influencer Selection
-- Comprehensive brand workflow for influencer discovery, proposal creation, and collaboration management

BEGIN;

-- ============================================================================
-- 1. BRAND PROPOSALS TABLE
-- Core proposal system for brand campaigns and influencer selection
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.brand_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Proposal metadata
    proposal_title VARCHAR(300) NOT NULL,
    proposal_description TEXT NOT NULL,
    campaign_brief TEXT, -- Detailed campaign information
    brand_name VARCHAR(200) NOT NULL,
    brand_logo_url TEXT,
    
    -- Campaign details
    campaign_type VARCHAR(50) NOT NULL DEFAULT 'sponsored_post', -- sponsored_post, story, reel, ugc, event, ambassador
    campaign_goals JSONB DEFAULT '[]'::jsonb, -- ["brand_awareness", "sales", "engagement"]
    target_demographics JSONB DEFAULT '{}'::jsonb, -- Age, gender, location preferences
    
    -- Budget and compensation
    total_budget_usd INTEGER NOT NULL CHECK (total_budget_usd >= 0),
    budget_per_influencer_min INTEGER CHECK (budget_per_influencer_min >= 0),
    budget_per_influencer_max INTEGER CHECK (budget_per_influencer_max >= budget_per_influencer_min),
    compensation_type VARCHAR(50) DEFAULT 'paid', -- paid, barter, revenue_share, hybrid
    
    -- Timeline
    proposal_deadline TIMESTAMP WITH TIME ZONE,
    campaign_start_date TIMESTAMP WITH TIME ZONE,
    campaign_end_date TIMESTAMP WITH TIME ZONE,
    deliverables_due_date TIMESTAMP WITH TIME ZONE,
    
    -- Requirements and guidelines
    content_requirements JSONB DEFAULT '{}'::jsonb, -- Post specs, hashtags, mentions
    brand_guidelines TEXT, -- Brand voice, visual guidelines
    prohibited_content JSONB DEFAULT '[]'::jsonb, -- What not to include
    
    -- Proposal settings
    auto_approve_threshold INTEGER DEFAULT 0, -- Auto-approve if influencer meets criteria
    max_influencers INTEGER DEFAULT 50, -- Maximum number of influencers
    proposal_visibility VARCHAR(30) DEFAULT 'private', -- private, invite_only, public
    
    -- Status and workflow
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft, active, paused, completed, cancelled
    approval_required BOOLEAN DEFAULT true,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days')
);

-- Indexes for brand proposals
CREATE INDEX IF NOT EXISTS idx_brand_proposals_user ON brand_proposals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_brand_proposals_status ON brand_proposals(status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_brand_proposals_campaign_type ON brand_proposals(campaign_type, status);
CREATE INDEX IF NOT EXISTS idx_brand_proposals_budget ON brand_proposals(total_budget_usd, status);
CREATE INDEX IF NOT EXISTS idx_brand_proposals_deadline ON brand_proposals(proposal_deadline);
CREATE INDEX IF NOT EXISTS idx_brand_proposals_expires ON brand_proposals(expires_at);

-- ============================================================================
-- 2. PROPOSAL INFLUENCER INVITATIONS TABLE  
-- Track invited influencers and their proposal participation
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES brand_proposals(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    invited_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Invitation details
    invitation_message TEXT,
    custom_offer_usd INTEGER, -- Custom offer for this specific influencer
    custom_requirements JSONB DEFAULT '{}'::jsonb, -- Specific requirements for this influencer
    
    -- Status tracking
    invitation_status VARCHAR(50) DEFAULT 'pending', -- pending, accepted, declined, expired, withdrawn
    response_message TEXT, -- Influencer's response message
    
    -- Decision metadata
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    responded_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days'),
    
    -- Notification tracking
    email_sent BOOLEAN DEFAULT false,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    reminder_sent_count INTEGER DEFAULT 0,
    last_reminder_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    UNIQUE(proposal_id, profile_id)
);

-- Indexes for proposal invitations
CREATE INDEX IF NOT EXISTS idx_proposal_invitations_proposal ON proposal_invitations(proposal_id, invitation_status);
CREATE INDEX IF NOT EXISTS idx_proposal_invitations_profile ON proposal_invitations(profile_id, invitation_status);
CREATE INDEX IF NOT EXISTS idx_proposal_invitations_invited_by ON proposal_invitations(invited_by_user_id, invited_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_invitations_status ON proposal_invitations(invitation_status, invited_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_invitations_expires ON proposal_invitations(expires_at) WHERE invitation_status = 'pending';

-- ============================================================================
-- 3. PROPOSAL APPLICATIONS TABLE
-- Handle influencer applications to public proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES brand_proposals(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    applicant_user_id UUID REFERENCES users(id) ON DELETE SET NULL, -- The user who applied (if any)
    
    -- Application content
    application_message TEXT NOT NULL,
    portfolio_links JSONB DEFAULT '[]'::jsonb, -- Portfolio/previous work links
    proposed_content_ideas TEXT,
    requested_compensation_usd INTEGER,
    
    -- Application metadata
    application_status VARCHAR(50) DEFAULT 'pending', -- pending, under_review, approved, rejected, withdrawn
    brand_notes TEXT, -- Internal brand notes about this application
    
    -- Review process
    reviewed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_score INTEGER CHECK (review_score >= 1 AND review_score <= 10), -- 1-10 rating
    
    -- Timestamps
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(proposal_id, profile_id)
);

-- Indexes for proposal applications
CREATE INDEX IF NOT EXISTS idx_proposal_applications_proposal ON proposal_applications(proposal_id, application_status);
CREATE INDEX IF NOT EXISTS idx_proposal_applications_profile ON proposal_applications(profile_id, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_applications_applicant ON proposal_applications(applicant_user_id, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_applications_status ON proposal_applications(application_status, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_applications_score ON proposal_applications(review_score DESC) WHERE review_score IS NOT NULL;

-- ============================================================================
-- 4. PROPOSAL COLLABORATIONS TABLE
-- Track approved influencer collaborations and deliverables
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_collaborations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES brand_proposals(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Source of collaboration (from invitation or application)
    source_invitation_id UUID REFERENCES proposal_invitations(id) ON DELETE SET NULL,
    source_application_id UUID REFERENCES proposal_applications(id) ON DELETE SET NULL,
    
    -- Collaboration agreement
    agreed_compensation_usd INTEGER NOT NULL CHECK (agreed_compensation_usd >= 0),
    compensation_type VARCHAR(50) DEFAULT 'paid', -- paid, barter, revenue_share, hybrid
    agreed_deliverables JSONB NOT NULL DEFAULT '[]'::jsonb, -- What the influencer will deliver
    
    -- Contract and legal
    contract_signed BOOLEAN DEFAULT false,
    contract_signed_at TIMESTAMP WITH TIME ZONE,
    contract_url TEXT, -- Link to signed contract
    
    -- Performance tracking
    deliverables_submitted INTEGER DEFAULT 0,
    deliverables_approved INTEGER DEFAULT 0,
    deliverables_rejected INTEGER DEFAULT 0,
    
    -- Payment tracking
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, partial, completed, failed
    payment_amount_usd INTEGER DEFAULT 0,
    payment_date TIMESTAMP WITH TIME ZONE,
    payment_notes TEXT,
    
    -- Collaboration status
    collaboration_status VARCHAR(50) DEFAULT 'active', -- active, completed, cancelled, paused
    completion_date TIMESTAMP WITH TIME ZONE,
    
    -- Performance metrics
    estimated_reach INTEGER,
    actual_reach INTEGER,
    estimated_engagement INTEGER, 
    actual_engagement INTEGER,
    conversion_metrics JSONB DEFAULT '{}'::jsonb, -- CTR, sales, etc.
    
    -- Ratings and feedback
    brand_rating INTEGER CHECK (brand_rating >= 1 AND brand_rating <= 5),
    influencer_rating INTEGER CHECK (influencer_rating >= 1 AND influencer_rating <= 5),
    brand_feedback TEXT,
    influencer_feedback TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(proposal_id, profile_id),
    CHECK ((source_invitation_id IS NOT NULL AND source_application_id IS NULL) OR 
           (source_invitation_id IS NULL AND source_application_id IS NOT NULL))
);

-- Indexes for proposal collaborations
CREATE INDEX IF NOT EXISTS idx_proposal_collaborations_proposal ON proposal_collaborations(proposal_id, collaboration_status);
CREATE INDEX IF NOT EXISTS idx_proposal_collaborations_profile ON proposal_collaborations(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_collaborations_status ON proposal_collaborations(collaboration_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_collaborations_payment ON proposal_collaborations(payment_status, payment_date DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_collaborations_completion ON proposal_collaborations(completion_date DESC) WHERE completion_date IS NOT NULL;

-- ============================================================================
-- 5. PROPOSAL DELIVERABLES TABLE
-- Track specific deliverable items and their approval workflow
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_deliverables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collaboration_id UUID NOT NULL REFERENCES proposal_collaborations(id) ON DELETE CASCADE,
    
    -- Deliverable details
    deliverable_type VARCHAR(50) NOT NULL, -- post, story, reel, ugc_video, blog_post, review
    deliverable_title VARCHAR(300) NOT NULL,
    deliverable_description TEXT,
    
    -- Content specifications
    required_hashtags JSONB DEFAULT '[]'::jsonb,
    required_mentions JSONB DEFAULT '[]'::jsonb, 
    content_guidelines TEXT,
    
    -- Submission tracking
    submitted_content_url TEXT, -- Link to submitted content
    submitted_content_text TEXT, -- Text content for posts
    submitted_media_urls JSONB DEFAULT '[]'::jsonb, -- Media files
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    -- Approval workflow
    approval_status VARCHAR(50) DEFAULT 'pending', -- pending, submitted, under_review, approved, rejected, revision_requested
    reviewed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    
    -- Content performance (post-publication)
    published_at TIMESTAMP WITH TIME ZONE,
    published_url TEXT, -- Final published content URL
    performance_metrics JSONB DEFAULT '{}'::jsonb, -- Views, likes, comments, shares
    
    -- Timeline
    due_date TIMESTAMP WITH TIME ZONE,
    reminder_sent_count INTEGER DEFAULT 0,
    last_reminder_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for proposal deliverables
CREATE INDEX IF NOT EXISTS idx_proposal_deliverables_collaboration ON proposal_deliverables(collaboration_id, approval_status);
CREATE INDEX IF NOT EXISTS idx_proposal_deliverables_type ON proposal_deliverables(deliverable_type, approval_status);
CREATE INDEX IF NOT EXISTS idx_proposal_deliverables_status ON proposal_deliverables(approval_status, due_date);
CREATE INDEX IF NOT EXISTS idx_proposal_deliverables_due ON proposal_deliverables(due_date) WHERE approval_status IN ('pending', 'submitted');
CREATE INDEX IF NOT EXISTS idx_proposal_deliverables_reviewed ON proposal_deliverables(reviewed_by_user_id, reviewed_at DESC);

-- ============================================================================
-- 6. PROPOSAL ANALYTICS TABLE
-- Track proposal performance and engagement metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES brand_proposals(id) ON DELETE CASCADE,
    
    -- Time dimension
    date_recorded DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Invitation metrics
    total_invitations_sent INTEGER DEFAULT 0,
    invitations_accepted INTEGER DEFAULT 0,
    invitations_declined INTEGER DEFAULT 0,
    invitations_expired INTEGER DEFAULT 0,
    
    -- Application metrics  
    total_applications_received INTEGER DEFAULT 0,
    applications_approved INTEGER DEFAULT 0,
    applications_rejected INTEGER DEFAULT 0,
    applications_pending INTEGER DEFAULT 0,
    
    -- Collaboration metrics
    active_collaborations INTEGER DEFAULT 0,
    completed_collaborations INTEGER DEFAULT 0,
    cancelled_collaborations INTEGER DEFAULT 0,
    
    -- Deliverable metrics
    deliverables_submitted INTEGER DEFAULT 0,
    deliverables_approved INTEGER DEFAULT 0,
    deliverables_rejected INTEGER DEFAULT 0,
    deliverables_overdue INTEGER DEFAULT 0,
    
    -- Financial metrics
    total_spent_usd INTEGER DEFAULT 0,
    average_influencer_rate_usd INTEGER DEFAULT 0,
    
    -- Performance metrics
    total_estimated_reach INTEGER DEFAULT 0,
    total_actual_reach INTEGER DEFAULT 0,
    total_estimated_engagement INTEGER DEFAULT 0,
    total_actual_engagement INTEGER DEFAULT 0,
    
    -- Quality metrics
    average_brand_rating DECIMAL(3,2), -- Average rating given by brands
    average_influencer_rating DECIMAL(3,2), -- Average rating given by influencers
    content_approval_rate DECIMAL(5,2), -- Percentage of content approved on first submission
    
    -- Metadata
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Constraints
    UNIQUE(proposal_id, date_recorded)
);

-- Indexes for proposal analytics
CREATE INDEX IF NOT EXISTS idx_proposal_analytics_proposal_date ON proposal_analytics(proposal_id, date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_analytics_date ON proposal_analytics(date_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_analytics_performance ON proposal_analytics(total_actual_reach DESC, total_actual_engagement DESC);

-- ============================================================================
-- 7. PROPOSAL COMMUNICATION LOG TABLE
-- Track all communications related to proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.proposal_communications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES brand_proposals(id) ON DELETE CASCADE,
    
    -- Communication participants
    sender_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    recipient_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    recipient_profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL, -- For communications to influencers
    
    -- Communication details
    communication_type VARCHAR(50) NOT NULL, -- email, message, notification, system_update
    subject VARCHAR(300),
    message_content TEXT NOT NULL,
    
    -- Communication context
    related_invitation_id UUID REFERENCES proposal_invitations(id) ON DELETE SET NULL,
    related_application_id UUID REFERENCES proposal_applications(id) ON DELETE SET NULL,
    related_collaboration_id UUID REFERENCES proposal_collaborations(id) ON DELETE SET NULL,
    related_deliverable_id UUID REFERENCES proposal_deliverables(id) ON DELETE SET NULL,
    
    -- Delivery tracking
    delivery_status VARCHAR(50) DEFAULT 'pending', -- pending, sent, delivered, failed, read
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Ensure at least one recipient is specified
    CHECK ((recipient_user_id IS NOT NULL AND recipient_profile_id IS NULL) OR 
           (recipient_user_id IS NULL AND recipient_profile_id IS NOT NULL))
);

-- Indexes for proposal communications
CREATE INDEX IF NOT EXISTS idx_proposal_communications_proposal ON proposal_communications(proposal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_communications_sender ON proposal_communications(sender_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_communications_recipient_user ON proposal_communications(recipient_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_communications_recipient_profile ON proposal_communications(recipient_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposal_communications_delivery ON proposal_communications(delivery_status, sent_at DESC);

-- ============================================================================
-- 8. DATABASE FUNCTIONS FOR PROPOSALS SYSTEM
-- Optimized functions for common proposal operations
-- ============================================================================

-- Function to get proposal summary with key metrics
CREATE OR REPLACE FUNCTION public.get_proposal_summary(p_proposal_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_summary JSONB;
BEGIN
    SELECT jsonb_build_object(
        'proposal_id', bp.id,
        'proposal_title', bp.proposal_title,
        'status', bp.status,
        'total_budget_usd', bp.total_budget_usd,
        'created_at', bp.created_at,
        'expires_at', bp.expires_at,
        
        -- Invitation metrics
        'invitations_sent', COALESCE(inv_metrics.sent_count, 0),
        'invitations_accepted', COALESCE(inv_metrics.accepted_count, 0),
        'invitations_pending', COALESCE(inv_metrics.pending_count, 0),
        
        -- Application metrics
        'applications_received', COALESCE(app_metrics.received_count, 0),
        'applications_approved', COALESCE(app_metrics.approved_count, 0),
        'applications_pending', COALESCE(app_metrics.pending_count, 0),
        
        -- Collaboration metrics
        'active_collaborations', COALESCE(collab_metrics.active_count, 0),
        'completed_collaborations', COALESCE(collab_metrics.completed_count, 0),
        
        -- Financial metrics
        'total_committed_budget', COALESCE(collab_metrics.total_committed, 0),
        'budget_remaining', bp.total_budget_usd - COALESCE(collab_metrics.total_committed, 0)
    ) INTO v_summary
    FROM brand_proposals bp
    LEFT JOIN (
        SELECT 
            proposal_id,
            COUNT(*) as sent_count,
            COUNT(*) FILTER (WHERE invitation_status = 'accepted') as accepted_count,
            COUNT(*) FILTER (WHERE invitation_status = 'pending') as pending_count
        FROM proposal_invitations 
        WHERE proposal_id = p_proposal_id
        GROUP BY proposal_id
    ) inv_metrics ON bp.id = inv_metrics.proposal_id
    LEFT JOIN (
        SELECT 
            proposal_id,
            COUNT(*) as received_count,
            COUNT(*) FILTER (WHERE application_status = 'approved') as approved_count,
            COUNT(*) FILTER (WHERE application_status = 'pending') as pending_count
        FROM proposal_applications 
        WHERE proposal_id = p_proposal_id
        GROUP BY proposal_id
    ) app_metrics ON bp.id = app_metrics.proposal_id
    LEFT JOIN (
        SELECT 
            proposal_id,
            COUNT(*) FILTER (WHERE collaboration_status = 'active') as active_count,
            COUNT(*) FILTER (WHERE collaboration_status = 'completed') as completed_count,
            SUM(agreed_compensation_usd) as total_committed
        FROM proposal_collaborations 
        WHERE proposal_id = p_proposal_id
        GROUP BY proposal_id
    ) collab_metrics ON bp.id = collab_metrics.proposal_id
    WHERE bp.id = p_proposal_id;
    
    RETURN v_summary;
END;
$$;

-- Function to check proposal availability for influencer
CREATE OR REPLACE FUNCTION public.check_proposal_availability(
    p_proposal_id UUID,
    p_profile_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_proposal RECORD;
    v_existing_invitation RECORD;
    v_existing_application RECORD;
    v_existing_collaboration RECORD;
    v_result JSONB;
BEGIN
    -- Get proposal details
    SELECT * INTO v_proposal
    FROM brand_proposals 
    WHERE id = p_proposal_id;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object('available', false, 'reason', 'proposal_not_found');
    END IF;
    
    -- Check if proposal is active and not expired
    IF v_proposal.status != 'active' OR v_proposal.expires_at < CURRENT_TIMESTAMP THEN
        RETURN jsonb_build_object('available', false, 'reason', 'proposal_not_active');
    END IF;
    
    -- Check for existing invitation
    SELECT * INTO v_existing_invitation
    FROM proposal_invitations 
    WHERE proposal_id = p_proposal_id AND profile_id = p_profile_id;
    
    -- Check for existing application
    SELECT * INTO v_existing_application
    FROM proposal_applications 
    WHERE proposal_id = p_proposal_id AND profile_id = p_profile_id;
    
    -- Check for existing collaboration
    SELECT * INTO v_existing_collaboration
    FROM proposal_collaborations 
    WHERE proposal_id = p_proposal_id AND profile_id = p_profile_id;
    
    -- Build result
    v_result := jsonb_build_object(
        'available', true,
        'proposal_status', v_proposal.status,
        'expires_at', v_proposal.expires_at,
        'has_invitation', v_existing_invitation IS NOT NULL,
        'has_application', v_existing_application IS NOT NULL,
        'has_collaboration', v_existing_collaboration IS NOT NULL
    );
    
    IF v_existing_invitation IS NOT NULL THEN
        v_result := v_result || jsonb_build_object(
            'invitation_status', v_existing_invitation.invitation_status,
            'invitation_expires_at', v_existing_invitation.expires_at
        );
    END IF;
    
    IF v_existing_application IS NOT NULL THEN
        v_result := v_result || jsonb_build_object(
            'application_status', v_existing_application.application_status,
            'applied_at', v_existing_application.applied_at
        );
    END IF;
    
    IF v_existing_collaboration IS NOT NULL THEN
        v_result := v_result || jsonb_build_object(
            'collaboration_status', v_existing_collaboration.collaboration_status,
            'agreed_compensation_usd', v_existing_collaboration.agreed_compensation_usd
        );
    END IF;
    
    RETURN v_result;
END;
$$;

-- ============================================================================
-- 9. TRIGGERS FOR AUTOMATIC UPDATES
-- Maintain data consistency and automatic calculations
-- ============================================================================

-- Function to update proposal updated_at timestamp
CREATE OR REPLACE FUNCTION update_proposal_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for timestamp updates
CREATE TRIGGER trigger_brand_proposals_updated_at
    BEFORE UPDATE ON brand_proposals
    FOR EACH ROW EXECUTE FUNCTION update_proposal_timestamp();

CREATE TRIGGER trigger_proposal_applications_updated_at
    BEFORE UPDATE ON proposal_applications
    FOR EACH ROW EXECUTE FUNCTION update_proposal_timestamp();

CREATE TRIGGER trigger_proposal_collaborations_updated_at
    BEFORE UPDATE ON proposal_collaborations
    FOR EACH ROW EXECUTE FUNCTION update_proposal_timestamp();

CREATE TRIGGER trigger_proposal_deliverables_updated_at
    BEFORE UPDATE ON proposal_deliverables
    FOR EACH ROW EXECUTE FUNCTION update_proposal_timestamp();

-- ============================================================================
-- 10. ROW LEVEL SECURITY (RLS) POLICIES
-- Secure access to proposal data
-- ============================================================================

-- Enable RLS on all proposal tables
ALTER TABLE brand_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_collaborations ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_deliverables ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_communications ENABLE ROW LEVEL SECURITY;

-- Brand Proposals Policies
CREATE POLICY "brand_proposals_user_policy" ON brand_proposals
    FOR ALL TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "brand_proposals_service_policy" ON brand_proposals
    FOR ALL TO service_role USING (true);

-- Proposal Invitations Policies
CREATE POLICY "proposal_invitations_owner_policy" ON proposal_invitations
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM brand_proposals WHERE id = proposal_id
            UNION
            SELECT invited_by_user_id
        )
    );

CREATE POLICY "proposal_invitations_service_policy" ON proposal_invitations
    FOR ALL TO service_role USING (true);

-- Proposal Applications Policies  
CREATE POLICY "proposal_applications_owner_policy" ON proposal_applications
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM brand_proposals WHERE id = proposal_id
            UNION
            SELECT applicant_user_id
        )
    );

CREATE POLICY "proposal_applications_service_policy" ON proposal_applications
    FOR ALL TO service_role USING (true);

-- Proposal Collaborations Policies
CREATE POLICY "proposal_collaborations_participant_policy" ON proposal_collaborations
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM brand_proposals WHERE id = proposal_id
        )
    );

CREATE POLICY "proposal_collaborations_service_policy" ON proposal_collaborations
    FOR ALL TO service_role USING (true);

-- Proposal Deliverables Policies
CREATE POLICY "proposal_deliverables_participant_policy" ON proposal_deliverables
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT bp.user_id 
            FROM proposal_collaborations pc 
            JOIN brand_proposals bp ON pc.proposal_id = bp.id 
            WHERE pc.id = collaboration_id
        )
    );

CREATE POLICY "proposal_deliverables_service_policy" ON proposal_deliverables
    FOR ALL TO service_role USING (true);

-- Proposal Analytics Policies (Brand owners only)
CREATE POLICY "proposal_analytics_owner_policy" ON proposal_analytics
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM brand_proposals WHERE id = proposal_id
        )
    );

CREATE POLICY "proposal_analytics_service_policy" ON proposal_analytics
    FOR ALL TO service_role USING (true);

-- Proposal Communications Policies
CREATE POLICY "proposal_communications_participant_policy" ON proposal_communications
    FOR ALL TO authenticated USING (
        (SELECT auth.uid()) IN (
            SELECT user_id FROM brand_proposals WHERE id = proposal_id
            UNION
            SELECT sender_user_id
            UNION  
            SELECT recipient_user_id
        )
    );

CREATE POLICY "proposal_communications_service_policy" ON proposal_communications
    FOR ALL TO service_role USING (true);

COMMIT;

-- Verification queries (for manual checking)
/*
-- Check proposals system structure
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name LIKE 'proposal%' OR table_name LIKE 'brand_proposals'
ORDER BY table_name, ordinal_position;

-- Test proposal summary function
SELECT get_proposal_summary('00000000-0000-0000-0000-000000000000'::UUID);

-- Check RLS policies
SELECT schemaname, tablename, policyname, roles, cmd, qual 
FROM pg_policies 
WHERE tablename LIKE 'proposal%' OR tablename LIKE 'brand_proposals';
*/