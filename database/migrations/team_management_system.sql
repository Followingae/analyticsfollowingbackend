-- Team Management System - Professional B2B SaaS Team Collaboration
-- Analytics Following Platform - Industry Standard Team Features

-- =============================================================================
-- TEAM MANAGEMENT TABLES
-- =============================================================================

-- Teams table - Company/Organization level
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'free',
    subscription_status VARCHAR(50) NOT NULL DEFAULT 'active',
    subscription_expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Team limits based on subscription
    max_team_members INTEGER NOT NULL DEFAULT 1,
    monthly_profile_limit INTEGER NOT NULL DEFAULT 5,
    monthly_email_limit INTEGER NOT NULL DEFAULT 0,
    monthly_posts_limit INTEGER NOT NULL DEFAULT 0,
    
    -- Usage tracking
    profiles_used_this_month INTEGER NOT NULL DEFAULT 0,
    emails_used_this_month INTEGER NOT NULL DEFAULT 0,
    posts_used_this_month INTEGER NOT NULL DEFAULT 0,
    
    -- Billing cycle management
    billing_cycle_start DATE,
    billing_cycle_end DATE,
    
    -- Team settings
    settings JSONB NOT NULL DEFAULT '{}',
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    created_by UUID REFERENCES auth.users(id),
    
    -- Constraints
    CONSTRAINT valid_subscription_tier CHECK (subscription_tier IN ('free', 'standard', 'premium')),
    CONSTRAINT valid_subscription_status CHECK (subscription_status IN ('active', 'suspended', 'cancelled', 'past_due')),
    CONSTRAINT positive_limits CHECK (
        max_team_members > 0 AND 
        monthly_profile_limit >= 0 AND 
        monthly_email_limit >= 0 AND 
        monthly_posts_limit >= 0
    )
);

-- Team members table - Individual users within teams
CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Member role and permissions
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    permissions JSONB NOT NULL DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    last_active_at TIMESTAMP WITH TIME ZONE,
    
    -- Invitation details
    invited_by UUID REFERENCES auth.users(id),
    invitation_accepted_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT valid_member_role CHECK (role IN ('owner', 'admin', 'manager', 'member')),
    CONSTRAINT valid_member_status CHECK (status IN ('active', 'inactive', 'suspended')),
    CONSTRAINT unique_team_user UNIQUE(team_id, user_id)
);

-- Team invitations table - Pending team member invitations
CREATE TABLE team_invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    
    -- Invitation details
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by UUID NOT NULL REFERENCES auth.users(id),
    invitation_token VARCHAR(255) NOT NULL UNIQUE,
    
    -- Status and expiration
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    accepted_by UUID REFERENCES auth.users(id),
    
    -- Personal message
    personal_message TEXT,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT valid_invitation_role CHECK (role IN ('admin', 'manager', 'member')),
    CONSTRAINT valid_invitation_status CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    CONSTRAINT unique_team_email_pending UNIQUE(team_id, email, status) DEFERRABLE
);

-- =============================================================================
-- EMAIL UNLOCK TRACKING
-- =============================================================================

-- Email unlocks table - Track email access separately from profile analysis
CREATE TABLE email_unlocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Email data
    email_address VARCHAR(255),
    email_source VARCHAR(50) NOT NULL DEFAULT 'profile', -- 'profile', 'bio', 'contact_info'
    confidence_score FLOAT DEFAULT 0.0,
    
    -- Usage tracking
    unlocked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    billing_month DATE NOT NULL DEFAULT date_trunc('month', now()),
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT valid_email_source CHECK (email_source IN ('profile', 'bio', 'contact_info', 'external')),
    CONSTRAINT valid_confidence CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    CONSTRAINT unique_team_profile_email UNIQUE(team_id, profile_id, billing_month)
);

-- =============================================================================
-- SUBSCRIPTION LIMITS TRACKING
-- =============================================================================

-- Monthly usage tracking - More granular than team-level counters
CREATE TABLE monthly_usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Usage period
    billing_month DATE NOT NULL DEFAULT date_trunc('month', now()),
    
    -- Usage counters
    profiles_analyzed INTEGER NOT NULL DEFAULT 0,
    emails_unlocked INTEGER NOT NULL DEFAULT 0,
    posts_analyzed INTEGER NOT NULL DEFAULT 0,
    
    -- Last updated
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT unique_team_user_month UNIQUE(team_id, user_id, billing_month)
);

