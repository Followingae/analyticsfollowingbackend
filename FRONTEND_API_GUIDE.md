# Campaign Module - Complete Frontend Integration Guide

## 🎯 Overview
This guide provides the complete mapping between Frontend requirements and Backend API endpoints with exact field names and response structures.

---

## 📡 API Endpoints & Field Mapping

### 1. Campaigns List Page (`/campaigns`)

**Endpoint:** `GET /api/v1/campaigns/`

**Query Parameters:**
- `status_filter` (optional): "draft" | "active" | "completed"
- `limit` (optional, default: 50): Max results per page
- `offset` (optional, default: 0): Pagination offset

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "campaigns": [
      {
        "id": "f15257b4-f220-4bc2-a0a7-68e903d2906a",
        "name": "Summer Campaign 2025",
        "brand_name": "Nike",
        "brand_logo_url": "https://cdn.following.ae/brand-logos/...",
        "status": "active",
        "created_at": "2025-09-26T10:30:00Z",
        "updated_at": "2025-10-01T15:22:00Z",

        // ✅ Per-Campaign Statistics
        "creators_count": 7,
        "posts_count": 12,
        "total_reach": 5000000,
        "engagement_rate": 0.1382
      }
    ],

    // ✅ Dashboard Summary Cards
    "summary": {
      "totalCampaigns": 5,
      "totalCreators": 25,
      "totalReach": 15000000,
      "avgEngagementRate": 0.12
    },

    "pagination": {
      "limit": 50,
      "offset": 0,
      "total": 5,
      "has_more": false
    }
  }
}
```

**Frontend Display Mapping:**

| Frontend Field | Backend Field | Display Format |
|---|---|---|
| ID (8 chars) | `id` | `id.substring(0,8).toUpperCase()` |
| Campaign Name | `name` | As-is |
| Status Badge | `status` | Badge with color (draft/active/completed) |
| Brand Name | `brand_name` | As-is |
| Brand Logo | `brand_logo_url` | `<img src={brand_logo_url \|\| '/placeholder.png'} />` |
| Creators Count | `creators_count` | Number with comma separator |
| Posts Count | `posts_count` | Number with comma separator |
| Total Reach | `total_reach` | `total_reach.toLocaleString()` followers |
| Engagement Rate | `engagement_rate` | `(engagement_rate * 100).toFixed(2)}%` |
| Created Date | `created_at` | `new Date(created_at).toLocaleDateString()` |

**Dashboard Summary Cards:**
```typescript
// Total Campaigns
<Card value={summary.totalCampaigns} label="Total Campaigns" />

// Total Creators
<Card value={summary.totalCreators.toLocaleString()} label="Total Creators" />

// Total Reach
<Card value={summary.totalReach.toLocaleString()} label="Total Reach" />

