# Campaign AI Insights - Frontend Integration Guide

## Overview
The Campaign module now provides **comprehensive AI intelligence aggregation** across all posts in a campaign. When you add a post to a campaign, the system automatically triggers FULL Creator Analytics with all 10 AI models, and you can fetch aggregated insights for the entire campaign.

---

## 🎯 What Happens When You Add a Post to a Campaign

### POST `/api/v1/campaigns/{campaign_id}/posts`

**Request:**
```json
{
  "instagram_post_url": "https://www.instagram.com/p/DPRPnq0kYde/"
}
```

**Response (Immediate):**
```json
{
  "success": true,
  "data": {
    "post_id": "6d575f2e-d922-4fb2-888b-baed36339c57",
    "shortcode": "DPRPnq0kYde",
    "creator_username": "feedkiani",
    "creator_profile_id": "82bbfe9d-1475-4200-9c0e-3bfd56b0b208",
    "thumbnail_url": "https://cdn.following.ae/posts/DPRPnq0kYde/thumbnail.webp",
    "likes_count": 382,
    "comments_count": 26,
    "ai_analysis": {
      "category": "food",
      "sentiment": "neutral",
      "language": "en"
    }
  },
  "message": "Post added to campaign successfully"
}
```

### Background Processing (Automatic - No Action Required)

The system automatically:

1. ✅ **Fetches full creator profile** from Instagram (if not already complete)
   - 12 posts
   - Full profile data (followers, biography, etc.)
   - Related profiles

2. ✅ **Processes CDN thumbnails** for all images
   - Profile picture
   - All 12 post thumbnails
   - Optimized WebP format

3. ✅ **Runs ALL 10 AI Models**:
   - Sentiment Analysis
   - Language Detection
   - Category Classification
   - Audience Quality
   - Visual Content Analysis
   - Audience Insights (Geographic + Demographic)
   - Trend Detection
   - Advanced NLP
   - Fraud Detection
   - Behavioral Patterns

4. ✅ **Stores complete results** in database
   - Individual post AI analysis
   - Profile-level aggregations
   - Audience demographics

**Processing Time:** ~60 seconds for new creators, <1 second for existing creators with full analytics

---

## 📊 Fetching Campaign Data

### 1. **Campaign Overview**
GET `/api/v1/campaigns/{campaign_id}`

```json
{
  "success": true,
  "data": {
    "id": "81ea5c8f-c0ee-4ef3-b68e-a0ee29038c95",
    "name": "Nike Launch",
    "brand_name": "Nike",
    "brand_logo_url": "https://cdn.following.ae/brand-logos/.../logo.webp",
    "status": "draft",
    "created_at": "2025-10-02T06:23:54Z",
    "total_posts": 1,
    "total_creators": 1,
    "total_reach": 0  // Note: 0 until full creator analytics completes
  }
}
```

### 2. **Campaign Creators**
GET `/api/v1/campaigns/{campaign_id}/creators`

```json
{
  "success": true,
  "data": {
    "creators": [
      {
        "id": "b0d388a2-a490-40f2-bbc8-7aad235261d4",
        "profile": {
          "id": "82bbfe9d-1475-4200-9c0e-3bfd56b0b208",
          "username": "feedkiani",
          "full_name": "Reza Kiani",
          "followers_count": 50000,  // Updated after background processing
          "posts_count": 245,
          "engagement_rate": 3.5,
          "profile_pic_url_hd": "https://cdn.following.ae/profiles/ig/feedkiani/profile_picture.webp",
          "ai_primary_content_type": "food",
          "ai_avg_sentiment_score": 0.15,
          "ai_content_quality_score": 75
        },
        "added_at": "2025-10-02T07:05:30Z"
      }
    ]
  }
}
```

### 3. **Campaign Posts**
GET `/api/v1/campaigns/{campaign_id}/posts`

```json
{
  "success": true,
  "data": {
    "posts": [
      {
        "id": "fdbbcce9-e798-442d-8075-6e6bb948bd99",
        "post": {
          "id": "6d575f2e-d922-4fb2-888b-baed36339c57",
          "shortcode": "DPRPnq0kYde",
          "caption": "‼️Looking for Ethiopian🇪🇹Restaurant in Dubai🇦🇪?!...",
          "likes_count": 382,
          "comments_count": 26,
          "engagement_rate": 3.2,
          "cdn_thumbnail_url": "https://cdn.following.ae/posts/DPRPnq0kYde/thumbnail.webp",
          "ai_content_category": "food",
          "ai_category_confidence": 0.27,
          "ai_sentiment": "neutral",
          "ai_sentiment_score": 0,
          "ai_language_code": "en",
          "creator_username": "feedkiani"
        },
        "instagram_post_url": "https://www.instagram.com/p/DPRPnq0kYde/",
        "added_at": "2025-10-02T07:05:30Z"
      }
    ]
  }
}
```