-- =============================================================================
-- TOPUP SYSTEM
-- =============================================================================

-- Topup orders table - Additional capacity purchases
CREATE TABLE topup_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    ordered_by UUID NOT NULL REFERENCES auth.users(id),
    
    -- Order details
    topup_type VARCHAR(50) NOT NULL, -- 'profiles', 'emails', 'posts'
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    discount_rate DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 20% for premium
    total_price DECIMAL(10,2) NOT NULL,
    
    -- Payment details
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    payment_method VARCHAR(100),
    payment_reference VARCHAR(255),
    
    -- Validity period
    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '1 month'),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    activated_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT valid_topup_type CHECK (topup_type IN ('profiles', 'emails', 'posts')),
    CONSTRAINT valid_payment_status CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
    CONSTRAINT valid_topup_status CHECK (status IN ('pending', 'active', 'expired', 'cancelled')),
    CONSTRAINT positive_quantities CHECK (quantity > 0 AND unit_price >= 0 AND total_price >= 0),
    CONSTRAINT valid_discount CHECK (discount_rate >= 0.00 AND discount_rate <= 100.00)
);

-- =============================================================================
-- PROPOSAL UNLOCK SYSTEM (Superadmin Only)
-- =============================================================================

-- Proposal access grants - Superadmin controlled
CREATE TABLE proposal_access_grants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    
    -- Grant details
    granted_by UUID NOT NULL REFERENCES auth.users(id), -- Must be superadmin
    granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    
    -- Access details
    access_level VARCHAR(50) NOT NULL DEFAULT 'full', -- 'read', 'write', 'full'
    expires_at TIMESTAMP WITH TIME ZONE, -- NULL for permanent access
    
    -- Grant reason and notes
    reason TEXT NOT NULL,
    internal_notes TEXT,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by UUID REFERENCES auth.users(id),
    revoked_reason TEXT,
    
    -- Constraints
    CONSTRAINT valid_access_level CHECK (access_level IN ('read', 'write', 'full')),
    CONSTRAINT valid_grant_status CHECK (status IN ('active', 'revoked', 'expired'))
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

-- Teams indexes
CREATE INDEX idx_teams_subscription_tier ON teams(subscription_tier);
CREATE INDEX idx_teams_subscription_status ON teams(subscription_status);
CREATE INDEX idx_teams_billing_cycle ON teams(billing_cycle_start, billing_cycle_end);

-- Team members indexes
CREATE INDEX idx_team_members_team_id ON team_members(team_id);
CREATE INDEX idx_team_members_user_id ON team_members(user_id);
CREATE INDEX idx_team_members_role ON team_members(role);
CREATE INDEX idx_team_members_status ON team_members(status);

-- Team invitations indexes
CREATE INDEX idx_team_invitations_team_id ON team_invitations(team_id);
CREATE INDEX idx_team_invitations_email ON team_invitations(email);
CREATE INDEX idx_team_invitations_status ON team_invitations(status);
CREATE INDEX idx_team_invitations_expires_at ON team_invitations(expires_at);

-- Email unlocks indexes
CREATE INDEX idx_email_unlocks_team_id ON email_unlocks(team_id);
CREATE INDEX idx_email_unlocks_user_id ON email_unlocks(user_id);
CREATE INDEX idx_email_unlocks_profile_id ON email_unlocks(profile_id);
CREATE INDEX idx_email_unlocks_billing_month ON email_unlocks(billing_month);

-- Usage tracking indexes
CREATE INDEX idx_usage_tracking_team_month ON monthly_usage_tracking(team_id, billing_month);
CREATE INDEX idx_usage_tracking_user_month ON monthly_usage_tracking(user_id, billing_month);

-- Topup orders indexes
CREATE INDEX idx_topup_orders_team_id ON topup_orders(team_id);
CREATE INDEX idx_topup_orders_status ON topup_orders(status);
CREATE INDEX idx_topup_orders_valid_period ON topup_orders(valid_from, valid_until);

-- Proposal access indexes
CREATE INDEX idx_proposal_access_team_id ON proposal_access_grants(team_id);
CREATE INDEX idx_proposal_access_status ON proposal_access_grants(status);

-- =============================================================================
-- ROW LEVEL SECURITY POLICIES
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_unlocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_usage_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE topup_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_access_grants ENABLE ROW LEVEL SECURITY;