// Avg Engagement
<Card value={(summary.avgEngagementRate * 100).toFixed(2) + '%'} label="Avg Engagement" />
```

---

### 2. Campaign Details - Stats Tab

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}`

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "id": "f15257b4-f220-4bc2-a0a7-68e903d2906a",
    "name": "Summer Campaign 2025",
    "brand_name": "Nike",
    "brand_logo_url": "https://...",
    "status": "active",
    "user_id": "uuid",
    "created_at": "2025-09-26T10:30:00Z",
    "updated_at": "2025-10-01T15:22:00Z",

    // ✅ Campaign Statistics
    "stats": {
      "total_creators": 7,
      "total_posts": 12,
      "total_reach": 5000000,
      "total_views": 125000,
      "total_likes": 8500,
      "total_comments": 450,
      "overall_engagement_rate": 0.1382,
      "static_count": 7,
      "reels_count": 5
    }
  }
}
```

**Frontend Display Mapping:**

| Frontend Field | Backend Field | Display Format |
|---|---|---|
| Total Creators | `stats.total_creators` | Number |
| Total Posts | `stats.total_posts` | Number |
| Total Followers | `stats.total_reach` | `toLocaleString()` |
| Total Reach | `stats.total_reach` | `toLocaleString()` |
| Total Views | `stats.total_views` | `toLocaleString()` |
| Engagement Rate | `stats.overall_engagement_rate` | `(value * 100).toFixed(2)}%` |
| Total Comments | `stats.total_comments` | `toLocaleString()` |
| Total Likes | `stats.total_likes` | `toLocaleString()` |
| Static Posts | `stats.static_count` | Number |
| Reels | `stats.reels_count` | Number |

---

### 3. Campaign Details - Posts Tab

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/posts`

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "posts": [
      {
        // Core Fields
        "id": "e4f1f716-cc16-479c-b1c5-49f3fa28a1a3",
        "thumbnail": "https://cdn.following.ae/posts/DPGYXeDAN9f/thumbnail.webp",
        "display_url": "https://instagram.com/...",
        "url": "https://instagram.com/p/DPGYXeDAN9f",
        "type": "reel",
        "shortcode": "DPGYXeDAN9f",

        // Content
        "caption": "Amazing summer vibes! 🌞 #summer #fashion",

        // Metrics
        "views": 12345,
        "likes": 1000,
        "comments": 50,
        "engagementRate": 0.1382,

        // AI Analysis (may be null for old posts)
        "ai_content_category": "fashion",
        "ai_sentiment": "positive",
        "ai_language_code": "en",

        // Creator Info
        "creator_username": "latifalshamsi",
        "creator_full_name": "Latifa Alshamsi",
        "creator_followers_count": 762157,

        // Metadata
        "added_at": "2025-10-01T11:15:22Z"
      }
    ],

    // ✅ Aggregated Totals
    "total_posts": 7,
    "total_views": 85430,
    "total_likes": 7200,
    "total_comments": 450,
    "total_engagement": 7650
  }
}
```

**Frontend Display Mapping:**

| Frontend Field | Backend Field | Display Format |
|---|---|---|
| Post ID | `id` | UUID |
| Thumbnail | `thumbnail` \|\| `display_url` | `<img src={thumbnail \|\| display_url \|\| '/placeholder.jpg'} />` |
| Post URL | `url` | Link to Instagram |
| Type Badge | `type` | "Static" \| "Reel" badge |
| Caption | `caption` | `caption \|\| "No caption"` (truncate for list view) |
| Views | `views` | `views > 0 ? toLocaleString() : '-'` (only for reels) |
| Likes | `likes` | `toLocaleString()` |
| Comments | `comments` | `toLocaleString()` |
| Engagement | `engagementRate` | `(engagementRate * 100).toFixed(2)}%` |
| AI Category | `ai_content_category` | `ai_content_category \|\| 'Uncategorized'` |
| AI Sentiment | `ai_sentiment` | Icon (😊 positive, 😐 neutral, 😞 negative) |
| Language | `ai_language_code` | `ai_language_code?.toUpperCase()` |
| Creator | `creator_username` | `@{creator_username}` |
| Creator Name | `creator_full_name` | As-is |
| Creator Followers | `creator_followers_count` | `toLocaleString()` followers |
| Date Added | `added_at` | `new Date(added_at).toLocaleDateString()` |

**Post Type Check:**
```typescript
// Only show views for reels
{post.type === 'reel' && post.views > 0 && (
  <div>👁️ {post.views.toLocaleString()} views</div>
)}
```

---

### 4. Campaign Details - Creators Tab

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/creators`

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "creators": [
      {
        "profile_id": "4642aa24-b8b8-45e4-8edf-4dd52a0e2ad1",
        "username": "latifalshamsi",
        "full_name": "Latifa Alshamsi",
        "profile_pic_url": "https://...",
        "followers_count": 762157,
        "posts_count": 7940,
        "engagement_rate": 0.1382,

        // Campaign-Specific Metrics
        "campaign_posts_count": 2,
        "campaign_total_likes": 2000,
        "campaign_total_comments": 150,
        "campaign_total_engagement": 2150,

        // Audience Demographics (⚠️ Currently NULL - see note below)
        "audience_demographics": null
      }
    ],
    "total_creators": 7
  }
}
```

**Frontend Display Mapping:**

| Frontend Field | Backend Field | Display Format |
|---|---|---|
| Profile ID | `profile_id` | UUID |
| Username | `username` | `@{username}` |
| Full Name | `full_name` | As-is |
| Avatar | `profile_pic_url` | `<img src={profile_pic_url \|\| '/avatar-placeholder.png'} />` |
| Followers | `followers_count` | `toLocaleString()` |
| Total Posts | `posts_count` | Number |
| Engagement Rate | `engagement_rate` | `(engagement_rate * 100).toFixed(2)}%` |
| Campaign Posts | `campaign_posts_count` | Number |
| Campaign Likes | `campaign_total_likes` | `toLocaleString()` |
| Campaign Comments | `campaign_total_comments` | `toLocaleString()` |
| Campaign Engagement | `campaign_total_engagement` | `toLocaleString()` |

---

### 5. Campaign Details - Audience Tab

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/audience`

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "total_reach": 5000000,
    "total_creators": 7,

    // ✅ Full Distributions (for charts)
    "gender_distribution": {
      "FEMALE": 65.5,
      "MALE": 34.5
    },
    "age_distribution": {
      "18-24": 25.3,
      "25-34": 45.2,
      "35-44": 20.1,
      "45-54": 9.4
    },
    "country_distribution": {
      "United Arab Emirates": 35.2,
      "Saudi Arabia": 25.8,
      "Kuwait": 15.3,
      "Egypt": 10.5,
      "Bahrain": 8.2
    },
    "city_distribution": {
      "Dubai": 28.5,
      "Abu Dhabi": 15.2,
      "Riyadh": 12.8,
      "Jeddah": 8.5,
      "Kuwait City": 7.2
    },

    // ✅ Top Items (for quick stats display)
    "topGender": {
      "name": "FEMALE",
      "percentage": 65.5
    },
    "topAgeGroup": {
      "name": "25-34",
      "percentage": 45.2
    },
    "topCountry": {
      "name": "United Arab Emirates",
      "percentage": 35.2
    },
    "topCity": {
      "name": "Dubai",
      "percentage": 28.5
    }
  }
}
```

**Frontend Display Mapping:**

**Summary Stats:**
| Frontend Field | Backend Field | Display Format |
|---|---|---|
| Total Reach | `total_reach` | `toLocaleString()` followers |
| Total Creators | `total_creators` | Number |

**Top Demographics (Quick Display):**
```typescript
// Top Gender
<Stat label="Top Gender">
  {audience.topGender?.name} ({audience.topGender?.percentage}%)
