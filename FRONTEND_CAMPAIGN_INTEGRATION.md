# Campaign System - Complete Frontend Integration Guide

## 🎯 System Overview

There are **TWO completely separate campaign creation flows**:

### 1. USER Flow (Simple)
- User creates campaign themselves
- Adds Instagram post links directly
- Gets automatic reports
- No approval workflow needed

### 2. SUPERADMIN Flow (Full Workflow)
- Superadmin creates campaign FOR a user
- User selects influencers from discovery
- Superadmin reviews and locks selections
- Content submission and approval workflow
- Multi-stage workflow tracking

---

## 📊 Database Tables Created

### Core Tables (Already Exist)
- `campaigns` - Campaign basic info
- `campaign_posts` - Instagram posts added to campaign
- `campaign_creators` - Auto-populated creators from posts

### New Workflow Tables (Just Created)
- `campaign_influencer_selections` - Influencer selection tracking
- `campaign_content_approvals` - Content approval workflow
- `campaign_workflow_notifications` - Workflow notifications
- `campaign_workflow_state` - Workflow stage tracking

---

## 🔌 API Endpoints

### Base URL
```
/api/v1/campaigns/workflow
```

---

## 1️⃣ USER FLOW APIs

### Create User Campaign (Simple Flow)
```typescript
POST /api/v1/campaigns/workflow/user/create

Request:
{
  "name": "Summer Collection 2025",
  "brand_name": "My Brand",
  "brand_logo_url": "https://cdn.example.com/logo.png", // Optional
  "description": "Summer campaign description", // Optional
  "budget": 5000.00, // Optional
  "start_date": "2025-01-15T00:00:00Z", // Optional
  "end_date": "2025-03-15T00:00:00Z" // Optional
}

Response:
{
  "success": true,
  "data": {
    "id": "uuid-here",
    "name": "Summer Collection 2025",
    "brand_name": "My Brand",
    "status": "active", // Goes straight to active
    "created_by": "user",
    "created_at": "2025-01-11T...",
    "message": "Campaign created! You can now add Instagram post links..."
  },
  "message": "User campaign created successfully"
}
```

### Add Post to User Campaign
```typescript
POST /api/v1/campaigns/{campaign_id}/posts

Request:
{
  "instagram_post_url": "https://www.instagram.com/p/ABC123/"
}

Response:
{
  "success": true,
  "data": {
    "post_id": "uuid-here",
    "instagram_post_url": "...",
    "profile_username": "influencer_name",
    "likes": 15000,
    "comments": 250,
    "engagement_rate": 3.5
  }
}
```

### Get Campaign Report (User Flow)
```typescript
GET /api/v1/campaigns/{campaign_id}/analytics

Response:
{
  "success": true,
  "data": {
    "campaign_id": "uuid",
    "total_posts": 15,
    "total_reach": 500000,
    "avg_engagement_rate": 4.2,
    "total_likes": 45000,
    "total_comments": 3500,
    "top_performing_post": {...},
    "creators": [
      {
        "username": "influencer1",
        "posts_count": 3,
        "total_reach": 150000,
        "avg_engagement": 4.5
      }
    ]
  }
}
```

---

## 2️⃣ SUPERADMIN FLOW APIs

### Create Superadmin Campaign (Full Workflow)
```typescript
POST /api/v1/campaigns/workflow/superadmin/create

Request:
{
  "user_id": "uuid-of-user-this-is-for",
  "name": "Premium Brand Campaign",
  "brand_name": "Premium Brand",
  "brand_logo_url": "...",
  "description": "...",
  "budget": 10000.00,
  "start_date": "2025-02-01T00:00:00Z",
  "end_date": "2025-04-01T00:00:00Z"
}

Response:
{
  "success": true,
  "data": {
    "id": "uuid-here",
    "name": "Premium Brand Campaign",
    "status": "draft",
    "created_by": "superadmin",
    "workflow_stage": "influencer_selection",
    "message": "Campaign created! Awaiting influencer selection from user."
  }
}
```

