# Admin-Brand Proposals System - Frontend Implementation Guide

## Overview

**IMPORTANT**: This is an Admin-to-Brand proposal system. Admin (us) creates proposals and sends them to Brands (users) for approval. No influencers have access to this platform.

**System Flow**:
1. **Admin creates proposals** for brands offering marketing services
2. **Admin sends proposals** to brands for review
3. **Brands review and respond** (approve, reject, negotiate, ask questions)
4. **Admin manages the sales pipeline** and follows up with brands
5. **System tracks conversion metrics** and proposal performance

---

## Database Schema

### Core Tables

```sql
admin_brand_proposals:
- id (UUID, Primary Key)
- brand_user_id (UUID, FK to auth.users) -- The brand receiving the proposal
- created_by_admin_id (UUID, FK to auth.users) -- Admin who created it
- proposal_title (VARCHAR(300))
- proposal_description (TEXT)
- executive_summary (TEXT) -- High-level summary for executives
- service_type (VARCHAR(100)) -- 'influencer_marketing', 'content_creation', 'brand_strategy'
- service_description (TEXT) -- What services we will provide
- deliverables (JSONB) -- What we will deliver to the brand
- proposed_start_date (DATE)
- proposed_end_date (DATE)
- estimated_duration_days (INTEGER)
- proposed_budget_usd (INTEGER) -- Our proposed service fee
- budget_breakdown (JSONB) -- Detailed cost breakdown
- payment_terms (VARCHAR(100)) -- 'net_30', 'net_15', 'upfront', 'milestone'
- campaign_objectives (JSONB) -- ["brand_awareness", "lead_generation", "sales"]
- target_audience_description (TEXT)
- expected_deliverables (JSONB) -- Expected campaign outcomes
- success_metrics (JSONB) -- KPIs we'll measure
- expected_results (TEXT) -- What results we expect to deliver
- status (VARCHAR(50)) -- 'draft', 'sent', 'under_review', 'approved', 'rejected', 'negotiation', 'closed'
- priority_level (VARCHAR(20)) -- 'high', 'medium', 'low'
- brand_viewed_at (TIMESTAMP) -- When brand first viewed proposal
- brand_response_due_date (TIMESTAMP)
- brand_decision (VARCHAR(50)) -- 'approved', 'rejected', 'counter_proposal', 'needs_clarification'
- brand_feedback (TEXT) -- Brand's feedback/concerns
- brand_counter_proposal (JSONB) -- Brand's counter-offer
- last_contact_date (TIMESTAMP)
- next_follow_up_date (TIMESTAMP)
- contact_attempts (INTEGER)
- admin_notes (TEXT) -- Internal notes not visible to brand
- tags (JSONB) -- Tags for organization
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- sent_at (TIMESTAMP) -- When proposal was sent to brand
- responded_at (TIMESTAMP) -- When brand responded
- closed_at (TIMESTAMP) -- When proposal was closed (approved/rejected)

proposal_versions:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to admin_brand_proposals)
- version_number (INTEGER)
- version_description (TEXT) -- What changed in this version
- created_by_admin_id (UUID, FK to auth.users)
- proposal_data (JSONB) -- Complete proposal data snapshot
- changes_made (JSONB) -- List of changes made
- created_at (TIMESTAMP)
- is_current_version (BOOLEAN)

proposal_communications:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to admin_brand_proposals)
- sender_admin_id (UUID, FK to auth.users)
- sender_is_brand (BOOLEAN) -- true if brand sent this communication
- communication_type (VARCHAR(50)) -- 'email', 'phone_call', 'meeting', 'message', 'document_shared'
- subject (VARCHAR(300))
- message_content (TEXT)
- meeting_type (VARCHAR(50)) -- 'video_call', 'phone_call', 'in_person', 'presentation'
- meeting_duration_minutes (INTEGER)
- meeting_attendees (JSONB)
- shared_documents (JSONB) -- Links to shared documents
- action_items (JSONB) -- Action items from this communication
- follow_up_required (BOOLEAN)
- follow_up_date (TIMESTAMP)
- delivery_status (VARCHAR(50)) -- 'sent', 'delivered', 'read', 'responded'
- brand_response_required (BOOLEAN)
- brand_responded (BOOLEAN)
- created_at (TIMESTAMP)
- scheduled_for (TIMESTAMP) -- For scheduled communications
- completed_at (TIMESTAMP)

proposal_analytics:
- id (UUID, Primary Key)
- proposal_id (UUID, FK to admin_brand_proposals)
- date_recorded (DATE)
- days_in_draft (INTEGER)
- days_sent_to_brand (INTEGER)
- days_under_review (INTEGER)
- days_in_negotiation (INTEGER)
- time_to_decision_days (INTEGER) -- Time from sent to decision
- total_communications (INTEGER)
- admin_initiated_communications (INTEGER)
- brand_initiated_communications (INTEGER)
- meetings_held (INTEGER)
- documents_shared (INTEGER)
- proposal_views (INTEGER) -- How many times brand viewed proposal
- time_spent_reviewing_minutes (INTEGER)
- sections_viewed (JSONB) -- Which sections were viewed
- conversion_stage (VARCHAR(50)) -- 'created', 'sent', 'viewed', 'responded', 'negotiated', 'decided'
- conversion_probability (DECIMAL) -- Estimated probability of conversion (0-100)
- proposed_value_usd (INTEGER)
- negotiated_value_usd (INTEGER)
- discount_amount_usd (INTEGER)
- discount_percentage (DECIMAL)
- final_decision (VARCHAR(50)) -- 'approved', 'rejected', 'withdrawn'
- rejection_reason (VARCHAR(100)) -- 'budget', 'timeline', 'services', 'competition'
- win_reason (VARCHAR(100)) -- 'price', 'services', 'relationship', 'expertise'
- recorded_at (TIMESTAMP)

proposal_templates:
- id (UUID, Primary Key)
- template_name (VARCHAR(200))
- template_description (TEXT)
- service_type (VARCHAR(100))
- template_structure (JSONB) -- Complete proposal template structure
- default_budget_range (JSONB) -- {"min": 5000, "max": 25000}
- default_timeline_days (INTEGER)
- is_active (BOOLEAN)
- usage_count (INTEGER)
- created_by_admin_id (UUID, FK to auth.users)
- category (VARCHAR(100)) -- 'standard', 'premium', 'enterprise', 'custom'
- tags (JSONB)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- last_used_at (TIMESTAMP)
```

