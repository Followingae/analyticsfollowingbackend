# Frontend Implementation Guide - Influencer Marketing Platform

Complete implementation guide for all enhanced systems in the influencer marketing platform. This covers database schemas, API endpoints, data models, and integration patterns for frontend development.

## Table of Contents
1. [Enhanced Lists System](#enhanced-lists-system)
2. [Proposals System](#proposals-system) 
3. [Campaign Enhancement](#campaign-enhancement)
4. [Superadmin Dashboard](#superadmin-dashboard)
5. [Common Patterns](#common-patterns)
6. [API Integration Examples](#api-integration-examples)

---

## Enhanced Lists System

### Overview
Build on existing favorites with full list management including collaboration, templates, analytics, and export capabilities.

### Database Schema

#### Core Tables
```sql
-- Enhanced user_lists table (existing table with new fields)
user_lists:
- id (UUID, Primary Key)
- user_id (UUID, FK to auth.users)
- list_name (VARCHAR(200))
- list_description (TEXT)
- list_type (VARCHAR(50)) -- 'custom', 'template', 'shared', 'favorites'
- is_public (BOOLEAN, default false)
- is_template (BOOLEAN, default false)
- template_category (VARCHAR(100))
- collaboration_settings (JSONB)
- export_settings (JSONB)
- performance_metrics (JSONB)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

-- New supporting tables
list_templates:
- id (UUID, Primary Key)
- template_name (VARCHAR(200))
- template_description (TEXT)
- template_category (VARCHAR(100))
- template_config (JSONB)
- is_public (BOOLEAN)
- usage_count (INTEGER)
- created_by (UUID, FK to auth.users)

list_collaborations:
- id (UUID, Primary Key)
- list_id (UUID, FK to user_lists)
- collaborator_user_id (UUID, FK to auth.users)
- permission_level (VARCHAR(20)) -- 'view', 'comment', 'edit', 'admin'
- collaboration_status (VARCHAR(20)) -- 'pending', 'accepted', 'declined'
- invited_by (UUID, FK to auth.users)
- invited_at (TIMESTAMP)
- responded_at (TIMESTAMP)

list_activity_logs:
- id (UUID, Primary Key)
- list_id (UUID, FK to user_lists)
- user_id (UUID, FK to auth.users)
- activity_type (VARCHAR(50))
- activity_description (TEXT)
- activity_data (JSONB)
- created_at (TIMESTAMP)

list_performance_metrics:
- id (UUID, Primary Key)
- list_id (UUID, FK to user_lists)
- date_recorded (DATE)
- views_count (INTEGER)
- shares_count (INTEGER)
- exports_count (INTEGER)
- collaboration_requests (INTEGER)
- engagement_score (FLOAT)
- metrics_data (JSONB)

list_export_jobs:
- id (UUID, Primary Key)
- list_id (UUID, FK to user_lists)
- user_id (UUID, FK to auth.users)
- export_format (VARCHAR(20)) -- 'csv', 'xlsx', 'pdf', 'json'
- export_status (VARCHAR(20)) -- 'pending', 'processing', 'completed', 'failed'
- file_url (TEXT)
- export_config (JSONB)
- created_at (TIMESTAMP)
- completed_at (TIMESTAMP)
```

### API Endpoints

#### List Management
```typescript
// Get user lists with filtering and pagination
GET /api/lists?page=1&limit=20&type=custom&search=fashion
Response: {
  lists: ListItem[],
  pagination: PaginationInfo,
  templates: ListTemplate[],
  collaboration_invites: CollaborationInvite[]
}

// Create new list
POST /api/lists
Body: {
  list_name: string,
  list_description?: string,
  list_type: 'custom' | 'template' | 'shared',
  is_public?: boolean,
  collaboration_settings?: CollaborationSettings,
  template_id?: string
}

// Update list
PUT /api/lists/{listId}
Body: {
  list_name?: string,
  list_description?: string,
  collaboration_settings?: CollaborationSettings,
  export_settings?: ExportSettings
}

// Delete list
DELETE /api/lists/{listId}
```

#### List Templates
```typescript
// Get available templates
GET /api/lists/templates?category=influencer_marketing
Response: {
  templates: ListTemplate[],
  categories: string[]
}

// Create template from list
POST /api/lists/{listId}/create-template
Body: {
  template_name: string,
  template_description: string,
  template_category: string,
  is_public: boolean
}

// Use template to create list
POST /api/lists/from-template/{templateId}
Body: {
  list_name: string,
  customizations?: TemplateCustomizations
}
```

#### List Collaboration
```typescript
// Share list with users
POST /api/lists/{listId}/share
Body: {
  collaborators: Array<{
    email: string,
    permission_level: 'view' | 'comment' | 'edit' | 'admin'
  }>,
  message?: string
}

// Respond to collaboration invite
PUT /api/lists/collaborations/{collaborationId}/respond
Body: {
  response: 'accepted' | 'declined',
  message?: string
}

// Update collaboration permissions
PUT /api/lists/collaborations/{collaborationId}
Body: {
  permission_level: 'view' | 'comment' | 'edit' | 'admin'
}

// Get list collaborators
GET /api/lists/{listId}/collaborators
Response: {
  collaborators: Collaborator[],
  pending_invites: CollaborationInvite[]
}
```

#### List Analytics and Export
```typescript
// Get list analytics
GET /api/lists/{listId}/analytics?period=30d
Response: {
  performance_metrics: {
    views_count: number,
    shares_count: number,
    exports_count: number,
    engagement_score: number
  },
  activity_timeline: ActivityLog[],
  collaboration_stats: CollaborationStats
}

// Export list
POST /api/lists/{listId}/export
Body: {
  format: 'csv' | 'xlsx' | 'pdf' | 'json',
  include_fields: string[],
  export_options: ExportOptions
}
Response: {
  job_id: string,
  estimated_completion: string
}

// Check export status
GET /api/lists/export-jobs/{jobId}
Response: {
  status: 'pending' | 'processing' | 'completed' | 'failed',
  file_url?: string,
  error_message?: string,
  progress_percentage: number
}
```

### Data Models

```typescript
interface ListItem {
  id: string;
  list_name: string;
  list_description?: string;
  list_type: 'custom' | 'template' | 'shared' | 'favorites';
  is_public: boolean;
  is_template: boolean;
  template_category?: string;
  profiles_count: number;
  collaboration_settings: CollaborationSettings;
  export_settings: ExportSettings;
  performance_metrics: PerformanceMetrics;
  created_at: string;
  updated_at: string;
  collaborators?: Collaborator[];
  recent_activity?: ActivityLog[];
}

interface ListTemplate {
  id: string;
  template_name: string;
  template_description: string;
  template_category: string;
  template_config: TemplateConfig;
  is_public: boolean;
  usage_count: number;
  created_by: string;
  created_at: string;
}

interface Collaborator {
  id: string;
  user_id: string;
  email: string;
  full_name?: string;
  permission_level: 'view' | 'comment' | 'edit' | 'admin';
  collaboration_status: 'pending' | 'accepted' | 'declined';
  invited_at: string;
  responded_at?: string;
}

interface ActivityLog {
  id: string;
  user_id: string;
  user_name: string;
  activity_type: string;
  activity_description: string;
  activity_data: Record<string, any>;
  created_at: string;
}
```

---

## Proposals System

### Overview
Complete brand approval workflow for influencer selection with invitation management, application processing, and collaboration tracking.

### Database Schema

#### Core Tables
```sql
brand_proposals:
- id (UUID, Primary Key)
- user_id (UUID, FK to auth.users)
- proposal_title (VARCHAR(300))
- proposal_description (TEXT)
- proposal_type (VARCHAR(50)) -- 'collaboration', 'sponsorship', 'campaign', 'event'
- brand_name (VARCHAR(200))
- brand_website (VARCHAR(500))
- campaign_budget_min (INTEGER)
- campaign_budget_max (INTEGER)
- target_audience (JSONB)
- deliverables_required (JSONB)
- timeline_start (DATE)
- timeline_end (DATE)
- proposal_status (VARCHAR(20)) -- 'draft', 'active', 'paused', 'completed', 'cancelled'
- approval_status (VARCHAR(20)) -- 'pending', 'approved', 'rejected', 'needs_revision'
- visibility_settings (JSONB)
- requirements (JSONB)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

proposal_invitations:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- inviter_user_id (UUID, FK to auth.users)
- invited_profile_id (UUID, FK to profiles)
- invitation_type (VARCHAR(50)) -- 'direct', 'application_based', 'open_call'
- invitation_message (TEXT)
- compensation_offer (JSONB)
- deliverables_expected (JSONB)
- deadline_response (TIMESTAMP)
- invitation_status (VARCHAR(20)) -- 'sent', 'viewed', 'responded', 'expired'
- response_type (VARCHAR(20)) -- 'accepted', 'declined', 'interested', 'negotiating'
- sent_at (TIMESTAMP)
- viewed_at (TIMESTAMP)
- responded_at (TIMESTAMP)

proposal_applications:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- applicant_profile_id (UUID, FK to profiles)
- application_message (TEXT)
- portfolio_links (JSONB)
- proposed_deliverables (JSONB)
- compensation_expectation (JSONB)
- availability_period (JSONB)
- application_status (VARCHAR(20)) -- 'submitted', 'under_review', 'approved', 'rejected', 'withdrawn'
- review_notes (TEXT)
- reviewed_by (UUID, FK to auth.users)
- submitted_at (TIMESTAMP)
- reviewed_at (TIMESTAMP)

proposal_collaborations:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- collaborator_profile_id (UUID, FK to profiles)
- collaboration_role (VARCHAR(50)) -- 'primary', 'secondary', 'supporting'
- collaboration_status (VARCHAR(20)) -- 'confirmed', 'in_progress', 'completed', 'terminated'
- contract_terms (JSONB)
- compensation_details (JSONB)
- performance_expectations (JSONB)
- actual_performance (JSONB)
- started_at (TIMESTAMP)
- completed_at (TIMESTAMP)

proposal_deliverables:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- collaboration_id (UUID, FK to proposal_collaborations)
- deliverable_title (VARCHAR(300))
- deliverable_type (VARCHAR(50))
- deliverable_description (TEXT)
- due_date (TIMESTAMP)
- submission_url (TEXT)
- submission_notes (TEXT)
- deliverable_status (VARCHAR(20)) -- 'pending', 'submitted', 'approved', 'revision_requested', 'rejected'
- quality_rating (INTEGER) -- 1-10 scale
- feedback (TEXT)
- submitted_at (TIMESTAMP)
- reviewed_at (TIMESTAMP)

proposal_analytics:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- date_recorded (DATE)
- views_count (INTEGER)
- applications_count (INTEGER)
- invitations_sent (INTEGER)
- responses_received (INTEGER)
- conversions_count (INTEGER)
- engagement_metrics (JSONB)
- performance_data (JSONB)

proposal_communications:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to brand_proposals)
- sender_user_id (UUID, FK to auth.users)
- recipient_user_id (UUID, FK to auth.users)
- recipient_profile_id (UUID, FK to profiles)
- communication_type (VARCHAR(50)) -- 'message', 'negotiation', 'update', 'reminder'
- subject (VARCHAR(300))
- message_content (TEXT)
- delivery_status (VARCHAR(50)) -- 'pending', 'sent', 'delivered', 'read'
- sent_at (TIMESTAMP)
- delivered_at (TIMESTAMP)
- read_at (TIMESTAMP)
```

### API Endpoints

#### Proposal Management
```typescript
// Get brand proposals with filtering
GET /api/proposals?status=active&type=collaboration&page=1
Response: {
  proposals: BrandProposal[],
  pagination: PaginationInfo,
  filter_options: FilterOptions
}

// Create new proposal
POST /api/proposals
Body: {
  proposal_title: string,
  proposal_description: string,
  proposal_type: string,
  brand_name: string,
  brand_website?: string,
  campaign_budget_min?: number,
  campaign_budget_max?: number,
  target_audience: TargetAudience,
  deliverables_required: Deliverable[],
  timeline_start: string,
  timeline_end: string,
  requirements: ProposalRequirements
}

// Update proposal
PUT /api/proposals/{proposalId}
Body: Partial<BrandProposal>

// Get proposal details with applications and invitations
GET /api/proposals/{proposalId}
Response: {
  proposal: BrandProposal,
  applications: Application[],
  invitations: Invitation[],
  collaborations: Collaboration[],
  analytics: ProposalAnalytics
}
```

#### Invitation Management
```typescript
// Send invitations to influencers
POST /api/proposals/{proposalId}/invitations
Body: {
  invited_profiles: Array<{
    profile_id: string,
    invitation_message?: string,
    compensation_offer: CompensationOffer,
    deliverables_expected: Deliverable[]
  }>,
  deadline_response: string
}

// Respond to invitation (from influencer perspective)
PUT /api/proposals/invitations/{invitationId}/respond
Body: {
  response_type: 'accepted' | 'declined' | 'interested' | 'negotiating',
  response_message?: string,
  counter_offer?: CompensationOffer
}

// Get received invitations
GET /api/proposals/invitations/received?status=sent
Response: {
  invitations: Invitation[],
  pagination: PaginationInfo
}

// Get sent invitations
GET /api/proposals/{proposalId}/invitations
Response: {
  invitations: Invitation[],
  response_summary: ResponseSummary
}
```

#### Application Management
```typescript
// Submit application to proposal
POST /api/proposals/{proposalId}/apply
Body: {
  application_message: string,
  portfolio_links: string[],
  proposed_deliverables: Deliverable[],
  compensation_expectation: CompensationExpectation,
  availability_period: AvailabilityPeriod
}

// Get proposal applications (brand view)
GET /api/proposals/{proposalId}/applications?status=submitted
Response: {
  applications: Application[],
  pagination: PaginationInfo,
  application_stats: ApplicationStats
}

// Review application
PUT /api/proposals/applications/{applicationId}/review
Body: {
  application_status: 'approved' | 'rejected',
  review_notes?: string,
  collaboration_offer?: CollaborationOffer
}

// Get my applications (influencer view)
GET /api/proposals/applications/my?status=submitted
Response: {
  applications: Application[],
  pagination: PaginationInfo
}
```

#### Collaboration Management
```typescript
// Create collaboration from approved application/invitation
POST /api/proposals/{proposalId}/collaborations
Body: {
  collaborator_profile_id: string,
  collaboration_role: string,
  contract_terms: ContractTerms,
  compensation_details: CompensationDetails,
  performance_expectations: PerformanceExpectations
}

// Get proposal collaborations
GET /api/proposals/{proposalId}/collaborations
Response: {
  collaborations: Collaboration[],
  collaboration_summary: CollaborationSummary
}

// Update collaboration status
PUT /api/proposals/collaborations/{collaborationId}
Body: {
  collaboration_status?: string,
  actual_performance?: PerformanceMetrics,
  completion_notes?: string
}
```

#### Deliverables Management
```typescript
// Create deliverable for collaboration
POST /api/proposals/{proposalId}/deliverables
Body: {
  collaboration_id: string,
  deliverable_title: string,
  deliverable_type: string,
  deliverable_description: string,
  due_date: string
}

// Submit deliverable
PUT /api/proposals/deliverables/{deliverableId}/submit
Body: {
  submission_url: string,
  submission_notes?: string,
  additional_files?: File[]
}

// Review deliverable
PUT /api/proposals/deliverables/{deliverableId}/review
Body: {
  deliverable_status: 'approved' | 'revision_requested' | 'rejected',
  quality_rating?: number,
  feedback?: string
}

// Get collaboration deliverables
GET /api/proposals/collaborations/{collaborationId}/deliverables
Response: {
  deliverables: Deliverable[],
  completion_stats: CompletionStats
}
```

### Data Models

```typescript
interface BrandProposal {
  id: string;
  proposal_title: string;
  proposal_description: string;
  proposal_type: 'collaboration' | 'sponsorship' | 'campaign' | 'event';
  brand_name: string;
  brand_website?: string;
  campaign_budget_min?: number;
  campaign_budget_max?: number;
  target_audience: TargetAudience;
  deliverables_required: Deliverable[];
  timeline_start: string;
  timeline_end: string;
  proposal_status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled';
  approval_status: 'pending' | 'approved' | 'rejected' | 'needs_revision';
  visibility_settings: VisibilitySettings;
  requirements: ProposalRequirements;
  created_at: string;
  updated_at: string;
}

interface Invitation {
  id: string;
  proposal_id: string;
  invited_profile: ProfileSummary;
  invitation_type: 'direct' | 'application_based' | 'open_call';
  invitation_message: string;
  compensation_offer: CompensationOffer;
  deliverables_expected: Deliverable[];
  deadline_response: string;
  invitation_status: 'sent' | 'viewed' | 'responded' | 'expired';
  response_type?: 'accepted' | 'declined' | 'interested' | 'negotiating';
  sent_at: string;
  viewed_at?: string;
  responded_at?: string;
}

interface Application {
  id: string;
  proposal_id: string;
  applicant_profile: ProfileSummary;
  application_message: string;
  portfolio_links: string[];
  proposed_deliverables: Deliverable[];
  compensation_expectation: CompensationExpectation;
  availability_period: AvailabilityPeriod;
  application_status: 'submitted' | 'under_review' | 'approved' | 'rejected' | 'withdrawn';
  review_notes?: string;
  reviewed_by?: string;
  submitted_at: string;
  reviewed_at?: string;
}

interface Collaboration {
  id: string;
  proposal_id: string;
  collaborator_profile: ProfileSummary;
  collaboration_role: 'primary' | 'secondary' | 'supporting';
  collaboration_status: 'confirmed' | 'in_progress' | 'completed' | 'terminated';
  contract_terms: ContractTerms;
  compensation_details: CompensationDetails;
  performance_expectations: PerformanceExpectations;
  actual_performance?: PerformanceMetrics;
  started_at: string;
  completed_at?: string;
}
```

---

## Campaign Enhancement

### Overview
Complete campaign management with deliverables, collaboration, milestones, budget tracking, and performance analytics.

### Database Schema

#### Enhanced Campaigns Table
```sql
-- Enhanced campaigns table (existing table with new fields)
campaigns:
- id (UUID, Primary Key)
- user_id (UUID, FK to auth.users) 
- name (VARCHAR(255))
- description (TEXT)
- status (VARCHAR(50)) -- 'draft', 'active', 'paused', 'completed', 'cancelled'
-- NEW ENHANCED FIELDS:
- campaign_type (VARCHAR(50)) -- 'influencer_marketing', 'brand_awareness', 'product_launch', 'event_promotion'
- campaign_objectives (JSONB)
- target_audience (JSONB)
- budget_total_usd (INTEGER)
- budget_allocated_usd (INTEGER)
- budget_spent_usd (INTEGER)
- timeline_start (DATE)
- timeline_end (DATE)
- performance_goals (JSONB)
- approval_workflow (JSONB)
- collaboration_settings (JSONB)
- reporting_settings (JSONB)
- tags (JSONB)
- priority_level (VARCHAR(20)) -- 'low', 'medium', 'high', 'critical'
- completion_percentage (INTEGER DEFAULT 0)
- roi_target (FLOAT)
- roi_actual (FLOAT)
- last_activity_at (TIMESTAMP)
- archived_at (TIMESTAMP)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

-- New supporting tables
campaign_deliverables:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- assigned_to_user_id (UUID, FK to auth.users)
- assigned_to_profile_id (UUID, FK to profiles)
- deliverable_title (VARCHAR(300))
- deliverable_type (VARCHAR(50))
- deliverable_description (TEXT)
- deliverable_format (VARCHAR(50))
- content_requirements (JSONB)
- due_date (TIMESTAMP)
- submission_url (TEXT)
- submission_notes (TEXT)
- deliverable_status (VARCHAR(20)) -- 'assigned', 'in_progress', 'submitted', 'approved', 'revision_requested', 'rejected'
- quality_rating (INTEGER) -- 1-10 scale
- approval_notes (TEXT)
- approved_by_user_id (UUID, FK to auth.users)
- created_at (TIMESTAMP)
- submitted_at (TIMESTAMP)
- approved_at (TIMESTAMP)

campaign_collaborators:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- collaborator_user_id (UUID, FK to auth.users)
- collaborator_profile_id (UUID, FK to profiles)
- role (VARCHAR(50)) -- 'manager', 'contributor', 'reviewer', 'observer'
- permissions (JSONB)
- collaboration_status (VARCHAR(20)) -- 'invited', 'active', 'paused', 'completed', 'removed'
- compensation_type (VARCHAR(50)) -- 'fixed', 'performance_based', 'revenue_share', 'free'
- compensation_amount_usd (INTEGER)
- performance_metrics (JSONB)
- deliverables_assigned (INTEGER DEFAULT 0)
- deliverables_completed (INTEGER DEFAULT 0)
- average_quality_rating (FLOAT)
- joined_at (TIMESTAMP)
- last_activity_at (TIMESTAMP)

campaign_milestones:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- milestone_title (VARCHAR(200))
- milestone_description (TEXT)
- milestone_type (VARCHAR(50))
- target_date (TIMESTAMP)
- actual_date (TIMESTAMP)
- milestone_status (VARCHAR(50)) -- 'pending', 'in_progress', 'completed', 'delayed', 'cancelled'
- completion_percentage (INTEGER DEFAULT 0)
- depends_on_milestone_ids (JSONB)
- blocks_milestone_ids (JSONB)
- required_deliverables (JSONB)
- success_criteria (TEXT)
- acceptance_criteria (TEXT)
- assigned_to_user_id (UUID, FK to auth.users)
- requires_approval (BOOLEAN DEFAULT false)
- approved_by_user_id (UUID, FK to auth.users)
- approved_at (TIMESTAMP)
- budgeted_amount_usd (INTEGER DEFAULT 0)
- actual_spent_usd (INTEGER DEFAULT 0)
- quality_rating (INTEGER)
- milestone_notes (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

campaign_performance_metrics:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- date_recorded (DATE)
- metric_period (VARCHAR(20)) -- 'daily', 'weekly', 'monthly'
- total_impressions (BIGINT DEFAULT 0)
- unique_reach (BIGINT DEFAULT 0)
- engagement_rate (FLOAT DEFAULT 0.0)
- click_through_rate (FLOAT DEFAULT 0.0)
- conversion_rate (FLOAT DEFAULT 0.0)
- cost_per_impression (FLOAT DEFAULT 0.0)
- cost_per_click (FLOAT DEFAULT 0.0)
- cost_per_conversion (FLOAT DEFAULT 0.0)
- roi_percentage (FLOAT DEFAULT 0.0)
- brand_mentions (INTEGER DEFAULT 0)
- user_generated_content (INTEGER DEFAULT 0)
- social_media_followers_gained (INTEGER DEFAULT 0)
- website_traffic (INTEGER DEFAULT 0)
- sales_attributed (INTEGER DEFAULT 0)
- revenue_attributed_usd (INTEGER DEFAULT 0)
- sentiment_score (FLOAT DEFAULT 0.0)
- performance_data (JSONB)

campaign_budget_tracking:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- budget_category (VARCHAR(50)) -- 'influencer_fees', 'content_creation', 'advertising', 'tools', 'other'
- budgeted_amount_usd (INTEGER)
- spent_amount_usd (INTEGER DEFAULT 0)
- remaining_amount_usd (INTEGER)
- budget_period (VARCHAR(20)) -- 'total', 'monthly', 'weekly'
- spending_date (DATE)
- expense_description (TEXT)
- approved_by_user_id (UUID, FK to auth.users)
- budget_status (VARCHAR(20)) -- 'allocated', 'spent', 'overbudget', 'returned'
- transaction_reference (VARCHAR(100))
- created_at (TIMESTAMP)

campaign_activity_log:
- id (UUID, Primary Key)
- campaign_id (UUID, FK to campaigns)
- user_id (UUID, FK to auth.users)
- activity_type (VARCHAR(50))
- activity_description (TEXT)
- activity_data (JSONB)
- ip_address (VARCHAR(45))
- created_at (TIMESTAMP)
```

### API Endpoints

#### Campaign Management
```typescript
// Get campaigns with enhanced filtering
GET /api/campaigns?status=active&type=influencer_marketing&page=1
Response: {
  campaigns: Campaign[],
  pagination: PaginationInfo,
  campaign_summary: CampaignSummary
}

// Create enhanced campaign
POST /api/campaigns
Body: {
  name: string,
  description: string,
  campaign_type: string,
  campaign_objectives: CampaignObjectives,
  target_audience: TargetAudience,
  budget_total_usd: number,
  timeline_start: string,
  timeline_end: string,
  performance_goals: PerformanceGoals,
  collaboration_settings: CollaborationSettings,
  tags: string[],
  priority_level: 'low' | 'medium' | 'high' | 'critical'
}

// Get campaign with full details
GET /api/campaigns/{campaignId}
Response: {
  campaign: Campaign,
  deliverables: Deliverable[],
  collaborators: Collaborator[],
  milestones: Milestone[],
  performance_metrics: PerformanceMetrics[],
  budget_tracking: BudgetTracking[],
  activity_log: ActivityLog[]
}

// Update campaign
PUT /api/campaigns/{campaignId}
Body: Partial<Campaign>

// Get campaign analytics
GET /api/campaigns/{campaignId}/analytics?period=30d
Response: {
  performance_overview: PerformanceOverview,
  milestone_progress: MilestoneProgress,
  budget_utilization: BudgetUtilization,
  collaborator_performance: CollaboratorPerformance[],
  deliverable_completion: DeliverableCompletion,
  roi_analysis: ROIAnalysis
}
```

#### Deliverables Management
```typescript
// Create deliverable
POST /api/campaigns/{campaignId}/deliverables
Body: {
  assigned_to_user_id?: string,
  assigned_to_profile_id?: string,
  deliverable_title: string,
  deliverable_type: string,
  deliverable_description: string,
  deliverable_format: string,
  content_requirements: ContentRequirements,
  due_date: string
}

// Get campaign deliverables
GET /api/campaigns/{campaignId}/deliverables?status=in_progress
Response: {
  deliverables: Deliverable[],
  deliverable_stats: DeliverableStats,
  overdue_count: number
}

// Submit deliverable
PUT /api/campaigns/deliverables/{deliverableId}/submit
Body: {
  submission_url: string,
  submission_notes?: string,
  additional_files?: File[]
}

// Approve/reject deliverable
PUT /api/campaigns/deliverables/{deliverableId}/review
Body: {
  deliverable_status: 'approved' | 'revision_requested' | 'rejected',
  quality_rating?: number,
  approval_notes?: string
}

// Get my deliverables (assigned to current user)
GET /api/campaigns/deliverables/assigned?status=in_progress
Response: {
  deliverables: Deliverable[],
  upcoming_deadlines: Deliverable[],
  overdue_items: Deliverable[]
}
```

#### Collaborators Management
```typescript
// Add collaborator to campaign
POST /api/campaigns/{campaignId}/collaborators
Body: {
  collaborator_user_id?: string,
  collaborator_profile_id?: string,
  role: 'manager' | 'contributor' | 'reviewer' | 'observer',
  permissions: CollaboratorPermissions,
  compensation_type: string,
  compensation_amount_usd?: number
}

// Get campaign collaborators
GET /api/campaigns/{campaignId}/collaborators
Response: {
  collaborators: Collaborator[],
  collaboration_stats: CollaborationStats,
  permission_matrix: PermissionMatrix
}

// Update collaborator role/permissions
PUT /api/campaigns/collaborators/{collaboratorId}
Body: {
  role?: string,
  permissions?: CollaboratorPermissions,
  collaboration_status?: string,
  compensation_amount_usd?: number
}

// Get collaborator performance
GET /api/campaigns/collaborators/{collaboratorId}/performance
Response: {
  performance_metrics: CollaboratorPerformanceMetrics,
  deliverable_history: DeliverableHistory[],
  activity_summary: ActivitySummary
}
```

#### Milestones Management
```typescript
// Create campaign milestone
POST /api/campaigns/{campaignId}/milestones
Body: {
  milestone_title: string,
  milestone_description: string,
  milestone_type: string,
  target_date: string,
  depends_on_milestone_ids?: string[],
  required_deliverables?: string[],
  success_criteria: string,
  assigned_to_user_id?: string,
  budgeted_amount_usd?: number
}

// Get campaign milestones
GET /api/campaigns/{campaignId}/milestones
Response: {
  milestones: Milestone[],
  milestone_timeline: MilestoneTimeline,
  critical_path: CriticalPath,
  upcoming_deadlines: Milestone[]
}

// Update milestone progress
PUT /api/campaigns/milestones/{milestoneId}
Body: {
  completion_percentage?: number,
  milestone_status?: string,
  actual_date?: string,
  milestone_notes?: string,
  actual_spent_usd?: number
}

// Complete milestone
PUT /api/campaigns/milestones/{milestoneId}/complete
Body: {
  completion_notes: string,
  quality_rating?: number,
  actual_spent_usd?: number
}
```

#### Budget Management
```typescript
// Get campaign budget overview
GET /api/campaigns/{campaignId}/budget
Response: {
  budget_overview: BudgetOverview,
  spending_by_category: SpendingByCategory,
  budget_tracking: BudgetTracking[],
  forecast: BudgetForecast,
  alerts: BudgetAlert[]
}

// Record budget expense
POST /api/campaigns/{campaignId}/budget/expenses
Body: {
  budget_category: string,
  spent_amount_usd: number,
  expense_description: string,
  spending_date: string,
  transaction_reference?: string
}

// Update budget allocation
PUT /api/campaigns/{campaignId}/budget/allocation
Body: {
  category_budgets: Array<{
    budget_category: string,
    budgeted_amount_usd: number
  }>
}

// Get budget alerts
GET /api/campaigns/{campaignId}/budget/alerts
Response: {
  active_alerts: BudgetAlert[],
  threshold_warnings: ThresholdWarning[],
  overspend_risks: OverspendRisk[]
}
```

### Data Models

```typescript
interface Campaign {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled';
  campaign_type: 'influencer_marketing' | 'brand_awareness' | 'product_launch' | 'event_promotion';
  campaign_objectives: CampaignObjectives;
  target_audience: TargetAudience;
  budget_total_usd: number;
  budget_allocated_usd: number;
  budget_spent_usd: number;
  timeline_start: string;
  timeline_end: string;
  performance_goals: PerformanceGoals;
  approval_workflow: ApprovalWorkflow;
  collaboration_settings: CollaborationSettings;
  reporting_settings: ReportingSettings;
  tags: string[];
  priority_level: 'low' | 'medium' | 'high' | 'critical';
  completion_percentage: number;
  roi_target?: number;
  roi_actual?: number;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
}

interface Deliverable {
  id: string;
  campaign_id: string;
  assigned_to_user_id?: string;
  assigned_to_profile_id?: string;
  assignee?: UserProfile | ProfileSummary;
  deliverable_title: string;
  deliverable_type: string;
  deliverable_description: string;
  deliverable_format: string;
  content_requirements: ContentRequirements;
  due_date: string;
  submission_url?: string;
  submission_notes?: string;
  deliverable_status: 'assigned' | 'in_progress' | 'submitted' | 'approved' | 'revision_requested' | 'rejected';
  quality_rating?: number;
  approval_notes?: string;
  approved_by_user_id?: string;
  created_at: string;
  submitted_at?: string;
  approved_at?: string;
}

interface Collaborator {
  id: string;
  campaign_id: string;
  collaborator_user_id?: string;
  collaborator_profile_id?: string;
  collaborator?: UserProfile | ProfileSummary;
  role: 'manager' | 'contributor' | 'reviewer' | 'observer';
  permissions: CollaboratorPermissions;
  collaboration_status: 'invited' | 'active' | 'paused' | 'completed' | 'removed';
  compensation_type: 'fixed' | 'performance_based' | 'revenue_share' | 'free';
  compensation_amount_usd?: number;
  performance_metrics: CollaboratorPerformanceMetrics;
  deliverables_assigned: number;
  deliverables_completed: number;
  average_quality_rating?: number;
  joined_at: string;
  last_activity_at?: string;
}

interface Milestone {
  id: string;
  campaign_id: string;
  milestone_title: string;
  milestone_description: string;
  milestone_type: string;
  target_date: string;
  actual_date?: string;
  milestone_status: 'pending' | 'in_progress' | 'completed' | 'delayed' | 'cancelled';
  completion_percentage: number;
  depends_on_milestone_ids: string[];
  blocks_milestone_ids: string[];
  required_deliverables: string[];
  success_criteria: string;
  acceptance_criteria: string;
  assigned_to_user_id?: string;
  assigned_user?: UserProfile;
  requires_approval: boolean;
  approved_by_user_id?: string;
  approved_at?: string;
  budgeted_amount_usd: number;
  actual_spent_usd: number;
  quality_rating?: number;
  milestone_notes?: string;
  created_at: string;
  updated_at: string;
}
```

---

## Superadmin Dashboard

### Overview
Complete platform management dashboard with system analytics, user management, configurations, and monitoring capabilities.

### Database Schema

#### Core Tables
```sql
admin_users:
- id (BIGSERIAL, Primary Key)
- user_id (UUID, FK to auth.users)
- admin_role (VARCHAR(50)) -- 'superadmin', 'admin', 'support', 'analyst'
- permissions (JSONB)
- is_active (BOOLEAN DEFAULT true)
- created_by (UUID, FK to auth.users)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- last_login_at (TIMESTAMP)

system_analytics:
- id (BIGSERIAL, Primary Key)
- date (DATE UNIQUE)
- total_users (INTEGER)
- active_users (INTEGER)
- new_users (INTEGER)
- total_profiles (INTEGER)
- profiles_analyzed (INTEGER)
- api_requests (INTEGER)
- ai_analysis_jobs (INTEGER)
- successful_ai_jobs (INTEGER)
- credits_consumed (INTEGER)
- revenue_generated (DECIMAL(10,2))
- total_campaigns (INTEGER)
- active_campaigns (INTEGER)
- total_proposals (INTEGER)
- active_proposals (INTEGER)
- system_uptime_percentage (DECIMAL(5,2))
- average_response_time_ms (INTEGER)
- error_rate_percentage (DECIMAL(5,2))
- cache_hit_rate_percentage (DECIMAL(5,2))
- analytics_data (JSONB)
- created_at (TIMESTAMP)

system_configurations:
- id (BIGSERIAL, Primary Key)
- config_key (VARCHAR(100) UNIQUE)
- config_value (JSONB)
- config_type (VARCHAR(50)) -- 'general', 'ai', 'credits', 'performance', 'security'
- description (TEXT)
- is_active (BOOLEAN DEFAULT true)
- requires_restart (BOOLEAN DEFAULT false)
- created_by (UUID, FK to auth.users)
- updated_by (UUID, FK to auth.users)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

admin_notifications:
- id (BIGSERIAL, Primary Key)
- notification_type (VARCHAR(50)) -- 'system_alert', 'user_activity', 'performance', 'security'
- title (VARCHAR(255))
- message (TEXT)
- severity (VARCHAR(20)) -- 'critical', 'warning', 'info', 'success'
- data (JSONB)
- is_read (BOOLEAN DEFAULT false)
- is_dismissed (BOOLEAN DEFAULT false)
- target_admin_role (VARCHAR(50))
- created_at (TIMESTAMP)
- read_at (TIMESTAMP)
- dismissed_at (TIMESTAMP)

system_audit_logs:
- id (BIGSERIAL, Primary Key)
- admin_user_id (UUID, FK to auth.users)
- action (VARCHAR(100))
- resource_type (VARCHAR(50)) -- 'user', 'campaign', 'proposal', 'config', 'system'
- resource_id (VARCHAR(100))
- old_values (JSONB)
- new_values (JSONB)
- ip_address (VARCHAR(45))
- user_agent (TEXT)
- result (VARCHAR(20)) -- 'success', 'failure', 'partial'
- error_message (TEXT)
- created_at (TIMESTAMP)

feature_flags:
- id (BIGSERIAL, Primary Key)
- flag_name (VARCHAR(100) UNIQUE)
- flag_description (TEXT)
- is_enabled (BOOLEAN DEFAULT false)
- rollout_percentage (INTEGER DEFAULT 0) -- 0-100
- target_users (JSONB) -- Array of user IDs
- conditions (JSONB) -- Conditions for enabling
- created_by (UUID, FK to auth.users)
- updated_by (UUID, FK to auth.users)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

system_maintenance_jobs:
- id (BIGSERIAL, Primary Key)
- job_name (VARCHAR(100))
- job_type (VARCHAR(50)) -- 'cleanup', 'backup', 'analytics', 'optimization'
- job_status (VARCHAR(20)) -- 'scheduled', 'running', 'completed', 'failed'
- scheduled_at (TIMESTAMP)
- started_at (TIMESTAMP)
- completed_at (TIMESTAMP)
- job_config (JSONB)
- job_result (JSONB)
- error_message (TEXT)
- created_by (UUID, FK to auth.users)
- created_at (TIMESTAMP)

admin_user_actions:
- id (BIGSERIAL, Primary Key)
- admin_user_id (UUID, FK to auth.users)
- target_user_id (UUID, FK to auth.users)
- action (VARCHAR(50)) -- 'suspend', 'unsuspend', 'delete', 'update_credits', 'reset_password'
- reason (TEXT)
- action_data (JSONB)
- created_at (TIMESTAMP)
```

### API Endpoints

#### System Dashboard
```typescript
// Get system dashboard overview
GET /api/admin/dashboard
Response: {
  platform_summary: {
    total_users: number,
    active_users: number,
    total_profiles: number,
    total_campaigns: number,
    active_campaigns: number,
    total_proposals: number,
    pending_proposals: number,
    total_credits_consumed: number,
    ai_jobs_processed: number,
    last_updated: string
  },
  performance_metrics: {
    avg_response_time: number,
    avg_error_rate: number,
    avg_cache_hit_rate: number,
    avg_uptime: number,
    total_api_requests: number,
    successful_ai_jobs_rate: number,
    period: string,
    generated_at: string
  },
  recent_analytics: SystemAnalytics[],
  trends: {
    users_growth: number,
    active_users_change: number,
    api_requests_change: number,
    credits_consumption_change: number,
    error_rate_change: number,
    cache_hit_rate_change: number
  },
  recent_notifications: AdminNotification[],
  generated_at: string
}

// Get user activity summary
GET /api/admin/analytics/user-activity?days=7
Response: {
  new_users: number,
  active_users: number,
  profile_searches: number,
  credits_purchased: number,
  period_days: number,
  generated_at: string
}

// Get system analytics by date range
GET /api/admin/analytics?start_date=2024-01-01&end_date=2024-01-31
Response: {
  analytics: SystemAnalytics[],
  aggregated_metrics: AggregatedMetrics,
  period_summary: PeriodSummary
}

// Update daily analytics (manual trigger)
POST /api/admin/analytics/update-daily
Response: {
  status: 'success' | 'error',
  message: string,
  analytics: SystemAnalytics
}
```

#### User Management
```typescript
// Get user list with admin controls
GET /api/admin/users?page=1&limit=50&search=john&status=active
Response: {
  users: Array<{
    id: string,
    email: string,
    created_at: string,
    full_name?: string,
    company?: string,
    total_credits: number,
    available_credits: number,
    used_credits: number,
    profile_access_count: number,
    last_active?: string
  }>,
  pagination: PaginationInfo
}

// Update user credits
POST /api/admin/users/{userId}/credits
Body: {
  credit_amount: number, // positive or negative
  reason: string
}
Response: {
  transaction_id: string,
  credit_amount: number,
  new_balance: number,
  reason: string
}

// Get user details for admin
GET /api/admin/users/{userId}
Response: {
  user: UserDetails,
  credit_history: CreditTransaction[],
  profile_access_history: UserProfileAccess[],
  campaign_activity: CampaignActivity[],
  system_activity: UserSystemActivity[]
}

// Suspend/unsuspend user
PUT /api/admin/users/{userId}/status
Body: {
  action: 'suspend' | 'unsuspend',
  reason: string
}
Response: {
  status: 'success',
  user_status: string,
  action_recorded: boolean
}
```

#### System Configuration
```typescript
// Get all system configurations
GET /api/admin/config?type=ai&active_only=true
Response: {
  configurations: Array<{
    id: number,
    config_key: string,
    config_value: any,
    config_type: string,
    description: string,
    is_active: boolean,
    requires_restart: boolean,
    created_at: string,
    updated_at: string
  }>
}

// Update system configuration
PUT /api/admin/config/{configKey}
Body: {
  config_value: any,
  config_type?: string,
  description?: string,
  requires_restart?: boolean
}
Response: {
  configuration: SystemConfiguration,
  requires_restart: boolean,
  previous_value: any
}

// Get single configuration
GET /api/admin/config/{configKey}
Response: {
  configuration: SystemConfiguration,
  usage_notes?: string,
  related_configs?: string[]
}
```

#### Admin Notifications
```typescript
// Get admin notifications
GET /api/admin/notifications?type=system_alert&severity=critical&unread_only=true
Response: {
  notifications: Array<{
    id: number,
    notification_type: string,
    title: string,
    message: string,
    severity: string,
    data: Record<string, any>,
    is_read: boolean,
    is_dismissed: boolean,
    target_admin_role?: string,
    created_at: string
  }>
}

// Mark notification as read
PUT /api/admin/notifications/{notificationId}/read
Response: {
  status: 'success',
  notification: AdminNotification
}

// Dismiss notification
PUT /api/admin/notifications/{notificationId}/dismiss
Response: {
  status: 'success',
  notification: AdminNotification
}

// Create system notification
POST /api/admin/notifications
Body: {
  notification_type: string,
  title: string,
  message: string,
  severity: 'critical' | 'warning' | 'info' | 'success',
  data?: Record<string, any>,
  target_admin_role?: string
}
Response: {
  notification: AdminNotification
}
```

#### Feature Flags Management
```typescript
// Get all feature flags
GET /api/admin/feature-flags
Response: {
  feature_flags: Array<{
    id: number,
    flag_name: string,
    flag_description: string,
    is_enabled: boolean,
    rollout_percentage: number,
    target_users: string[],
    conditions: Record<string, any>,
    created_at: string,
    updated_at: string
  }>
}

// Create feature flag
POST /api/admin/feature-flags
Body: {
  flag_name: string,
  flag_description?: string,
  is_enabled?: boolean,
  rollout_percentage?: number,
  target_users?: string[],
  conditions?: Record<string, any>
}
Response: {
  feature_flag: FeatureFlag
}

// Update feature flag
PUT /api/admin/feature-flags/{flagId}
Body: {
  is_enabled?: boolean,
  rollout_percentage?: number,
  target_users?: string[],
  conditions?: Record<string, any>
}
Response: {
  feature_flag: FeatureFlag
}

// Check feature flag for user
GET /api/admin/feature-flags/{flagName}/check?user_id={userId}
Response: {
  flag_name: string,
  is_enabled: boolean,
  reason: string
}
```

#### System Audit and Maintenance
```typescript
// Get audit logs
GET /api/admin/audit-logs?admin_user_id={userId}&resource_type=user&action=update_credits&page=1
Response: {
  audit_logs: Array<{
    id: number,
    admin_user_id?: string,
    action: string,
    resource_type: string,
    resource_id?: string,
    old_values?: Record<string, any>,
    new_values?: Record<string, any>,
    ip_address?: string,
    result: string,
    error_message?: string,
    created_at: string
  }>,
  pagination: PaginationInfo
}

// Get maintenance jobs
GET /api/admin/maintenance-jobs?status=scheduled&type=cleanup
Response: {
  maintenance_jobs: Array<{
    id: number,
    job_name: string,
    job_type: string,
    job_status: string,
    scheduled_at: string,
    started_at?: string,
    completed_at?: string,
    job_config: Record<string, any>,
    job_result?: Record<string, any>,
    error_message?: string
  }>
}

// Create maintenance job
POST /api/admin/maintenance-jobs
Body: {
  job_name: string,
  job_type: string,
  scheduled_at: string,
  job_config?: Record<string, any>
}
Response: {
  maintenance_job: SystemMaintenanceJob
}

// Get system health status
GET /api/admin/system/health
Response: {
  overall_health: number, // 0-100
  components: Array<{
    name: string,
    status: 'healthy' | 'warning' | 'critical',
    response_time?: number,
    error_rate?: number,
    last_check: string
  }>,
  alerts: SystemAlert[],
  uptime: UptimeMetrics
}
```

### Data Models

```typescript
interface SystemAnalytics {
  id: number;
  date: string;
  total_users: number;
  active_users: number;
  new_users: number;
  total_profiles: number;
  profiles_analyzed: number;
  api_requests: number;
  ai_analysis_jobs: number;
  successful_ai_jobs: number;
  credits_consumed: number;
  revenue_generated: number;
  total_campaigns: number;
  active_campaigns: number;
  total_proposals: number;
  active_proposals: number;
  system_uptime_percentage: number;
  average_response_time_ms: number;
  error_rate_percentage: number;
  cache_hit_rate_percentage: number;
  analytics_data: Record<string, any>;
  created_at: string;
}

interface AdminUser {
  id: number;
  user_id: string;
  admin_role: 'superadmin' | 'admin' | 'support' | 'analyst';
  permissions: Record<string, any>;
  is_active: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
}

interface SystemConfiguration {
  id: number;
  config_key: string;
  config_value: any;
  config_type: 'general' | 'ai' | 'credits' | 'performance' | 'security';
  description?: string;
  is_active: boolean;
  requires_restart: boolean;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
}

interface AdminNotification {
  id: number;
  notification_type: 'system_alert' | 'user_activity' | 'performance' | 'security';
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info' | 'success';
  data: Record<string, any>;
  is_read: boolean;
  is_dismissed: boolean;
  target_admin_role?: string;
  created_at: string;
  read_at?: string;
  dismissed_at?: string;
}

interface FeatureFlag {
  id: number;
  flag_name: string;
  flag_description?: string;
  is_enabled: boolean;
  rollout_percentage: number;
  target_users: string[];
  conditions: Record<string, any>;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
}
```

---

## Common Patterns

### Authentication and Authorization
All endpoints require authentication via Supabase JWT tokens. Admin endpoints require additional role-based permissions.

```typescript
// Request headers for all API calls
headers: {
  'Authorization': 'Bearer <supabase_jwt_token>',
  'Content-Type': 'application/json'
}

// Admin endpoints additionally require admin role verification
// This is handled automatically by Row Level Security policies
```

### Pagination Pattern
All list endpoints use consistent pagination:

```typescript
interface PaginationInfo {
  page: number;
  limit: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// URL pattern: ?page=1&limit=20
// Response includes pagination info
```

### Error Handling
Consistent error response format:

```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
  request_id: string;
  timestamp: string;
}

// HTTP status codes follow REST conventions
// 400: Bad Request, 401: Unauthorized, 403: Forbidden, 404: Not Found, 500: Internal Server Error
```

### Real-time Updates
WebSocket connections for real-time updates:

```typescript
// Connect to WebSocket
const ws = new WebSocket('wss://api.domain.com/ws');

// Subscribe to specific events
ws.send(JSON.stringify({
  type: 'subscribe',
  topics: ['campaigns.{campaignId}', 'notifications.admin']
}));

// Receive real-time updates
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // Handle update based on update.type and update.topic
};
```

---

## API Integration Examples

### TypeScript Service Classes

```typescript
// Base API service
class ApiService {
  private baseUrl = 'https://api.yourdomain.com/api';
  private authToken: string;

  constructor(authToken: string) {
    this.authToken = authToken;
  }

  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.authToken}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || 'API request failed');
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

// Lists service example
class ListsService extends ApiService {
  async getLists(params: {
    page?: number;
    limit?: number;
    type?: string;
    search?: string;
  } = {}) {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
    
    return this.get<{
      lists: ListItem[];
      pagination: PaginationInfo;
      templates: ListTemplate[];
    }>(`/lists?${queryParams.toString()}`);
  }

  async createList(listData: CreateListRequest) {
    return this.post<ListItem>('/lists', listData);
  }

  async shareList(listId: string, collaborators: CollaboratorRequest[]) {
    return this.post(`/lists/${listId}/share`, { collaborators });
  }

  async exportList(listId: string, exportOptions: ExportOptions) {
    return this.post<{ job_id: string }>(`/lists/${listId}/export`, exportOptions);
  }
}

// Proposals service example
class ProposalsService extends ApiService {
  async getProposals(filters: ProposalFilters = {}) {
    const queryParams = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });

    return this.get<{
      proposals: BrandProposal[];
      pagination: PaginationInfo;
    }>(`/proposals?${queryParams.toString()}`);
  }

  async createProposal(proposalData: CreateProposalRequest) {
    return this.post<BrandProposal>('/proposals', proposalData);
  }

  async sendInvitations(proposalId: string, invitations: InvitationRequest[]) {
    return this.post(`/proposals/${proposalId}/invitations`, {
      invited_profiles: invitations
    });
  }

  async respondToInvitation(invitationId: string, response: InvitationResponse) {
    return this.put(`/proposals/invitations/${invitationId}/respond`, response);
  }

  async submitApplication(proposalId: string, application: ApplicationRequest) {
    return this.post(`/proposals/${proposalId}/apply`, application);
  }
}

// Campaigns service example
class CampaignsService extends ApiService {
  async getCampaigns(filters: CampaignFilters = {}) {
    const queryParams = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });

    return this.get<{
      campaigns: Campaign[];
      pagination: PaginationInfo;
    }>(`/campaigns?${queryParams.toString()}`);
  }

  async createCampaign(campaignData: CreateCampaignRequest) {
    return this.post<Campaign>('/campaigns', campaignData);
  }

  async getCampaignDetails(campaignId: string) {
    return this.get<{
      campaign: Campaign;
      deliverables: Deliverable[];
      collaborators: Collaborator[];
      milestones: Milestone[];
      performance_metrics: PerformanceMetrics[];
    }>(`/campaigns/${campaignId}`);
  }

  async createDeliverable(campaignId: string, deliverableData: CreateDeliverableRequest) {
    return this.post<Deliverable>(`/campaigns/${campaignId}/deliverables`, deliverableData);
  }

  async submitDeliverable(deliverableId: string, submission: DeliverableSubmission) {
    return this.put(`/campaigns/deliverables/${deliverableId}/submit`, submission);
  }

  async addCollaborator(campaignId: string, collaboratorData: AddCollaboratorRequest) {
    return this.post<Collaborator>(`/campaigns/${campaignId}/collaborators`, collaboratorData);
  }
}

// Admin service example
class AdminService extends ApiService {
  async getDashboard() {
    return this.get<{
      platform_summary: PlatformSummary;
      performance_metrics: PerformanceMetrics;
      recent_analytics: SystemAnalytics[];
      trends: TrendData;
      recent_notifications: AdminNotification[];
    }>('/admin/dashboard');
  }

  async getUserList(params: UserListParams = {}) {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });

    return this.get<{
      users: AdminUserInfo[];
      pagination: PaginationInfo;
    }>(`/admin/users?${queryParams.toString()}`);
  }

  async updateUserCredits(userId: string, creditAmount: number, reason: string) {
    return this.post(`/admin/users/${userId}/credits`, {
      credit_amount: creditAmount,
      reason
    });
  }

  async getSystemConfig(configType?: string) {
    const params = configType ? `?type=${configType}` : '';
    return this.get<{ configurations: SystemConfiguration[] }>(`/admin/config${params}`);
  }

  async updateSystemConfig(configKey: string, configValue: any, options: UpdateConfigOptions = {}) {
    return this.put(`/admin/config/${configKey}`, {
      config_value: configValue,
      ...options
    });
  }
}
```

### React Hooks Examples

```typescript
// Custom hooks for API integration with React Query

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Lists hooks
export const useListsQuery = (params: ListQueryParams = {}) => {
  return useQuery({
    queryKey: ['lists', params],
    queryFn: () => listsService.getLists(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useCreateListMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (listData: CreateListRequest) => listsService.createList(listData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lists'] });
    },
  });
};

export const useShareListMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ listId, collaborators }: { listId: string; collaborators: CollaboratorRequest[] }) =>
      listsService.shareList(listId, collaborators),
    onSuccess: (_, { listId }) => {
      queryClient.invalidateQueries({ queryKey: ['lists', listId] });
    },
  });
};

// Proposals hooks
export const useProposalsQuery = (filters: ProposalFilters = {}) => {
  return useQuery({
    queryKey: ['proposals', filters],
    queryFn: () => proposalsService.getProposals(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useCreateProposalMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (proposalData: CreateProposalRequest) => proposalsService.createProposal(proposalData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
};

export const useInvitationResponseMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ invitationId, response }: { invitationId: string; response: InvitationResponse }) =>
      proposalsService.respondToInvitation(invitationId, response),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['invitations'] });
    },
  });
};

// Campaigns hooks
export const useCampaignsQuery = (filters: CampaignFilters = {}) => {
  return useQuery({
    queryKey: ['campaigns', filters],
    queryFn: () => campaignsService.getCampaigns(filters),
    staleTime: 2 * 60 * 1000,
  });
};

export const useCampaignDetailsQuery = (campaignId: string) => {
  return useQuery({
    queryKey: ['campaigns', campaignId, 'details'],
    queryFn: () => campaignsService.getCampaignDetails(campaignId),
    enabled: !!campaignId,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
};

export const useCreateDeliverableMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ campaignId, deliverableData }: { campaignId: string; deliverableData: CreateDeliverableRequest }) =>
      campaignsService.createDeliverable(campaignId, deliverableData),
    onSuccess: (_, { campaignId }) => {
      queryClient.invalidateQueries({ queryKey: ['campaigns', campaignId, 'details'] });
    },
  });
};

// Admin hooks
export const useAdminDashboardQuery = () => {
  return useQuery({
    queryKey: ['admin', 'dashboard'],
    queryFn: () => adminService.getDashboard(),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refetch every minute
  });
};

export const useAdminUserListQuery = (params: UserListParams = {}) => {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => adminService.getUserList(params),
    staleTime: 1 * 60 * 1000,
  });
};

export const useUpdateUserCreditsMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ userId, creditAmount, reason }: { userId: string; creditAmount: number; reason: string }) =>
      adminService.updateUserCredits(userId, creditAmount, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
};
```

This comprehensive guide provides all the necessary information for frontend developers to integrate with the enhanced influencer marketing platform systems. Each section includes complete database schemas, API endpoints, data models, and practical integration examples.

The systems are designed to work together seamlessly while maintaining clear separation of concerns. The API follows REST conventions with consistent patterns for authentication, pagination, error handling, and real-time updates.