### 4. **Campaign Audience Demographics** (Existing)
GET `/api/v1/campaigns/{campaign_id}/audience`

```json
{
  "success": true,
  "data": {
    "total_reach": 50000,
    "total_creators": 1,
    "gender_distribution": {
      "female": 60,
      "male": 35,
      "other": 5
    },
    "age_distribution": {
      "18-24": 25,
      "25-34": 40,
      "35-44": 20,
      "45-54": 10,
      "55+": 5
    },
    "country_distribution": {
      "United Arab Emirates": 45,
      "Saudi Arabia": 25,
      "Egypt": 15,
      "Other": 15
    }
  }
}
```

---

## 🧠 NEW: Campaign AI Insights Endpoint

### GET `/api/v1/campaigns/{campaign_id}/ai-insights`

**The Big One!** This aggregates ALL 10 AI models across all campaign posts.

**Response Structure:**

```json
{
  "success": true,
  "data": {
    "total_posts": 1,
    "ai_analyzed_posts": 1,

    "sentiment_analysis": {
      "available": true,
      "distribution": {
        "positive": 20.0,
        "neutral": 65.0,
        "negative": 15.0
      },
      "average_score": 0.15,
      "dominant_sentiment": "neutral"
    },

    "language_detection": {
      "available": true,
      "total_languages": 2,
      "primary_language": "en",
      "top_languages": [
        {"language": "en", "percentage": 85.0},
        {"language": "ar", "percentage": 15.0}
      ]
    },

    "category_classification": {
      "available": true,
      "total_categories": 3,
      "primary_category": "food",
      "average_confidence": 0.27,
      "top_categories": [
        {"category": "food", "percentage": 80.0},
        {"category": "lifestyle", "percentage": 15.0},
        {"category": "travel", "percentage": 5.0}
      ]
    },

    "audience_quality": {
      "available": true,
      "average_authenticity": 75.0,
      "average_bot_score": 20.0,
      "quality_rating": "high"  // "high" | "medium" | "low"
    },

    "visual_content": {
      "available": true,
      "average_aesthetic_score": 69.22,
      "average_professional_quality": 58.84,
      "total_faces_detected": 5,
      "visual_rating": "good"  // "professional" | "good" | "basic"
    },

    "audience_insights": {
      "available": true,
      "top_countries": [
        {"country": "United Arab Emirates", "posts": 5},
        {"country": "Saudi Arabia", "posts": 3},
        {"country": "Ethiopia", "posts": 2}
      ],
      "age_distribution": {
        "18-24": 25.0,
        "25-34": 40.0,
        "35-44": 20.0,
        "45-54": 10.0,
        "55+": 5.0
      },
      "geographic_diversity": 8
    },

    "trend_detection": {
      "available": true,
      "average_viral_potential": 45.5,
      "viral_rating": "medium",  // "high" | "medium" | "low"
      "trending_posts": 0  // Posts with viral score > 70
    },

    "advanced_nlp": {
      "available": true,
      "average_word_count": 194,
      "average_readability": 36.69,
      "average_hashtags": 15,
      "total_brand_mentions": 10,
      "content_depth": "detailed"  // "detailed" | "moderate" | "brief"
    },

    "fraud_detection": {
      "available": true,
      "average_fraud_score": 5.0,
      "risk_distribution": {
        "low": 8,
        "medium": 2,
        "high": 0
      },
      "overall_trust_level": "high"  // "high" | "medium" | "low"
    },

    "behavioral_patterns": {
      "available": true,
      "average_engagement_consistency": 75.0,
      "average_posting_frequency": 20,
      "consistency_rating": "high"  // "high" | "medium" | "low"
    }
  },
  "message": "Campaign AI insights retrieved successfully"
}
```

---

## 🎨 UI Implementation Recommendations