---

## API Endpoints

### Admin Proposal Management

#### Create New Proposal (Admin Only)
```typescript
POST /api/admin/proposals
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  brand_user_id: string,
  proposal_title: string,
  proposal_description: string,
  executive_summary?: string,
  service_type: 'influencer_marketing' | 'content_creation' | 'brand_strategy' | 'campaign_management',
  service_description: string,
  deliverables: string[],
  proposed_start_date?: string, // DATE
  proposed_end_date?: string,   // DATE
  estimated_duration_days?: number,
  proposed_budget_usd: number,
  budget_breakdown?: Record<string, number>,
  payment_terms?: 'net_30' | 'net_15' | 'upfront' | 'milestone',
  campaign_objectives?: string[],
  target_audience_description?: string,
  expected_deliverables?: string[],
  success_metrics?: string[],
  expected_results?: string,
  priority_level?: 'high' | 'medium' | 'low',
  admin_notes?: string,
  tags?: string[]
}
Response: {
  id: string,
  proposal_title: string,
  status: string,
  created_at: string,
  proposed_budget_usd: number
}
```

#### Update Proposal (Admin Only)
```typescript
PUT /api/admin/proposals/{proposalId}
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  // Any fields from create proposal that need updating
  proposal_title?: string,
  proposal_description?: string,
  proposed_budget_usd?: number,
  // ... other updatable fields
}
Response: {
  id: string,
  proposal_title: string,
  status: string,
  updated_at: string
}
```

#### Send Proposal to Brand (Admin Only)
```typescript
POST /api/admin/proposals/{proposalId}/send
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  response_due_date?: string, // Optional deadline for brand response
  custom_message?: string,    // Optional message to include
  send_notification?: boolean // Whether to send email notification
}
Response: {
  proposal_id: string,
  status: 'sent',
  sent_at: string,
  message: string
}
```

#### Get Admin's Proposals (Admin Only)
```typescript
GET /api/admin/proposals?status=draft&service_type=influencer_marketing&limit=50&offset=0
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Query Parameters: {
  status?: 'draft' | 'sent' | 'under_review' | 'approved' | 'rejected' | 'negotiation' | 'closed',
  service_type?: 'influencer_marketing' | 'content_creation' | 'brand_strategy' | 'campaign_management',
  priority_level?: 'high' | 'medium' | 'low',
  min_budget?: number,
  max_budget?: number,
  limit?: number,
  offset?: number
}
Response: {
  proposals: AdminProposal[],
  total_count: number,
  limit: number,
  offset: number,
  has_more: boolean
}
```

#### Get Proposal Details (Admin Only)
```typescript
GET /api/admin/proposals/{proposalId}
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Response: AdminProposal
```