-- Teams policies
CREATE POLICY "Users can view their own team" ON teams
    FOR SELECT USING (
        id IN (
            SELECT team_id FROM team_members 
            WHERE user_id = (SELECT auth.uid()) AND status = 'active'
        )
    );

CREATE POLICY "Team owners can update their team" ON teams
    FOR UPDATE USING (
        id IN (
            SELECT team_id FROM team_members 
            WHERE user_id = (SELECT auth.uid()) AND role IN ('owner', 'admin') AND status = 'active'
        )
    );

-- Team members policies
CREATE POLICY "Users can view their team members" ON team_members
    FOR SELECT USING (
        team_id IN (
            SELECT team_id FROM team_members 
            WHERE user_id = (SELECT auth.uid()) AND status = 'active'
        )
    );

-- Email unlocks policies
CREATE POLICY "Users can view their team's email unlocks" ON email_unlocks
    FOR SELECT USING (
        team_id IN (
            SELECT team_id FROM team_members 
            WHERE user_id = (SELECT auth.uid()) AND status = 'active'
        )
    );

-- Usage tracking policies
CREATE POLICY "Users can view their team's usage" ON monthly_usage_tracking
    FOR SELECT USING (
        team_id IN (
            SELECT team_id FROM team_members 
            WHERE user_id = (SELECT auth.uid()) AND status = 'active'
        )
    );

-- Additional policies for other tables following similar pattern...

-- =============================================================================
-- TRIGGER FUNCTIONS FOR AUTOMATIC UPDATES
-- =============================================================================

-- Function to update team usage counters
CREATE OR REPLACE FUNCTION update_team_usage_counters()
RETURNS TRIGGER AS $$
BEGIN
    -- Update team-level counters when usage tracking changes
    UPDATE teams SET
        profiles_used_this_month = (
            SELECT COALESCE(SUM(profiles_analyzed), 0) 
            FROM monthly_usage_tracking 
            WHERE team_id = NEW.team_id AND billing_month = date_trunc('month', now())
        ),
        emails_used_this_month = (
            SELECT COALESCE(SUM(emails_unlocked), 0) 
            FROM monthly_usage_tracking 
            WHERE team_id = NEW.team_id AND billing_month = date_trunc('month', now())
        ),
        posts_used_this_month = (
            SELECT COALESCE(SUM(posts_analyzed), 0) 
            FROM monthly_usage_tracking 
            WHERE team_id = NEW.team_id AND billing_month = date_trunc('month', now())
        ),
        updated_at = now()
    WHERE id = NEW.team_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for team usage updates
CREATE TRIGGER trigger_update_team_usage
    AFTER INSERT OR UPDATE ON monthly_usage_tracking
    FOR EACH ROW
    EXECUTE FUNCTION update_team_usage_counters();

-- Function to automatically expire invitations
CREATE OR REPLACE FUNCTION expire_old_invitations()
RETURNS void AS $$
BEGIN
    UPDATE team_invitations 
    SET status = 'expired', updated_at = now()
    WHERE status = 'pending' AND expires_at < now();
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SUBSCRIPTION TIER CONFIGURATION
-- =============================================================================

-- Insert default subscription configurations
INSERT INTO teams (id, name, subscription_tier, max_team_members, monthly_profile_limit, monthly_email_limit, monthly_posts_limit) VALUES
-- Free tier template (for reference)
('00000000-0000-0000-0000-000000000001', 'Free Tier Template', 'free', 1, 5, 0, 0),
-- Standard tier template 
('00000000-0000-0000-0000-000000000002', 'Standard Tier Template', 'standard', 2, 500, 250, 125),
-- Premium tier template
('00000000-0000-0000-0000-000000000003', 'Premium Tier Template', 'premium', 5, 2000, 800, 300);

COMMENT ON TABLE teams IS 'Company/Organization level team management with subscription-based limits';
COMMENT ON TABLE team_members IS 'Individual users within teams with role-based permissions';
COMMENT ON TABLE team_invitations IS 'Pending team member invitations with expiration management';
COMMENT ON TABLE email_unlocks IS 'Email unlock tracking separate from profile analysis';
COMMENT ON TABLE monthly_usage_tracking IS 'Granular monthly usage tracking per team member';
COMMENT ON TABLE topup_orders IS 'Additional capacity purchases with discount support';
COMMENT ON TABLE proposal_access_grants IS 'Superadmin-controlled proposal access for agency clients';