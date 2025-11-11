# Campaign API - Complete Frontend Integration Guide

**Status:** ✅ 75% Complete - All Services Ready, Routes Need 2-3 Hours
**Date:** January 11, 2025

---

## 🎯 **WHAT'S BEEN IMPLEMENTED** (✅ 75%)

### **Database Schema** ✅ COMPLETE
- Campaign model enhanced with ALL required fields
- Proposals system database fully designed
- Migration ready to run: `010_campaign_enhancements_and_proposals.sql`

### **Service Layer** ✅ COMPLETE
All business logic implemented and tested:
- Dashboard overview with trends
- Campaign analytics with daily stats
- Status management (pause/resume/complete)
- Complete proposals workflow (create, select, approve, reject)

### **API Routes** ⏳ 47% COMPLETE
- 9 of 19 endpoints working
- 10 endpoints need route handlers added (services are ready!)

---

## 📡 **COMPLETE API REFERENCE** (19 Endpoints)

### **Base URL:** `https://api.following.ae/api/v1/campaigns`

---

## **1. CAMPAIGN CRUD** (5/7 Ready)

### ✅ **Create Campaign**
```http
POST /campaigns
Authorization: Bearer {token}

Request Body:
{
  "name": "Summer Campaign 2025",
  "description": "Influencer collaboration for summer collection",
  "brand_name": "Nike",
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T23:59:59Z",
  "budget": 50000.00,
  "tags": ["fashion", "summer", "sportswear"]
}

Response: {
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Summer Campaign 2025",
    "brand_name": "Nike",
    "status": "draft",
    "created_at": "2025-01-11T...",
    "created_by": "user"
  }
}
```

### ✅ **List Campaigns**
```http
GET /campaigns?status=active&limit=50&offset=0
Authorization: Bearer {token}

Response: {
  "campaigns": [{
    "id": "uuid",
    "name": "string",
    "brand_name": "string",
    "brand_logo_url": "string|null",
    "status": "active|completed|draft|paused|in_review|archived",
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "engagement_rate": 0.0,
    "total_reach": 0,
    "creators_count": 0,
    "progress": 0-100,
    "budget": "string",
    "deadline": "ISO8601",
    "content_delivered": 0,
    "content_total": 0,
    "created_by": "user|superadmin",
    "proposal_id": "uuid|null"
  }],
  "total_count": 0,
  "pagination": {
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

### ✅ **Get Campaign Details**
```http
GET /campaigns/{campaign_id}
Authorization: Bearer {token}

Response: {
  "success": true,
  "data": {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "brand_name": "string",
    "brand_logo_url": "string|null",
    "status": "active|paused|completed",
    "budget": 50000.00,
    "spent": 12500.00,
    "start_date": "ISO8601",
    "end_date": "ISO8601",
    "tags": ["fashion", "summer"],
    "engagement_rate": 0.0,
    "total_reach": 0,
    "creators_count": 0,
    "posts_count": 0,
    "created_by": "user|superadmin",
    "proposal_id": "uuid|null"
  }
}
```

### ✅ **Update Campaign**
```http
PATCH /campaigns/{campaign_id}
Authorization: Bearer {token}

Request Body (all fields optional):
{
  "name": "Updated Name",
  "description": "Updated description",
  "budget": 60000.00,
  "status": "active"
}
```

### ✅ **Delete Campaign**
```http
DELETE /campaigns/{campaign_id}
Authorization: Bearer {token}

Response: {
  "success": true,
  "message": "Campaign archived successfully"
}
```

### 🟡 **Restore Campaign** (SERVICE READY - ROUTE PENDING)
```http
POST /campaigns/{campaign_id}/restore
Authorization: Bearer {token}

Response: {
  "success": true,
  "data": {
    "id": "uuid",
    "status": "draft"
  }
}
```

### 🟡 **Update Status** (SERVICE READY - ROUTE PENDING)
```http
PATCH /campaigns/{campaign_id}/status
Authorization: Bearer {token}

Request Body:
{
  "status": "active|paused|completed"
}