### Brand Proposal Access

#### Get Proposals for Brand (Brand User Only)
```typescript
GET /api/brand/proposals
Headers: {
  Authorization: "Bearer {brand_jwt_token}"
}
Response: {
  proposals: BrandProposal[],
  total_count: number
}
```

#### Get Proposal Details (Brand User Only)
```typescript
GET /api/brand/proposals/{proposalId}
Headers: {
  Authorization: "Bearer {brand_jwt_token}"
}
Response: BrandProposal
```

#### Submit Brand Response (Brand User Only)
```typescript
POST /api/brand/proposals/{proposalId}/respond
Headers: {
  Authorization: "Bearer {brand_jwt_token}"
}
Body: {
  decision: 'approved' | 'rejected' | 'counter_proposal' | 'needs_clarification',
  feedback?: string,
  counter_proposal?: {
    requested_budget_usd?: number,
    requested_timeline_days?: number,
    requested_changes?: string[],
    additional_requirements?: string
  }
}
Response: {
  proposal_id: string,
  decision: string,
  status: string,
  responded_at: string,
  message: string
}
```

### Communications

#### Add Communication (Admin Only)
```typescript
POST /api/admin/proposals/{proposalId}/communications
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  communication_type: 'email' | 'phone_call' | 'meeting' | 'message' | 'document_shared',
  subject?: string,
  message_content: string,
  meeting_type?: 'video_call' | 'phone_call' | 'in_person' | 'presentation',
  meeting_duration_minutes?: number,
  meeting_attendees?: string[],
  shared_documents?: string[],
  action_items?: string[],
  follow_up_required?: boolean,
  follow_up_date?: string,
  brand_response_required?: boolean
}
Response: {
  id: string,
  created_at: string,
  message: string
}
```

#### Get Communications (Admin and Brand)
```typescript
GET /api/proposals/{proposalId}/communications
Headers: {
  Authorization: "Bearer {jwt_token}"
}
Response: {
  communications: Communication[],
  total_count: number
}
```

### Analytics and Reporting

#### Get Proposal Metrics (Admin Only)
```typescript
GET /api/admin/proposals/{proposalId}/metrics
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Response: {
  proposal_id: string,
  proposal_title: string,
  status: string,
  proposed_budget_usd: number,
  service_type: string,
  created_at: string,
  sent_at?: string,
  responded_at?: string,
  days_since_created: number,
  days_since_sent?: number,
  days_to_response?: number,
  total_communications: number,
  admin_communications: number,
  brand_communications: number,
  last_communication_date?: string,
  proposal_viewed: boolean,
  brand_viewed_at?: string,
  versions_created: number,
  is_overdue: boolean,
  needs_follow_up: boolean
}
```

#### Get Pipeline Summary (Admin Only)
```typescript
GET /api/admin/proposals/pipeline-summary
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Response: {
  total_proposals: number,
  draft_proposals: number,
  sent_proposals: number,
  under_review: number,
  in_negotiation: number,
  approved_proposals: number,
  rejected_proposals: number,
  total_proposed_value: number,
  approved_value: number,
  conversion_rate: number,
  proposals_sent_this_month: number,
  responses_received_this_month: number,
  proposals_needing_follow_up: number,
  overdue_responses: number
}
```

### Templates

#### Get Proposal Templates (Admin Only)
```typescript
GET /api/admin/proposal-templates?service_type=influencer_marketing
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Query Parameters: {
  service_type?: 'influencer_marketing' | 'content_creation' | 'brand_strategy',
  category?: 'standard' | 'premium' | 'enterprise' | 'custom',
  is_active?: boolean
}
Response: {
  templates: ProposalTemplate[],
  total_count: number
}
```

#### Create Proposal Template (Admin Only)
```typescript
POST /api/admin/proposal-templates
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  template_name: string,
  template_description: string,
  service_type: 'influencer_marketing' | 'content_creation' | 'brand_strategy' | 'campaign_management',
  template_structure: TemplateStructure,
  default_budget_range?: {
    min: number,
    max: number
  },
  default_timeline_days?: number,
  category?: 'standard' | 'premium' | 'enterprise' | 'custom',
  tags?: string[]
}
Response: {
  id: string,
  template_name: string,
  created_at: string
}
```

#### Create Proposal from Template (Admin Only)
```typescript
POST /api/admin/proposals/from-template/{templateId}
Headers: {
  Authorization: "Bearer {admin_jwt_token}"
}
Body: {
  brand_user_id: string,
  proposal_title: string,
  customizations?: {
    proposed_budget_usd?: number,
    deliverables?: string[],
    service_description?: string,
    // ... other custom fields
  }
}
Response: {
  id: string,
  proposal_title: string,
  status: string,
  created_at: string
}
```

