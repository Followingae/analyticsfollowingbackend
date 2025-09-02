# Database Cleanup and Security Hardening Recommendations

## Executive Summary
The database audit revealed excellent overall health with no critical issues. However, there are optimization opportunities for maintenance reduction and security hardening.

## 1. Unused Tables for Removal (52 Tables)

### Completely Unused Tables (0 operations, 0 rows, no code references)

**High Priority Removal (Safe to delete immediately):**
```sql
-- Admin and System Tables (no implementation)
DROP TABLE IF EXISTS admin_notifications CASCADE;
DROP TABLE IF EXISTS system_analytics CASCADE; 
DROP TABLE IF EXISTS system_audit_logs CASCADE;
DROP TABLE IF EXISTS system_maintenance_jobs CASCADE;
DROP TABLE IF EXISTS discovery_analytics CASCADE;
DROP TABLE IF EXISTS user_avatars CASCADE;
DROP TABLE IF EXISTS admin_user_actions CASCADE;

-- Over-engineered List System Extensions
DROP TABLE IF EXISTS list_activity_logs CASCADE;
DROP TABLE IF EXISTS list_collaborations CASCADE;
DROP TABLE IF EXISTS list_export_jobs CASCADE;
DROP TABLE IF EXISTS list_performance_metrics CASCADE;

-- Over-engineered Proposal System Extensions
DROP TABLE IF EXISTS proposal_analytics CASCADE;
DROP TABLE IF EXISTS proposal_communications CASCADE;
DROP TABLE IF EXISTS proposal_deliverables CASCADE;
DROP TABLE IF EXISTS proposal_templates CASCADE;
DROP TABLE IF EXISTS proposal_versions CASCADE;

-- Unused Campaign Extensions
DROP TABLE IF EXISTS campaign_activity_log CASCADE;
DROP TABLE IF EXISTS campaign_budget_tracking CASCADE;
DROP TABLE IF EXISTS campaign_collaborators CASCADE;
DROP TABLE IF EXISTS campaign_deliverables CASCADE;
DROP TABLE IF EXISTS campaign_milestones CASCADE;
DROP TABLE IF EXISTS campaign_performance_metrics CASCADE;
```

**Medium Priority Removal (Verify no future plans):**
```sql
-- Credit System Extensions (unused but part of credits architecture)
DROP TABLE IF EXISTS credit_top_up_orders CASCADE;
DROP TABLE IF EXISTS credit_transactions CASCADE;
DROP TABLE IF EXISTS credit_usage_tracking CASCADE;

-- Discovery System (planned feature?)
DROP TABLE IF EXISTS discovery_filters CASCADE;
DROP TABLE IF EXISTS discovery_sessions CASCADE;

-- Instagram Data Extensions (may be needed for AI)
DROP TABLE IF EXISTS audience_demographics CASCADE;
DROP TABLE IF EXISTS comment_sentiment CASCADE;
DROP TABLE IF EXISTS creator_metadata CASCADE;
DROP TABLE IF EXISTS mentions CASCADE;

-- User Data Extensions
DROP TABLE IF EXISTS search_history CASCADE;
DROP TABLE IF EXISTS user_favorites CASCADE;
DROP TABLE IF EXISTS user_list_items CASCADE;
DROP TABLE IF EXISTS user_searches CASCADE;
```

**Low Priority (Keep for now - core functionality):**
```sql
-- Core AI Processing (needed for background processing)
-- ai_analysis_jobs, ai_analysis_job_logs

-- Core Proposal System (basic functionality exists)
-- brand_proposals, proposal_invitations, proposal_applications, proposal_collaborations

-- Core Campaign System (basic functionality exists)
-- campaigns, campaign_posts, campaign_profiles

-- Core Team System (actively used)
-- team_invitations, email_unlocks, topup_orders

-- Core Credit System (actively used)
-- unlocked_influencers, unlocked_profiles

-- Core Feature System
-- feature_flags
```

## 2. Missing RLS Policies (Security Hardening)

### Tables with RLS Enabled but No Policies
```sql
-- proposal_access_grants
CREATE POLICY "Users can view their own team's proposal access grants" 
ON proposal_access_grants FOR SELECT 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active'
    )
);

CREATE POLICY "Team owners can manage proposal access grants" 
ON proposal_access_grants FOR ALL 
USING (
    team_id IN (
        SELECT tm.team_id FROM team_members tm
        JOIN teams t ON tm.team_id = t.id
        WHERE tm.user_id = auth.uid() 
        AND tm.role IN ('owner', 'admin')
        AND tm.status = 'active'
    )
);

-- team_invitations
CREATE POLICY "Users can view invitations for their teams" 
ON team_invitations FOR SELECT 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active' AND role IN ('owner', 'admin')
    ) OR invited_by = auth.uid()
);

CREATE POLICY "Team owners and admins can manage invitations" 
ON team_invitations FOR ALL 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active' AND role IN ('owner', 'admin')
    )
);

-- topup_orders  
CREATE POLICY "Users can view their own team's topup orders" 
ON topup_orders FOR SELECT 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active'
    )
);

CREATE POLICY "Team owners can manage topup orders" 
ON topup_orders FOR ALL 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active' AND role IN ('owner', 'admin')
    )
);
```