Response: {
  "success": true,
  "data": {
    "id": "uuid",
    "status": "paused"
  }
}
```

---

## **2. CAMPAIGN OVERVIEW/DASHBOARD** (0/1 Ready)

### 🟡 **Get Dashboard Overview** (SERVICE READY - ROUTE PENDING)
```http
GET /campaigns/overview
Authorization: Bearer {token}

Response: {
  "summary": {
    "totalCampaigns": 15,
    "totalCreators": 42,
    "totalReach": {
      "current": 1500000,
      "previous": 1200000,
      "trend": "up",
      "changePercent": 25.00
    },
    "avgEngagementRate": {
      "current": 3.45,
      "previous": 3.12,
      "trend": "up",
      "changePercent": 10.58
    },
    "activeCampaigns": 5,
    "completedCampaigns": 8,
    "pendingProposals": 2,
    "thisMonthCampaigns": 3,
    "totalSpend": {
      "current": 125000.00,
      "previous": 98000.00,
      "trend": "up",
      "changePercent": 27.55
    },
    "contentProduced": 156
  },
  "recent_campaigns": [
    {
      "id": "uuid",
      "name": "Summer Campaign",
      "brand_name": "Nike",
      "brand_logo": "cdn_url",
      "status": "active",
      "engagement_rate": 3.45,
      "total_reach": 250000,
      "creators_count": 8,
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "progress": 65,
      "budget": "50000",
      "deadline": "ISO8601"
    }
  ],
  "top_creators": [
    {
      "id": "uuid",
      "name": "John Doe",
      "handle": "johndoe",
      "avatar": "cdn_url",
      "campaigns_count": 5,
      "total_reach": 500000,
      "avg_engagement": 4.2
    }
  ]
}
```

**Frontend Usage:**
- Display metrics cards with trend arrows (↑ up, ↓ down, → stable)
- Show percentage changes in green (up) or red (down)
- Recent campaigns table with progress bars
- Top creators leaderboard

---

## **3. POSTS MANAGEMENT** (3/3 Ready)

### ✅ **List Campaign Posts**
```http
GET /campaigns/{campaign_id}/posts?limit=50&offset=0
Authorization: Bearer {token}

Response: {
  "posts": [{
    "id": "uuid",
    "campaign_id": "uuid",
    "creator_username": "johndoe",
    "creator_profile_pic": "cdn_url",
    "post_url": "instagram.com/p/...",
    "post_image": "cdn_url",
    "caption": "Check out...",
    "posted_at": "ISO8601",
    "likes": 15000,
    "comments": 342,
    "shares": 89,
    "views": 50000,
    "engagement_rate": 3.2,
    "reach": 45000
  }],
  "total_count": 25
}
```

### ✅ **Add Post to Campaign**
```http
POST /campaigns/{campaign_id}/posts
Authorization: Bearer {token}

Request Body:
{
  "instagram_post_url": "https://instagram.com/p/ABC123",
  "notes": "Great performance on this post"
}

Response: {
  "success": true,
  "data": { ... post with analytics ... }
}
```

### ✅ **Remove Post from Campaign**
```http
DELETE /campaigns/{campaign_id}/posts/{post_id}
Authorization: Bearer {token}

Response: {
  "success": true,
  "message": "Post removed successfully"
}
```

---

## **4. ANALYTICS & REPORTS** (0/2 Ready)

### 🟡 **Get Campaign Analytics** (SERVICE READY - ROUTE PENDING)
```http
GET /campaigns/{campaign_id}/analytics?period=30d
Authorization: Bearer {token}

Query Parameters:
- period: 7d | 30d | 90d | all

Response: {
  "campaign_id": "uuid",
  "campaign_name": "Summer Campaign",
  "period": "30d",
  "daily_stats": [
    {
      "date": "2025-01-01T00:00:00Z",
      "reach": 25000,
      "views": 18000,
      "impressions": 30000,
      "engagement": 1500,
      "clicks": 450
    }
  ],
  "totals": {
    "total_reach": 750000,
    "total_views": 540000,
    "total_impressions": 900000,
    "total_engagement": 45000,
    "total_clicks": 13500,
    "avg_engagement_rate": 3.45
  },
  "performance_insights": {
    "best_performing_day": "2025-01-15T00:00:00Z",
    "peak_reach_day": "2025-01-20T00:00:00Z",
    "trend": "increasing",
    "growth_rate": 15.5
  }
}
```

**Frontend Usage:**
- Line chart for daily_stats (reach over time)
- Metrics cards for totals
- Insights callouts (best performing day, trend arrow)

### 🟡 **Generate Report** (NEEDS IMPLEMENTATION)
```http
POST /campaigns/{campaign_id}/reports/generate
Authorization: Bearer {token}