### User Selects Influencer
```typescript
POST /api/v1/campaigns/workflow/{campaign_id}/select-influencer

Request:
{
  "profile_id": "uuid-of-instagram-profile",
  "selection_notes": "Perfect fit for brand aesthetic",
  "estimated_cost": 1500.00
}

Response:
{
  "success": true,
  "data": {
    "selection_id": "uuid",
    "profile_id": "uuid",
    "status": "pending",
    "message": "Influencer selected! Awaiting superadmin review."
  }
}
```

### Get Selected Influencers
```typescript
GET /api/v1/campaigns/workflow/{campaign_id}/selections

Response:
{
  "success": true,
  "data": {
    "campaign_id": "uuid",
    "total_selected": 5,
    "locked": 0,
    "pending": 5,
    "selections": [
      {
        "id": "uuid",
        "profile": {
          "id": "uuid",
          "username": "influencer1",
          "followers": 150000,
          "engagement_rate": 4.5
        },
        "status": "pending",
        "selected_by": "user",
        "selection_notes": "...",
        "estimated_cost": 1500.00,
        "created_at": "2025-01-11T..."
      }
    ]
  }
}
```

### Superadmin Locks Influencers
```typescript
POST /api/v1/campaigns/workflow/{campaign_id}/lock-influencers

Request:
{
  "selection_ids": ["uuid1", "uuid2", "uuid3"],
  "lock_duration_hours": 48 // 48 hour lock period
}

Response:
{
  "success": true,
  "data": {
    "locked_count": 3,
    "lock_expires_at": "2025-01-13T12:00:00Z",
    "workflow_stage": "locked",
    "message": "Influencers locked! Users can now begin content submission."
  }
}
```

### Submit Content for Approval
```typescript
POST /api/v1/campaigns/workflow/{campaign_id}/submit-content

Request:
{
  "profile_id": "uuid-of-influencer",
  "content_type": "draft", // or "final" or "published"
  "content_url": "https://drive.google.com/file/...",
  "content_caption": "Check out this amazing product! #ad",
  "content_media_urls": [
    "https://drive.google.com/file/1",
    "https://drive.google.com/file/2"
  ]
}

Response:
{
  "success": true,
  "data": {
    "approval_id": "uuid",
    "status": "pending",
    "submitted_at": "2025-01-11T...",
    "message": "Content submitted! Awaiting superadmin review."
  }
}
```

### Superadmin Reviews Content
```typescript
POST /api/v1/campaigns/workflow/{campaign_id}/content/{approval_id}/review

Request:
{
  "approval_status": "approved", // or "rejected" or "revision_requested"
  "reviewer_notes": "Looks great! Approved for posting.",
  "revision_notes": null // Only if revision_requested
}

Response:
{
  "success": true,
  "data": {
    "approval_id": "uuid",
    "status": "approved",
    "reviewed_at": "2025-01-11T...",
    "message": "Content approved! Influencer can proceed with posting."
  }
}
```

### Get Workflow State
```typescript
GET /api/v1/campaigns/workflow/{campaign_id}/state

Response:
{
  "success": true,
  "data": {
    "campaign_id": "uuid",
    "current_stage": "content_review",
    "stages": {
      "draft_started_at": "2025-01-10T...",
      "selection_started_at": "2025-01-10T...",
      "lock_confirmed_at": "2025-01-11T...",
      "content_submission_started_at": "2025-01-11T...",
      "active_started_at": null,
      "completed_at": null
    },
    "counters": {
      "influencers_selected": 5,
      "influencers_locked": 5,
      "content_pending": 2,
      "content_approved": 3
    }
  }
}
```