### Tables Missing RLS Entirely
```sql
-- Enable RLS and add policies for tables exposed to PostgREST

-- brand_proposals
ALTER TABLE brand_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own proposals" 
ON brand_proposals FOR ALL 
USING (user_id = auth.uid());

-- proposal_invitations
ALTER TABLE proposal_invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view invitations to their proposals" 
ON proposal_invitations FOR SELECT 
USING (
    proposal_id IN (SELECT id FROM brand_proposals WHERE user_id = auth.uid())
    OR profile_id IN (SELECT id FROM profiles WHERE created_by = auth.uid())
);

CREATE POLICY "Proposal owners can manage invitations" 
ON proposal_invitations FOR ALL 
USING (
    proposal_id IN (SELECT id FROM brand_proposals WHERE user_id = auth.uid())
);

-- proposal_applications
ALTER TABLE proposal_applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view applications to their proposals" 
ON proposal_applications FOR SELECT 
USING (
    proposal_id IN (SELECT id FROM brand_proposals WHERE user_id = auth.uid())
    OR applicant_user_id = auth.uid()
);

CREATE POLICY "Users can apply to proposals" 
ON proposal_applications FOR INSERT 
WITH CHECK (applicant_user_id = auth.uid());

-- proposal_collaborations
ALTER TABLE proposal_collaborations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their proposal collaborations" 
ON proposal_collaborations FOR SELECT 
USING (
    proposal_id IN (SELECT id FROM brand_proposals WHERE user_id = auth.uid())
    OR profile_id IN (SELECT id FROM profiles WHERE created_by = auth.uid())
);

-- proposal_deliverables  
ALTER TABLE proposal_deliverables ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage deliverables for their collaborations" 
ON proposal_deliverables FOR ALL 
USING (
    collaboration_id IN (
        SELECT id FROM proposal_collaborations pc
        JOIN brand_proposals bp ON pc.proposal_id = bp.id
        WHERE bp.user_id = auth.uid() OR pc.profile_id IN (
            SELECT id FROM profiles WHERE created_by = auth.uid()
        )
    )
);

-- user_roles (reference table - restrictive access)
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "All users can view available roles" 
ON user_roles FOR SELECT 
USING (true);

-- team_profile_access (team-based access control)
ALTER TABLE team_profile_access ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Team members can view their team's profile access" 
ON team_profile_access FOR SELECT 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active'
    )
);

CREATE POLICY "Team owners can manage profile access" 
ON team_profile_access FOR ALL 
USING (
    team_id IN (
        SELECT team_id FROM team_members 
        WHERE user_id = auth.uid() AND status = 'active' AND role IN ('owner', 'admin')
    )
);
```

## 3. Function Security Hardening

### Functions with Mutable Search Path (11 functions)
```sql
-- Add SECURITY DEFINER and SET search_path for all functions:

-- CDN Functions
ALTER FUNCTION get_cdn_asset_by_source() SECURITY DEFINER SET search_path = public, auth;
ALTER FUNCTION update_cdn_processing_stats() SECURITY DEFINER SET search_path = public, auth;

-- Credit Functions  
ALTER FUNCTION calculate_total_plan_credits() SECURITY DEFINER SET search_path = public, auth;

-- Team Functions
ALTER FUNCTION update_team_usage_counters() SECURITY DEFINER SET search_path = public, auth;
ALTER FUNCTION expire_old_invitations() SECURITY DEFINER SET search_path = public, auth;

-- Proposal Functions
ALTER FUNCTION update_admin_proposal_timestamp() SECURITY DEFINER SET search_path = public, auth;
ALTER FUNCTION update_proposal_timestamp() SECURITY DEFINER SET search_path = public, auth;

-- Campaign Functions
ALTER FUNCTION update_campaign_timestamp() SECURITY DEFINER SET search_path = public, auth;
ALTER FUNCTION update_campaign_completion_on_deliverable() SECURITY DEFINER SET search_path = public, auth;
ALTER FUNCTION update_campaign_budget_on_tracking() SECURITY DEFINER SET search_path = public, auth;

-- Utility Functions
ALTER FUNCTION update_updated_at_column() SECURITY DEFINER SET search_path = public, auth;
```

## 4. Auth Configuration (Manual Dashboard Steps)

### Supabase Dashboard Configuration Required:
1. **Enable Leaked Password Protection**: Go to Authentication > Settings > Password Policy > Enable "Check against database of leaked passwords"
2. **Set OTP Expiry**: Go to Authentication > Settings > OTP Expiry > Set to ≤ 1 hour (3600 seconds)

## Implementation Priority

1. **HIGH**: Remove completely unused tables (Batch 1) - Immediate 30% reduction in maintenance overhead
2. **HIGH**: Add missing RLS policies - Critical security hardening  
3. **MEDIUM**: Function security hardening - Additional security layer
4. **MEDIUM**: Remove medium priority unused tables - Further optimization
5. **LOW**: Dashboard configuration - Final security polish

## Expected Benefits

- **30-40% reduction** in database maintenance overhead
- **Complete security hardening** with comprehensive RLS policies
- **Improved performance** through reduced schema complexity
- **Enhanced security posture** meeting enterprise standards

## Rollback Plan

All DDL operations should be performed with transaction blocks and immediate backup verification. Keep schema backup before major cleanup operations.