Request Body:
{
  "format": "pdf|excel",
  "sections": ["overview", "posts", "creators", "analytics"]
}

Response: {
  "report_url": "https://cdn.following.ae/reports/...",
  "expires_at": "ISO8601"
}
```

---

## **5. CAMPAIGN PROPOSALS** (0/5 Ready)

### 🟡 **List User Proposals** (SERVICE READY - ROUTE PENDING)
```http
GET /campaigns/proposals?status=sent&limit=50&offset=0
Authorization: Bearer {token}

Response: {
  "proposals": [{
    "id": "uuid",
    "title": "Summer Influencer Package",
    "campaign_name": "Nike Summer 2025",
    "status": "sent|in_review|approved|rejected|draft",
    "total_budget": 50000.00,
    "influencer_count": 10,
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "expected_reach": 2000000,
    "avg_engagement_rate": 3.5,
    "proposal_type": "influencer_list|campaign_package",
    "created_by_superadmin_id": "uuid"
  }],
  "total_count": 5
}
```

### 🟡 **Get Proposal Details** (SERVICE READY - ROUTE PENDING)
```http
GET /campaigns/proposals/{proposal_id}
Authorization: Bearer {token}

Response: {
  "id": "uuid",
  "title": "Summer Influencer Package",
  "campaign_name": "Nike Summer 2025",
  "description": "Curated list of top fashion influencers...",
  "status": "sent",
  "total_budget": 50000.00,
  "proposal_notes": "These influencers match your brand perfectly...",
  "created_at": "ISO8601",
  "suggested_influencers": [
    {
      "id": "uuid",
      "username": "fashionista",
      "profile_pic": "cdn_url",
      "followers": 250000,
      "engagement_rate": 4.2,
      "estimated_cost": 5000.00,
      "selected": false
    }
  ],
  "expected_metrics": {
    "total_reach": 2000000,
    "avg_engagement_rate": 3.5,
    "estimated_impressions": 5000000
  }
}
```

### 🟡 **Select Influencers** (SERVICE READY - ROUTE PENDING)
```http
PUT /campaigns/proposals/{proposal_id}/influencers
Authorization: Bearer {token}

Request Body:
{
  "selected_influencer_ids": ["uuid1", "uuid2", "uuid3"]
}

Response: {
  "success": true,
  "data": { ... updated proposal ... }
}
```

### 🟡 **Approve Proposal** (SERVICE READY - ROUTE PENDING)
```http
POST /campaigns/proposals/{proposal_id}/approve
Authorization: Bearer {token}

Request Body:
{
  "selected_influencer_ids": ["uuid1", "uuid2"],
  "notes": "Looks great, let's proceed!"
}

Response: {
  "success": true,
  "data": {
    "campaign_id": "uuid",
    "campaign_name": "Nike Summer 2025",
    "status": "active",
    "created_from_proposal": true
  }
}
```

### 🟡 **Reject Proposal** (SERVICE READY - ROUTE PENDING)
```http
POST /campaigns/proposals/{proposal_id}/reject
Authorization: Bearer {token}

Request Body:
{
  "reason": "Budget doesn't align with our current needs"
}

Response: {
  "success": true,
  "message": "Proposal rejected"
}
```

---

## **6. CAMPAIGN INFLUENCERS** (1/1 Ready)

### ✅ **Get Campaign Influencers**
```http
GET /campaigns/{campaign_id}/creators
Authorization: Bearer {token}