</Stat>

// Top Age Group
<Stat label="Top Age Group">
  {audience.topAgeGroup?.name} ({audience.topAgeGroup?.percentage}%)
</Stat>

// Top Country
<Stat label="Top Country">
  {audience.topCountry?.name} ({audience.topCountry?.percentage}%)
</Stat>

// Top City
<Stat label="Top City">
  {audience.topCity?.name} ({audience.topCity?.percentage}%)
</Stat>
```

**Distribution Charts:**
```typescript
// Gender Distribution (Pie Chart)
<PieChart
  data={Object.entries(audience.gender_distribution).map(([key, value]) => ({
    name: key,
    value: value
  }))}
/>

// Age Distribution (Bar Chart)
<BarChart
  data={Object.entries(audience.age_distribution).map(([key, value]) => ({
    ageRange: key,
    percentage: value
  }))}
/>

// Country Distribution (Top 5)
const topCountries = Object.entries(audience.country_distribution)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 5);

// City Distribution (Top 5)
const topCities = Object.entries(audience.city_distribution)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 5);
```

---

## 🔧 Additional Endpoints

### Create Campaign
**Endpoint:** `POST /api/v1/campaigns/`
```json
{
  "name": "Campaign Name",
  "brand_name": "Brand Name",
  "brand_logo_url": "https://..." // optional
}
```

### Update Campaign
**Endpoint:** `PATCH /api/v1/campaigns/{campaign_id}`
```json
{
  "name": "New Name", // optional
  "brand_name": "New Brand", // optional
  "brand_logo_url": "https://...", // optional
  "status": "active" // optional: draft|active|completed
}
```

### Delete Campaign
**Endpoint:** `DELETE /api/v1/campaigns/{campaign_id}`

### Add Post to Campaign
**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/posts`
```json
{
  "instagram_post_url": "https://instagram.com/p/DPGYXeDAN9f"
}
```

### Remove Post from Campaign
**Endpoint:** `DELETE /api/v1/campaigns/{campaign_id}/posts/{post_id}`

### Upload Brand Logo
**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/logo`
- Content-Type: `multipart/form-data`
- Field name: `logo`
- Max size: 5MB
- Formats: PNG, JPG, JPEG, WebP

### Delete Brand Logo
**Endpoint:** `DELETE /api/v1/campaigns/{campaign_id}/logo`

---

## ⚠️ Important Notes

### 1. Audience Demographics - Currently Limited
**Status:** ⚠️ **Audience demographics are currently NULL for all creators**

**Why:** Instagram's Apify API does not provide audience demographics (gender, age, location). This data requires:
- Instagram Business Account access
- Facebook Graph API integration
- OR manual audience analysis tools

**Current Behavior:**
- All `audience_demographics` fields return `null`
- Audience aggregation endpoint returns empty distributions
- `topGender`, `topAgeGroup`, `topCountry`, `topCity` will be `null`

**Frontend Handling:**
```typescript
// Check for null before displaying
{audience.topGender ? (
  <div>Top Gender: {audience.topGender.name} ({audience.topGender.percentage}%)</div>
) : (
  <div>Audience demographics not available</div>
)}