### Campaign Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│ Campaign: Nike Launch                               │
│ Status: Draft  |  Posts: 1  |  Creators: 1         │
├─────────────────────────────────────────────────────┤
│                                                     │
│ OVERVIEW TAB                                        │
│ - Total Reach: 50,000                              │
│ - Engagement Rate: 3.5%                            │
│ - Primary Category: Food (80%)                     │
│ - Dominant Sentiment: Neutral (65%)                │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│ AI INSIGHTS TAB (NEW!)                             │
│                                                     │
│ Content Quality                                     │
│ ├─ Authenticity: 75% ⭐ High                       │
│ ├─ Visual Quality: 58.84 ⭐ Good                   │
│ └─ Trust Level: 95% ⭐ High                        │
│                                                     │
│ Audience Intelligence                              │
│ ├─ Primary Age: 25-34 (40%)                        │
│ ├─ Top Location: UAE (45%)                         │
│ └─ Geographic Diversity: 8 countries               │
│                                                     │
│ Content Analysis                                   │
│ ├─ Average Words: 194 (Detailed)                   │
│ ├─ Readability: 36.69 (Academic)                   │
│ ├─ Brand Mentions: 10                              │
│ └─ Avg Hashtags: 15                                │
│                                                     │
│ Viral Potential                                    │
│ ├─ Score: 45.5/100 (Medium)                        │
│ └─ Trending Posts: 0                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Chart Components

1. **Sentiment Pie Chart**: `sentiment_analysis.distribution`
2. **Language Bar Chart**: `language_detection.top_languages`
3. **Category Breakdown**: `category_classification.top_categories`
4. **Audience Age Distribution**: `audience_insights.age_distribution`
5. **Geographic Heatmap**: `audience_insights.top_countries`
6. **Quality Metrics Radar**: authenticity, visual quality, trust level, engagement consistency

---

## 🔄 Polling Strategy (Recommended)

Since AI processing happens in the background, implement polling for live updates:

```typescript
// After adding a post
const pollCampaignData = async (campaignId: string) => {
  const interval = setInterval(async () => {
    const creators = await fetch(`/api/v1/campaigns/${campaignId}/creators`);
    const data = await creators.json();

    // Check if creator has full analytics
    const hasFullAnalytics = data.data.creators.every(
      c => c.profile.followers_count > 0 && c.profile.ai_primary_content_type
    );

    if (hasFullAnalytics) {
      clearInterval(interval);
      // Fetch AI insights
      const insights = await fetch(`/api/v1/campaigns/${campaignId}/ai-insights`);
      // Update UI with comprehensive insights
    }
  }, 5000); // Poll every 5 seconds

  // Stop after 3 minutes
  setTimeout(() => clearInterval(interval), 180000);
};
```

---

## ⚠️ Important Notes

### Expected Behavior

1. **Immediate Response**: When you add a post, you get instant basic data (likes, comments, thumbnail)

2. **Background Processing**: Full creator analytics runs automatically (~60s)
   - Stub profiles (0 followers) trigger full Apify fetch
   - Complete profiles serve from database (<1s)

3. **Data Completeness**:
   - `followers_count = 0` → Still processing
   - `followers_count > 0` → Full analytics complete
   - `ai_profile_analyzed_at != null` → AI analysis complete

4. **AI Insights Availability**:
   - Each section has `"available": true/false`
   - If `available: false`, show "Processing..." or hide section
   - Data populates progressively as AI models complete

### Edge Cases

- **No AI Data Yet**: `ai_analyzed_posts: 0` → Show "AI analysis in progress"
- **Partial Data**: Some models may return `available: false` temporarily
- **Multiple Posts**: Insights aggregate across ALL posts in campaign
- **Empty Campaign**: Returns `total_posts: 0` with no insights

---

## 🎯 Summary

**When you add a post to a campaign:**
1. ✅ Post is added immediately with basic data
2. ✅ Creator profile triggers FULL analytics (Apify + CDN + AI 10 models)
3. ✅ Background processing completes in ~60 seconds
4. ✅ All endpoints update with complete data
5. ✅ NEW `/ai-insights` endpoint provides comprehensive intelligence

**Data Flow:**
```
Add Post → Stub Profile → Full Apify Fetch → CDN Processing → AI Analysis (10 models) →
Database Storage → API Endpoints (creators/posts/audience/ai-insights)
```

**Your Tasks:**
1. ✅ Display post thumbnails from CDN URLs
2. ✅ Show AI categories, sentiment, language on post cards
3. ✅ Build AI Insights dashboard with charts/metrics
4. ✅ Implement polling to update UI when processing completes
5. ✅ Handle `available: false` states gracefully

Enjoy building with comprehensive AI intelligence! 🚀