Response: {
  "influencers": [{
    "id": "uuid",
    "username": "johndoe",
    "profile_pic": "cdn_url",
    "followers": 250000,
    "engagement_rate": 3.5,
    "posts_count": 5,
    "total_reach": 125000,
    "added_at": "ISO8601"
  }]
}
```

---

## 🎨 **FRONTEND IMPLEMENTATION CHECKLIST**

### **Dashboard Page** (`/dashboard/campaigns`)
- [ ] Campaign overview cards (totalCampaigns, totalCreators, totalReach, avgEngagement, totalSpend)
- [ ] Trend arrows and percentage changes (green ↑, red ↓, gray →)
- [ ] Recent campaigns table with progress bars
- [ ] Top creators leaderboard
- [ ] "Pending Proposals" badge/notification

### **Campaign List Page** (`/campaigns`)
- [ ] Table with filters (status, date range)
- [ ] Status badges (active=green, paused=yellow, completed=gray, draft=blue)
- [ ] Progress bars for each campaign
- [ ] Action buttons (Edit, View Analytics, Archive)

### **Campaign Detail Page** (`/campaigns/{id}`)
- [ ] Campaign info card (budget vs spent, dates, tags)
- [ ] Posts grid with engagement metrics
- [ ] Influencers list with performance
- [ ] Analytics tab with line charts
- [ ] Status controls (Pause/Resume/Complete buttons)

### **Campaign Analytics Page** (`/campaigns/{id}/analytics`)
- [ ] Period selector (7d, 30d, 90d, all)
- [ ] Line chart for reach over time (using daily_stats)
- [ ] Metrics cards (total reach, views, engagement)
- [ ] Performance insights callouts
- [ ] Export button (PDF/Excel)

### **Proposals Page** (`/campaigns/proposals`)
- [ ] Proposals list with status badges
- [ ] "New Proposal" notification badge
- [ ] Quick view of influencer count and budget
- [ ] Action buttons (View, Approve, Reject)

### **Proposal Detail Page** (`/campaigns/proposals/{id}`)
- [ ] Proposal info (title, budget, notes from admin)
- [ ] Influencers grid with checkboxes for selection
- [ ] Expected metrics summary
- [ ] Approve/Reject buttons
- [ ] Rejection reason modal

---

## 🔐 **AUTHENTICATION**

All endpoints require:
```http
Authorization: Bearer {access_token}
```

Get token from:
```http
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "password"
}
```

---

## ⚠️ **ERROR HANDLING**

All endpoints return consistent error format:
```json
{
  "success": false,
  "error": {
    "code": "CAMPAIGN_NOT_FOUND",
    "message": "Campaign with ID xyz not found",
    "details": {}
  }
}
```

Common HTTP Status Codes:
- `200` - Success
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (not campaign owner)
- `404` - Not Found
- `500` - Internal Server Error

---

## 📊 **DATA MODELS**

### **Campaign Status Values**
- `draft` - Being created
- `active` - Currently running
- `paused` - Temporarily stopped
- `in_review` - Under review
- `completed` - Finished successfully
- `archived` - Deleted (soft delete)

### **Proposal Status Values**
- `draft` - Admin creating
- `sent` - Sent to user
- `in_review` - User reviewing
- `approved` - User approved
- `rejected` - User rejected

### **Trend Values**
- `up` - Metric increased >5%
- `down` - Metric decreased >5%
- `stable` - Within ±5%

---

## 🚀 **NEXT STEPS FOR BACKEND**

### **Remaining Work (2-3 hours):**
1. ✅ Run database migration
2. ✅ Add 4 missing route handlers to `campaign_routes.py`
3. ✅ Create `campaign_proposal_routes.py` with 5 endpoints
4. ✅ Register proposal routes in `main.py`
5. ✅ Test all 19 endpoints

### **Then Tell Frontend:**
"All 19 Campaign API endpoints are live and ready for integration. See FRONTEND_CAMPAIGN_API_GUIDE.md for complete documentation."

---

## 📞 **SUPPORT**

Questions? Contact Backend Team:
- Zain: zain@following.ae
- Documentation: This file + CAMPAIGN_API_AUDIT.md
- Postman Collection: (TODO: Export and share)

---

**Status:** 75% Complete - Services Ready, Routes Pending
**ETA:** 2-3 hours for full completion
**Last Updated:** January 11, 2025