// Empty state for charts
{Object.keys(audience.gender_distribution || {}).length > 0 ? (
  <PieChart data={audience.gender_distribution} />
) : (
  <EmptyState message="Audience data coming soon" />
)}
```

**Future Solutions:**
1. Integrate with Instagram Graph API (requires Business accounts)
2. Add manual audience data entry interface
3. Use AI-based audience estimation from post content/comments

### 2. AI Analysis Data
**Status:** ✅ **Fixed - Now working for NEW posts**

- Old posts (before fix): AI fields are `null`
- New posts (after fix): AI fields populate within 30-60 seconds
- Check for `null` before displaying AI data

```typescript
const category = post.ai_content_category || "Uncategorized";
const sentiment = post.ai_sentiment || "neutral";
```

### 3. CDN Thumbnails
**Status:** ✅ **Working for all new posts**

- Thumbnails process within ~10 seconds after adding post
- Always use fallback: `thumbnail || display_url || '/placeholder.jpg'`

### 4. Engagement Rate Format
**All engagement rates are decimals (0-1), multiply by 100 for percentage:**
```typescript
const percentage = (engagementRate * 100).toFixed(2) + '%';
```

### 5. Views Count
**Views are only available for video/reel posts:**
```typescript
// Only show for reels
{post.type === 'reel' && post.views > 0 && (
  <div>{post.views.toLocaleString()} views</div>
)}
```

---

## 📊 TypeScript Type Definitions

```typescript
// Campaign List Item
interface Campaign {
  id: string;
  name: string;
  brand_name: string;
  brand_logo_url: string | null;
  status: 'draft' | 'active' | 'completed';
  created_at: string;
  updated_at: string;
  creators_count: number;
  posts_count: number;
  total_reach: number;
  engagement_rate: number;
}

// Campaign Summary
interface CampaignSummary {
  totalCampaigns: number;
  totalCreators: number;
  totalReach: number;
  avgEngagementRate: number;
}

// Campaign Details
interface CampaignDetails extends Campaign {
  user_id: string;
  stats: {
    total_creators: number;
    total_posts: number;
    total_reach: number;
    total_views: number;
    total_likes: number;
    total_comments: number;
    overall_engagement_rate: number;
    static_count: number;
    reels_count: number;
  };
}

// Campaign Post
interface CampaignPost {
  id: string;
  thumbnail: string | null;
  display_url: string;
  url: string;
  type: 'static' | 'reel';
  shortcode: string;
  caption: string | null;
  views: number;
  likes: number;
  comments: number;
  engagementRate: number;
  ai_content_category: string | null;
  ai_sentiment: 'positive' | 'neutral' | 'negative' | null;
  ai_language_code: string | null;
  creator_username: string;
  creator_full_name: string;
  creator_followers_count: number;
  added_at: string;
}

// Campaign Creator
interface CampaignCreator {
  profile_id: string;
  username: string;
  full_name: string;
  profile_pic_url: string | null;
  followers_count: number;
  posts_count: number;
  engagement_rate: number;
  campaign_posts_count: number;
  campaign_total_likes: number;
  campaign_total_comments: number;
  campaign_total_engagement: number;
  audience_demographics: null; // Currently always null
}

// Campaign Audience
interface CampaignAudience {
  total_reach: number;
  total_creators: number;
  gender_distribution: Record<string, number>;
  age_distribution: Record<string, number>;
  country_distribution: Record<string, number>;
  city_distribution: Record<string, number>;
  topGender: { name: string; percentage: number } | null;
  topAgeGroup: { name: string; percentage: number } | null;
  topCountry: { name: string; percentage: number } | null;
  topCity: { name: string; percentage: number } | null;
}
```

---

## 🎯 Quick Reference Checklist

**Campaigns List Page:**
- ✅ Campaign ID (first 8 chars)
- ✅ Campaign name
- ✅ Status badge
- ✅ Brand name
- ✅ Brand logo
- ✅ Creators count
- ✅ Posts count
- ✅ Total reach
- ✅ Engagement rate
- ✅ Created date
- ✅ Dashboard summary (4 cards)

**Campaign Details - Stats Tab:**
- ✅ Total creators
- ✅ Total posts
- ✅ Total followers/reach
- ✅ Total views
- ✅ Overall engagement rate
- ✅ Total comments
- ✅ Total likes
- ✅ Post type breakdown

**Campaign Details - Posts Tab:**
- ✅ Post thumbnail
- ✅ Post URL
- ✅ Post type
- ✅ Caption
- ✅ Views (reels only)
- ✅ Likes
- ✅ Comments
- ✅ Engagement rate
- ✅ AI category
- ✅ AI sentiment
- ✅ Language
- ✅ Creator info

**Campaign Details - Creators Tab:**
- ✅ All creator fields
- ✅ Campaign-specific metrics

**Campaign Details - Audience Tab:**
- ⚠️ All fields available but data is NULL (awaiting Instagram Graph API or manual entry)
- ✅ API structure ready
- ✅ Frontend should show empty states

---

**Last Updated:** October 1, 2025
**Backend Status:** ✅ All endpoints functional
**Known Limitations:** Audience demographics require additional data sources