---

## Data Models

### TypeScript Interfaces

```typescript
interface AdminProposal {
  id: string;
  brand_user_id: string;
  created_by_admin_id: string;
  proposal_title: string;
  proposal_description: string;
  executive_summary?: string;
  service_type: 'influencer_marketing' | 'content_creation' | 'brand_strategy' | 'campaign_management';
  service_description: string;
  deliverables: string[];
  proposed_start_date?: string;
  proposed_end_date?: string;
  estimated_duration_days?: number;
  proposed_budget_usd: number;
  budget_breakdown?: Record<string, number>;
  payment_terms?: 'net_30' | 'net_15' | 'upfront' | 'milestone';
  campaign_objectives?: string[];
  target_audience_description?: string;
  expected_deliverables?: string[];
  success_metrics?: string[];
  expected_results?: string;
  status: 'draft' | 'sent' | 'under_review' | 'approved' | 'rejected' | 'negotiation' | 'closed';
  priority_level?: 'high' | 'medium' | 'low';
  brand_viewed_at?: string;
  brand_response_due_date?: string;
  brand_decision?: 'approved' | 'rejected' | 'counter_proposal' | 'needs_clarification';
  brand_feedback?: string;
  brand_counter_proposal?: CounterProposal;
  last_contact_date?: string;
  next_follow_up_date?: string;
  contact_attempts: number;
  admin_notes?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
  sent_at?: string;
  responded_at?: string;
  closed_at?: string;
  
  // Related data
  brand_user?: {
    id: string;
    email: string;
    name?: string;
  };
  versions?: ProposalVersion[];
  communications?: Communication[];
  analytics?: ProposalAnalytics[];
}

interface BrandProposal {
  id: string;
  proposal_title: string;
  proposal_description: string;
  executive_summary?: string;
  service_type: string;
  service_description: string;
  deliverables: string[];
  proposed_start_date?: string;
  proposed_end_date?: string;
  proposed_budget_usd: number;
  budget_breakdown?: Record<string, number>;
  payment_terms?: string;
  expected_results?: string;
  success_metrics?: string[];
  status: string;
  sent_at?: string;
  brand_response_due_date?: string;
  responded_at?: string;
  brand_decision?: string;
  brand_feedback?: string;
}

interface ProposalVersion {
  id: string;
  proposal_id: string;
  version_number: number;
  version_description: string;
  created_by_admin_id: string;
  proposal_data: Record<string, any>;
  changes_made: string[];
  created_at: string;
  is_current_version: boolean;
}

interface Communication {
  id: string;
  proposal_id: string;
  sender_admin_id?: string;
  sender_is_brand: boolean;
  communication_type: 'email' | 'phone_call' | 'meeting' | 'message' | 'document_shared';
  subject?: string;
  message_content: string;
  meeting_type?: 'video_call' | 'phone_call' | 'in_person' | 'presentation';
  meeting_duration_minutes?: number;
  meeting_attendees?: string[];
  shared_documents?: string[];
  action_items?: string[];
  follow_up_required?: boolean;
  follow_up_date?: string;
  delivery_status: 'sent' | 'delivered' | 'read' | 'responded';
  brand_response_required?: boolean;
  brand_responded?: boolean;
  created_at: string;
  scheduled_for?: string;
  completed_at?: string;
}

interface ProposalAnalytics {
  id: string;
  proposal_id: string;
  date_recorded: string;
  days_in_draft: number;
  days_sent_to_brand: number;
  days_under_review: number;
  days_in_negotiation: number;
  time_to_decision_days?: number;
  total_communications: number;
  admin_initiated_communications: number;
  brand_initiated_communications: number;
  meetings_held: number;
  documents_shared: number;
  proposal_views: number;
  time_spent_reviewing_minutes: number;
  sections_viewed: string[];
  conversion_stage: 'created' | 'sent' | 'viewed' | 'responded' | 'negotiated' | 'decided';
  conversion_probability?: number;
  proposed_value_usd: number;
  negotiated_value_usd?: number;
  discount_amount_usd?: number;
  discount_percentage?: number;
  final_decision?: 'approved' | 'rejected' | 'withdrawn';
  rejection_reason?: 'budget' | 'timeline' | 'services' | 'competition' | 'internal_decision';
  win_reason?: 'price' | 'services' | 'relationship' | 'expertise' | 'timeline';
  recorded_at: string;
}

interface ProposalTemplate {
  id: string;
  template_name: string;
  template_description: string;
  service_type: string;
  template_structure: TemplateStructure;
  default_budget_range?: {
    min: number;
    max: number;
  };
  default_timeline_days?: number;
  is_active: boolean;
  usage_count: number;
  created_by_admin_id: string;
  category?: 'standard' | 'premium' | 'enterprise' | 'custom';
  tags?: string[];
  created_at: string;
  updated_at: string;
  last_used_at?: string;
}

interface TemplateStructure {
  sections: TemplateSection[];
  default_values: Record<string, any>;
  required_fields: string[];
  conditional_fields: Record<string, any>;
}

interface TemplateSection {
  section_name: string;
  section_title: string;
  section_content: string;
  is_required: boolean;
  order_index: number;
  variables: TemplateVariable[];
}

interface TemplateVariable {
  variable_name: string;
  variable_type: 'text' | 'number' | 'date' | 'array' | 'object';
  display_name: string;
  default_value?: any;
  is_required: boolean;
  validation_rules?: Record<string, any>;
}

interface CounterProposal {
  requested_budget_usd?: number;
  requested_timeline_days?: number;
  requested_changes?: string[];
  additional_requirements?: string;
}

interface PipelineSummary {
  total_proposals: number;
  draft_proposals: number;
  sent_proposals: number;
  under_review: number;
  in_negotiation: number;
  approved_proposals: number;
  rejected_proposals: number;
  total_proposed_value: number;
  approved_value: number;
  conversion_rate: number;
  proposals_sent_this_month: number;
  responses_received_this_month: number;
  proposals_needing_follow_up: number;
  overdue_responses: number;
}

interface ProposalMetrics {
  proposal_id: string;
  proposal_title: string;
  status: string;
  proposed_budget_usd: number;
  service_type: string;
  created_at: string;
  sent_at?: string;
  responded_at?: string;
  days_since_created: number;
  days_since_sent?: number;
  days_to_response?: number;
  total_communications: number;
  admin_communications: number;
  brand_communications: number;
  last_communication_date?: string;
  proposal_viewed: boolean;
  brand_viewed_at?: string;
  versions_created: number;
  is_overdue: boolean;
  needs_follow_up: boolean;
}
```