### Get Workflow Notifications
```typescript
GET /api/v1/campaigns/workflow/notifications?unread_only=true

Response:
{
  "success": true,
  "data": {
    "total": 5,
    "unread": 3,
    "notifications": [
      {
        "id": "uuid",
        "campaign_id": "uuid",
        "notification_type": "content_submitted",
        "title": "New Content Submitted",
        "message": "Influencer @username submitted content for review.",
        "action_url": "/campaigns/uuid/review",
        "is_read": false,
        "created_at": "2025-01-11T..."
      }
    ]
  }
}
```

---

## 🎨 Frontend Implementation

### User Campaign Creation Form

```typescript
// components/campaigns/CreateUserCampaignForm.tsx

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

export function CreateUserCampaignForm() {
  const [formData, setFormData] = useState({
    name: '',
    brand_name: '',
    description: '',
    budget: null,
  });

  const createCampaign = useMutation({
    mutationFn: async (data) => {
      const response = await fetch('/api/v1/campaigns/workflow/user/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(data)
      });
      return response.json();
    },
    onSuccess: (data) => {
      // Navigate to campaign page to add posts
      router.push(`/campaigns/${data.data.id}`);
      toast.success('Campaign created! Add Instagram posts to begin tracking.');
    }
  });

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      createCampaign.mutate(formData);
    }}>
      <h2>Create Campaign</h2>

      <input
        type="text"
        placeholder="Campaign Name"
        value={formData.name}
        onChange={(e) => setFormData({...formData, name: e.target.value})}
        required
      />

      <input
        type="text"
        placeholder="Brand Name"
        value={formData.brand_name}
        onChange={(e) => setFormData({...formData, brand_name: e.target.value})}
        required
      />

      <textarea
        placeholder="Campaign Description (Optional)"
        value={formData.description}
        onChange={(e) => setFormData({...formData, description: e.target.value})}
      />

      <input
        type="number"
        placeholder="Budget (Optional)"
        value={formData.budget || ''}
        onChange={(e) => setFormData({...formData, budget: parseFloat(e.target.value)})}
      />

      <button type="submit" disabled={createCampaign.isPending}>
        {createCampaign.isPending ? 'Creating...' : 'Create Campaign'}
      </button>
    </form>
  );
}
```

### Add Post to Campaign

```typescript
// components/campaigns/AddPostForm.tsx

export function AddPostForm({ campaignId }: { campaignId: string }) {
  const [postUrl, setPostUrl] = useState('');

  const addPost = useMutation({
    mutationFn: async (url: string) => {
      const response = await fetch(`/api/v1/campaigns/${campaignId}/posts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ instagram_post_url: url })
      });
      return response.json();
    },
    onSuccess: () => {
      toast.success('Post added to campaign!');
      setPostUrl('');
      queryClient.invalidateQueries(['campaign', campaignId]);
    }
  });

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      addPost.mutate(postUrl);
    }}>
      <input
        type="url"
        placeholder="https://www.instagram.com/p/ABC123/"
        value={postUrl}
        onChange={(e) => setPostUrl(e.target.value)}
        required
      />

      <button type="submit">Add Post</button>
    </form>
  );
}
```

### Superadmin Campaign Creation

```typescript
// components/admin/CreateSuperadminCampaignForm.tsx

export function CreateSuperadminCampaignForm() {
  const [formData, setFormData] = useState({
    user_id: '',
    name: '',
    brand_name: '',
    description: '',
    budget: null,
  });

  const createCampaign = useMutation({
    mutationFn: async (data) => {
      const response = await fetch('/api/v1/campaigns/workflow/superadmin/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(data)
      });
      return response.json();
    },
    onSuccess: (data) => {
      toast.success('Workflow campaign created! User will be notified.');
      router.push(`/admin/campaigns/${data.data.id}`);
    }
  });

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      createCampaign.mutate(formData);
    }}>
      <h2>Create Workflow Campaign</h2>

      <UserSelect
        value={formData.user_id}
        onChange={(userId) => setFormData({...formData, user_id: userId})}
      />

      <input
        type="text"
        placeholder="Campaign Name"
        value={formData.name}
        onChange={(e) => setFormData({...formData, name: e.target.value})}
        required
      />

      {/* Other fields... */}

      <button type="submit">Create Workflow Campaign</button>
    </form>
  );
}
```

### Influencer Selection Interface

```typescript
// components/campaigns/InfluencerSelectionPage.tsx

