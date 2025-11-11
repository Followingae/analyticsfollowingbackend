-- =====================================================
-- Campaign Enhancements & Proposals System Migration
-- Date: 2025-01-11
-- Description: Add missing fields to campaigns and implement complete proposals system
-- =====================================================

-- STEP 1: Enhance campaigns table with missing fields
ALTER TABLE campaigns
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2),
ADD COLUMN IF NOT EXISTS spent NUMERIC(12, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS start_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS end_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS tags TEXT[],
ADD COLUMN IF NOT EXISTS created_by VARCHAR(20) DEFAULT 'user',
ADD COLUMN IF NOT EXISTS proposal_id UUID,
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;

-- STEP 2: Update campaigns status constraint to include new statuses
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_status_check;
ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check
CHECK (status IN ('draft', 'active', 'paused', 'in_review', 'completed', 'archived'));

-- STEP 3: Create campaign_proposals table
CREATE TABLE IF NOT EXISTS campaign_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_by_admin_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Proposal details
    title VARCHAR(255) NOT NULL,
    campaign_name VARCHAR(255) NOT NULL,
    description TEXT,
    proposal_notes TEXT,
    proposal_type VARCHAR(50) DEFAULT 'influencer_list',

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'draft',

    -- Budget & metrics
    total_budget NUMERIC(12, 2),
    expected_reach BIGINT,
    avg_engagement_rate NUMERIC(5, 2),
    estimated_impressions BIGINT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    sent_at TIMESTAMP WITH TIME ZONE,
    responded_at TIMESTAMP WITH TIME ZONE,

    -- User response
    rejection_reason TEXT,

    -- Constraints
    CONSTRAINT proposal_status_check CHECK (status IN ('draft', 'sent', 'in_review', 'approved', 'rejected')),
    CONSTRAINT proposal_type_check CHECK (proposal_type IN ('influencer_list', 'campaign_package'))
);

-- STEP 4: Create proposal_influencers table
CREATE TABLE IF NOT EXISTS proposal_influencers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES campaign_proposals(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,

    -- Superadmin's suggestion
    estimated_cost NUMERIC(12, 2),
    suggested_by_admin BOOLEAN DEFAULT TRUE,

    -- User's selection
    selected_by_user BOOLEAN DEFAULT FALSE,
    selection_notes TEXT,

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    selected_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT unique_proposal_influencer UNIQUE (proposal_id, profile_id)
);

-- STEP 5: Add foreign key from campaigns to proposals
ALTER TABLE campaigns
ADD CONSTRAINT fk_campaigns_proposal_id
FOREIGN KEY (proposal_id) REFERENCES campaign_proposals(id) ON DELETE SET NULL;

-- STEP 6: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_campaigns_proposal_id ON campaigns(proposal_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_archived_at ON campaigns(archived_at);
CREATE INDEX IF NOT EXISTS idx_campaigns_created_by ON campaigns(created_by);

CREATE INDEX IF NOT EXISTS idx_proposals_user_id ON campaign_proposals(user_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON campaign_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON campaign_proposals(created_at);
CREATE INDEX IF NOT EXISTS idx_proposals_created_by_admin_id ON campaign_proposals(created_by_admin_id);

CREATE INDEX IF NOT EXISTS idx_proposal_influencers_proposal_id ON proposal_influencers(proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposal_influencers_profile_id ON proposal_influencers(profile_id);
CREATE INDEX IF NOT EXISTS idx_proposal_influencers_selected ON proposal_influencers(selected_by_user);

-- STEP 7: Add helpful comments
COMMENT ON TABLE campaign_proposals IS 'Campaign proposals from superadmin to users with suggested influencers';
COMMENT ON TABLE proposal_influencers IS 'Influencers suggested in proposals with user selection tracking';

COMMENT ON COLUMN campaigns.description IS 'Campaign description for frontend display';
COMMENT ON COLUMN campaigns.budget IS 'Total campaign budget';
COMMENT ON COLUMN campaigns.spent IS 'Amount spent so far on campaign';
COMMENT ON COLUMN campaigns.tags IS 'Campaign tags for organization and filtering';
COMMENT ON COLUMN campaigns.created_by IS 'user or superadmin - who created the campaign';
COMMENT ON COLUMN campaigns.proposal_id IS 'Link to proposal if campaign was created from approved proposal';
COMMENT ON COLUMN campaigns.archived_at IS 'When campaign was archived (soft delete)';

-- STEP 8: Create updated_at trigger for proposals
CREATE OR REPLACE FUNCTION update_campaign_proposal_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_campaign_proposal_updated_at
    BEFORE UPDATE ON campaign_proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_campaign_proposal_updated_at();

-- STEP 9: Enable RLS on new tables
ALTER TABLE campaign_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_influencers ENABLE ROW LEVEL SECURITY;

-- STEP 10: Create RLS policies for campaign_proposals
CREATE POLICY "Users can view their own proposals"
    ON campaign_proposals FOR SELECT
    USING (
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE id = campaign_proposals.user_id
        )
        OR
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE role IN ('admin', 'super_admin')
        )
    );

CREATE POLICY "Only admins can create proposals"
    ON campaign_proposals FOR INSERT
    WITH CHECK (
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE role IN ('admin', 'super_admin')
        )
    );

CREATE POLICY "Users and admins can update proposals"
    ON campaign_proposals FOR UPDATE
    USING (
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE id = campaign_proposals.user_id
        )
        OR
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE role IN ('admin', 'super_admin')
        )
    );

-- STEP 11: Create RLS policies for proposal_influencers
CREATE POLICY "Users can view influencers in their proposals"
    ON proposal_influencers FOR SELECT
    USING (
        proposal_id IN (
            SELECT id FROM campaign_proposals WHERE user_id IN (
                SELECT id FROM users WHERE supabase_user_id = auth.uid()::text
            )
        )
        OR
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE role IN ('admin', 'super_admin')
        )
    );

CREATE POLICY "Only admins can manage proposal influencers"
    ON proposal_influencers FOR ALL
    USING (
        auth.uid()::text IN (
            SELECT supabase_user_id FROM users WHERE role IN ('admin', 'super_admin')
        )
    );

-- =====================================================
-- Migration Complete
-- =====================================================