---

## React Service Classes

### AdminProposalsService

```typescript
class AdminProposalsService {
  private baseUrl = '/api/admin/proposals';
  
  async createProposal(proposalData: CreateProposalRequest): Promise<AdminProposal> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAdminToken()}`
      },
      body: JSON.stringify(proposalData)
    });
    
    if (!response.ok) {
      throw new Error('Failed to create proposal');
    }
    
    return response.json();
  }
  
  async updateProposal(proposalId: string, updates: Partial<AdminProposal>): Promise<AdminProposal> {
    const response = await fetch(`${this.baseUrl}/${proposalId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAdminToken()}`
      },
      body: JSON.stringify(updates)
    });
    
    if (!response.ok) {
      throw new Error('Failed to update proposal');
    }
    
    return response.json();
  }
  
  async sendProposalToBrand(
    proposalId: string, 
    options?: SendProposalOptions
  ): Promise<SendProposalResponse> {
    const response = await fetch(`${this.baseUrl}/${proposalId}/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAdminToken()}`
      },
      body: JSON.stringify(options || {})
    });
    
    if (!response.ok) {
      throw new Error('Failed to send proposal');
    }
    
    return response.json();
  }
  
  async getAdminProposals(filters?: ProposalFilters): Promise<ProposalListResponse> {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.service_type) params.append('service_type', filters.service_type);
    if (filters?.priority_level) params.append('priority_level', filters.priority_level);
    if (filters?.min_budget) params.append('min_budget', filters.min_budget.toString());
    if (filters?.max_budget) params.append('max_budget', filters.max_budget.toString());
    if (filters?.limit) params.append('limit', filters.limit.toString());
    if (filters?.offset) params.append('offset', filters.offset.toString());
    
    const response = await fetch(`${this.baseUrl}?${params}`, {
      headers: {
        'Authorization': `Bearer ${getAdminToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch proposals');
    }
    
    return response.json();
  }
  
  async getProposalDetails(proposalId: string): Promise<AdminProposal> {
    const response = await fetch(`${this.baseUrl}/${proposalId}`, {
      headers: {
        'Authorization': `Bearer ${getAdminToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch proposal details');
    }
    
    return response.json();
  }
  
  async getProposalMetrics(proposalId: string): Promise<ProposalMetrics> {
    const response = await fetch(`${this.baseUrl}/${proposalId}/metrics`, {
      headers: {
        'Authorization': `Bearer ${getAdminToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch proposal metrics');
    }
    
    return response.json();
  }
  
  async getPipelineSummary(): Promise<PipelineSummary> {
    const response = await fetch(`${this.baseUrl}/pipeline-summary`, {
      headers: {
        'Authorization': `Bearer ${getAdminToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch pipeline summary');
    }
    
    return response.json();
  }
  
  async addCommunication(
    proposalId: string, 
    communication: CreateCommunicationRequest
  ): Promise<Communication> {
    const response = await fetch(`${this.baseUrl}/${proposalId}/communications`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAdminToken()}`
      },
      body: JSON.stringify(communication)
    });
    
    if (!response.ok) {
      throw new Error('Failed to add communication');
    }
    
    return response.json();
  }
}
```

### BrandProposalsService

```typescript
class BrandProposalsService {
  private baseUrl = '/api/brand/proposals';
  
  async getBrandProposals(): Promise<BrandProposalListResponse> {
    const response = await fetch(this.baseUrl, {
      headers: {
        'Authorization': `Bearer ${getBrandToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch brand proposals');
    }
    
    return response.json();
  }
  
  async getProposalDetails(proposalId: string): Promise<BrandProposal> {
    const response = await fetch(`${this.baseUrl}/${proposalId}`, {
      headers: {
        'Authorization': `Bearer ${getBrandToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch proposal details');
    }
    
    return response.json();
  }
  
  async submitResponse(
    proposalId: string, 
    response: BrandResponseRequest
  ): Promise<BrandResponseResponse> {
    const res = await fetch(`${this.baseUrl}/${proposalId}/respond`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getBrandToken()}`
      },
      body: JSON.stringify(response)
    });
    
    if (!res.ok) {
      throw new Error('Failed to submit response');
    }
    
    return res.json();
  }
}
```

---

## React Hooks

### useAdminProposals

```typescript
import { useState, useEffect } from 'react';
import { AdminProposalsService } from '../services/AdminProposalsService';

interface UseAdminProposalsOptions {
  filters?: ProposalFilters;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useAdminProposals(options: UseAdminProposalsOptions = {}) {
  const [proposals, setProposals] = useState<AdminProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  
  const service = new AdminProposalsService();
  
  const fetchProposals = async () => {
    try {
      setLoading(true);
      const response = await service.getAdminProposals(options.filters);
      setProposals(response.proposals);
      setTotalCount(response.total_count);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch proposals');
    } finally {
      setLoading(false);
    }
  };
  
  const createProposal = async (proposalData: CreateProposalRequest): Promise<AdminProposal> => {
    const newProposal = await service.createProposal(proposalData);
    await fetchProposals(); // Refresh list
    return newProposal;
  };
  
  const updateProposal = async (proposalId: string, updates: Partial<AdminProposal>): Promise<AdminProposal> => {
    const updatedProposal = await service.updateProposal(proposalId, updates);
    await fetchProposals(); // Refresh list
    return updatedProposal;
  };
  
  const sendProposal = async (proposalId: string, options?: SendProposalOptions): Promise<SendProposalResponse> => {
    const response = await service.sendProposalToBrand(proposalId, options);
    await fetchProposals(); // Refresh list
    return response;
  };
  
  useEffect(() => {
    fetchProposals();
    
    if (options.autoRefresh && options.refreshInterval) {
      const interval = setInterval(fetchProposals, options.refreshInterval);
      return () => clearInterval(interval);
    }
  }, [JSON.stringify(options.filters)]);
  
  return {
    proposals,
    loading,
    error,
    totalCount,
    fetchProposals,
    createProposal,
    updateProposal,
    sendProposal
  };
}
```

### useBrandProposals

```typescript
import { useState, useEffect } from 'react';
import { BrandProposalsService } from '../services/BrandProposalsService';

export function useBrandProposals() {
  const [proposals, setProposals] = useState<BrandProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const service = new BrandProposalsService();
  
  const fetchProposals = async () => {
    try {
      setLoading(true);
      const response = await service.getBrandProposals();
      setProposals(response.proposals);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch proposals');
    } finally {
      setLoading(false);
    }
  };
  
  const submitResponse = async (
    proposalId: string, 
    response: BrandResponseRequest
  ): Promise<BrandResponseResponse> => {
    const result = await service.submitResponse(proposalId, response);
    await fetchProposals(); // Refresh list
    return result;
  };
  
  useEffect(() => {
    fetchProposals();
  }, []);
  
  return {
    proposals,
    loading,
    error,
    fetchProposals,
    submitResponse
  };
}
```

### usePipelineMetrics

```typescript
import { useState, useEffect } from 'react';
import { AdminProposalsService } from '../services/AdminProposalsService';

export function usePipelineMetrics(refreshInterval = 30000) {
  const [metrics, setMetrics] = useState<PipelineSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const service = new AdminProposalsService();
  
  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const data = await service.getPipelineSummary();
      setMetrics(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchMetrics();
    
    const interval = setInterval(fetchMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);
  
  return {
    metrics,
    loading,
    error,
    fetchMetrics
  };
}
```

---

## Implementation Examples

### Admin Proposal Creation Form

```tsx
import React, { useState } from 'react';
import { useAdminProposals } from '../hooks/useAdminProposals';

interface ProposalFormProps {
  brandUserId?: string;
  onSuccess?: (proposal: AdminProposal) => void;
  onCancel?: () => void;
}

export function ProposalCreationForm({ brandUserId, onSuccess, onCancel }: ProposalFormProps) {
  const { createProposal, loading } = useAdminProposals();
  const [formData, setFormData] = useState<CreateProposalRequest>({
    brand_user_id: brandUserId || '',
    proposal_title: '',
    proposal_description: '',
    service_type: 'influencer_marketing',
    service_description: '',
    deliverables: [],
    proposed_budget_usd: 0,
    priority_level: 'medium'
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.brand_user_id) newErrors.brand_user_id = 'Brand is required';
    if (!formData.proposal_title) newErrors.proposal_title = 'Title is required';
    if (!formData.proposal_description) newErrors.proposal_description = 'Description is required';
    if (!formData.service_description) newErrors.service_description = 'Service description is required';
    if (formData.proposed_budget_usd <= 0) newErrors.proposed_budget_usd = 'Budget must be greater than 0';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    try {
      const proposal = await createProposal(formData);
      onSuccess?.(proposal);
    } catch (error) {
      setErrors({ general: 'Failed to create proposal' });
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Proposal Title
        </label>
        <input
          type="text"
          value={formData.proposal_title}
          onChange={(e) => setFormData({...formData, proposal_title: e.target.value})}
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
          placeholder="e.g., Q1 2024 Influencer Marketing Campaign"
        />
        {errors.proposal_title && (
          <p className="mt-1 text-sm text-red-600">{errors.proposal_title}</p>
        )}
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Service Type
        </label>
        <select
          value={formData.service_type}
          onChange={(e) => setFormData({...formData, service_type: e.target.value as any})}
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
        >
          <option value="influencer_marketing">Influencer Marketing</option>
          <option value="content_creation">Content Creation</option>
          <option value="brand_strategy">Brand Strategy</option>
          <option value="campaign_management">Campaign Management</option>
        </select>
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Proposal Description
        </label>
        <textarea
          value={formData.proposal_description}
          onChange={(e) => setFormData({...formData, proposal_description: e.target.value})}
          rows={4}
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
          placeholder="Detailed description of what we're proposing..."
        />
        {errors.proposal_description && (
          <p className="mt-1 text-sm text-red-600">{errors.proposal_description}</p>
        )}
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Service Description
        </label>
        <textarea
          value={formData.service_description}
          onChange={(e) => setFormData({...formData, service_description: e.target.value})}
          rows={3}
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
          placeholder="What services will we provide..."
        />
        {errors.service_description && (
          <p className="mt-1 text-sm text-red-600">{errors.service_description}</p>
        )}
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Proposed Budget (USD)
        </label>
        <input
          type="number"
          value={formData.proposed_budget_usd}
          onChange={(e) => setFormData({...formData, proposed_budget_usd: parseInt(e.target.value)})}
          min="1"
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
          placeholder="25000"
        />
        {errors.proposed_budget_usd && (
          <p className="mt-1 text-sm text-red-600">{errors.proposed_budget_usd}</p>
        )}
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700">
          Priority Level
        </label>
        <select
          value={formData.priority_level}
          onChange={(e) => setFormData({...formData, priority_level: e.target.value as any})}
          className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      
      {errors.general && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-600">{errors.general}</p>
        </div>
      )}
      
      <div className="flex justify-end space-x-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Create Proposal'}
        </button>
      </div>
    </form>
  );
}
```

### Brand Response Form

```tsx
import React, { useState } from 'react';
import { useBrandProposals } from '../hooks/useBrandProposals';

interface BrandResponseFormProps {
  proposal: BrandProposal;
  onSuccess?: () => void;
}

export function BrandResponseForm({ proposal, onSuccess }: BrandResponseFormProps) {
  const { submitResponse, loading } = useBrandProposals();
  const [response, setResponse] = useState<BrandResponseRequest>({
    decision: 'needs_clarification',
    feedback: ''
  });
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      await submitResponse(proposal.id, response);
      onSuccess?.();
    } catch (error) {
      console.error('Failed to submit response:', error);
    }
  };
  
  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900">
          {proposal.proposal_title}
        </h3>
        <p className="mt-1 text-sm text-gray-600">
          Service: {proposal.service_type} • Budget: ${proposal.proposed_budget_usd.toLocaleString()}
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Your Decision
          </label>
          <div className="mt-2 space-y-2">
            {[
              { value: 'approved', label: 'Approve Proposal', color: 'green' },
              { value: 'rejected', label: 'Reject Proposal', color: 'red' },
              { value: 'counter_proposal', label: 'Submit Counter Proposal', color: 'yellow' },
              { value: 'needs_clarification', label: 'Need More Information', color: 'blue' }
            ].map((option) => (
              <label key={option.value} className="flex items-center">
                <input
                  type="radio"
                  name="decision"
                  value={option.value}
                  checked={response.decision === option.value}
                  onChange={(e) => setResponse({...response, decision: e.target.value as any})}
                  className={`h-4 w-4 text-${option.color}-600`}
                />
                <span className="ml-2 text-sm text-gray-700">{option.label}</span>
              </label>
            ))}
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Feedback / Comments
          </label>
          <textarea
            value={response.feedback || ''}
            onChange={(e) => setResponse({...response, feedback: e.target.value})}
            rows={4}
            className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
            placeholder="Please provide your feedback..."
            required
          />
        </div>
        
        {response.decision === 'counter_proposal' && (
          <div className="border border-gray-200 rounded-md p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Counter Proposal Details</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-700">Requested Budget (USD)</label>
                <input
                  type="number"
                  value={response.counter_proposal?.requested_budget_usd || ''}
                  onChange={(e) => setResponse({
                    ...response,
                    counter_proposal: {
                      ...response.counter_proposal,
                      requested_budget_usd: parseInt(e.target.value)
                    }
                  })}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700">Requested Changes</label>
                <textarea
                  value={response.counter_proposal?.additional_requirements || ''}
                  onChange={(e) => setResponse({
                    ...response,
                    counter_proposal: {
                      ...response.counter_proposal,
                      additional_requirements: e.target.value
                    }
                  })}
                  rows={3}
                  className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                  placeholder="Describe your requested changes..."
                />
              </div>
            </div>
          </div>
        )}
        
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-blue-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Submitting...' : 'Submit Response'}
          </button>
        </div>
      </form>
    </div>
  );
}
```

### Pipeline Dashboard

```tsx
import React from 'react';
import { usePipelineMetrics } from '../hooks/usePipelineMetrics';

export function PipelineDashboard() {
  const { metrics, loading, error } = usePipelineMetrics();
  
  if (loading) return <div>Loading pipeline metrics...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!metrics) return <div>No metrics available</div>;
  
  const conversionRate = metrics.conversion_rate || 0;
  const totalValue = metrics.total_proposed_value || 0;
  const approvedValue = metrics.approved_value || 0;
  
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-2xl font-bold text-gray-900">{metrics.total_proposals}</div>
          <div className="text-sm text-gray-600">Total Proposals</div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-2xl font-bold text-green-600">{metrics.approved_proposals}</div>
          <div className="text-sm text-gray-600">Approved</div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-2xl font-bold text-blue-600">{conversionRate.toFixed(1)}%</div>
          <div className="text-sm text-gray-600">Conversion Rate</div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-2xl font-bold text-indigo-600">${approvedValue.toLocaleString()}</div>
          <div className="text-sm text-gray-600">Approved Value</div>
        </div>
      </div>
      
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Proposal Pipeline</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="font-medium text-gray-900">Draft</div>
            <div className="text-gray-600">{metrics.draft_proposals}</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">Sent</div>
            <div className="text-gray-600">{metrics.sent_proposals}</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">Under Review</div>
            <div className="text-gray-600">{metrics.under_review}</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">Negotiation</div>
            <div className="text-gray-600">{metrics.in_negotiation}</div>
          </div>
        </div>
      </div>
      
      {metrics.proposals_needing_follow_up > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <div className="flex">
            <div className="text-sm text-yellow-700">
              <strong>{metrics.proposals_needing_follow_up}</strong> proposals need follow-up
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

This updated guide now correctly reflects that the proposal system is between Admin (us) and Brands (users), with no influencer involvement. The system focuses on our admin team creating service proposals and managing the sales pipeline with potential brand clients.