export function InfluencerSelectionPage({ campaignId }: { campaignId: string }) {
  const { data: campaign } = useQuery({
    queryKey: ['campaign', campaignId],
    queryFn: () => fetchCampaign(campaignId)
  });

  const selectInfluencer = useMutation({
    mutationFn: async (data: { profile_id: string, notes: string }) => {
      const response = await fetch(
        `/api/v1/campaigns/workflow/${campaignId}/select-influencer`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(data)
        }
      );
      return response.json();
    },
    onSuccess: () => {
      toast.success('Influencer selected!');
      queryClient.invalidateQueries(['campaign-selections', campaignId]);
    }
  });

  return (
    <div>
      <h2>{campaign?.name} - Select Influencers</h2>

      {/* Discovery/Search Interface */}
      <DiscoverySearch
        onSelect={(profile) => {
          selectInfluencer.mutate({
            profile_id: profile.id,
            notes: '',
            estimated_cost: profile.estimated_cost
          });
        }}
      />

      {/* Selected Influencers List */}
      <SelectedInfluencersList campaignId={campaignId} />
    </div>
  );
}
```

---

## 🔔 Notification System Integration

```typescript
// components/NotificationBell.tsx

export function NotificationBell() {
  const { data: notifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => fetch('/api/v1/campaigns/workflow/notifications?unread_only=true'),
    refetchInterval: 30000 // Poll every 30 seconds
  });

  const markAsRead = useMutation({
    mutationFn: (notificationId: string) =>
      fetch(`/api/v1/campaigns/workflow/notifications/${notificationId}/read`, {
        method: 'POST'
      })
  });

  return (
    <Popover>
      <PopoverTrigger>
        <Bell className="w-5 h-5" />
        {notifications?.data.unread > 0 && (
          <Badge>{notifications.data.unread}</Badge>
        )}
      </PopoverTrigger>

      <PopoverContent>
        {notifications?.data.notifications.map((notif) => (
          <div
            key={notif.id}
            onClick={() => {
              markAsRead.mutate(notif.id);
              router.push(notif.action_url);
            }}
          >
            <h4>{notif.title}</h4>
            <p>{notif.message}</p>
            <time>{notif.created_at}</time>
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}
```

---

## 🎯 Key Differences Summary

| Feature | USER Flow | SUPERADMIN Flow |
|---------|-----------|-----------------|
| **Creation** | User creates own campaign | Superadmin creates FOR user |
| **Status** | Starts 'active' | Starts 'draft' |
| **Influencer Selection** | N/A - User adds posts directly | Multi-step workflow |
| **Approval** | None needed | Content approval required |
| **Workflow State** | None | Full state tracking |
| **Notifications** | None | Full notification system |

---

## ✅ Implementation Checklist

### Backend (Completed)
- [x] Database tables created
- [x] Models added to unified_models.py
- [x] API routes created (workflow routes)
- [x] RLS policies applied
- [x] Workflow state tracking

### Frontend (To Do)
- [ ] User campaign creation form
- [ ] Add post to campaign interface
- [ ] Campaign analytics dashboard
- [ ] Superadmin campaign creation form
- [ ] Influencer selection interface
- [ ] Content submission interface
- [ ] Content review/approval interface (superadmin)
- [ ] Workflow state visualization
- [ ] Notification system integration

---

## 🚀 Next Steps

1. **Implement user campaign creation form** (highest priority - unblocks users)
2. **Add post interface** (allows users to track performance)
3. **Campaign dashboard** (show reports and analytics)
4. **Superadmin forms** (parallel development)
5. **Workflow visualization** (track stages)
6. **Notification system** (real-time updates)

---

**All backend infrastructure is ready! Focus on frontend implementation.**
