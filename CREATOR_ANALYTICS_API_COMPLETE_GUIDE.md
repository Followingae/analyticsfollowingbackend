# 🎯 Creator Analytics API - Complete Data Access Guide

**Endpoint**: `GET /api/v1/search/creator/{username}`
**Example Profile**: `a.kkhalid`
**Authentication**: Required (Bearer token)

## 📊 Complete Response Structure

### Top-Level Response Object
```typescript
{
  success: boolean,           // Always true for successful response
  profile: ProfileObject,     // Complete profile data (see below)
  analytics_summary: AnalyticsSummary,  // Summary statistics
  background_processing: ProcessingStatus,  // Processing state info
  message: string,            // Human-readable status message
  data_source: string,        // "database_complete" | "apify_fresh"
  cached: boolean            // Whether data was served from cache
}
```

---

## 🧑 PROFILE OBJECT - Complete Structure

### Basic Profile Information
```typescript
profile: {
  // ═══════════════════════════════════════════════════════════
  // SECTION 1: BASIC PROFILE DATA
  // ═══════════════════════════════════════════════════════════
  id: string,                      // UUID profile ID
  username: string,                // Instagram username
  full_name: string | null,        // Full display name
  biography: string | null,        // Bio text

  // Profile Metrics
  followers_count: number,         // Total followers
  following_count: number,         // Total following
  posts_count: number,             // Total posts

  // Account Status
  is_verified: boolean,            // Verified badge
  is_private: boolean,             // Private account
  is_business_account: boolean,    // Business/Creator account

  // Profile Images
  profile_pic_url: string,         // Standard profile pic URL
  profile_pic_url_hd: string,      // HD profile pic URL
  cdn_avatar_url: string,          // CDN-optimized avatar (use this!)

  // Business Information
  external_url: string | null,             // Website/link in bio
  business_category_name: string | null,   // Business category
  business_email: string | null,           // Contact email
  business_phone_number: string | null,    // Contact phone

  // ═══════════════════════════════════════════════════════════
  // SECTION 2: ANALYTICS DATA
  // ═══════════════════════════════════════════════════════════
  engagement_rate: number | null,          // Overall engagement %
  detected_country: string | null,         // Detected country (AI)
  avg_likes: number,                       // Average likes per post
  avg_comments: number,                    // Average comments per post
  influence_score: number | null,          // Influence score (0-100)
  content_quality_score: number | null,    // Content quality (0-1)
  follower_growth_rate: number | null,     // Growth rate %

  // ═══════════════════════════════════════════════════════════
  // SECTION 3: AI ANALYSIS (COMPLETE 10 MODELS)
  // ═══════════════════════════════════════════════════════════
  ai_analysis: {
    // Core AI Metrics
    primary_content_type: string | null,   // Main content category
    avg_sentiment_score: number | null,    // Average sentiment (-1 to +1)
    content_quality_score: number | null,  // AI quality score (0-1)
    models_success_rate: number,           // AI models success rate %

    // Content Distribution (All Categories)
    content_distribution: {
      [category: string]: number           // Category -> Percentage
      // Example: { "Fashion": 45.5, "Travel": 30.2, "Lifestyle": 24.3 }
    },

    // Language Distribution
    language_distribution: {
      [language_code: string]: number      // Language -> Percentage
      // Example: { "en": 80.5, "ar": 19.5 }
    },

    // Analysis Timestamps
    profile_analyzed_at: string | null,           // ISO timestamp
    comprehensive_analyzed_at: string | null      // ISO timestamp
  },

  // ═══════════════════════════════════════════════════════════
  // SECTION 4: STRUCTURED AI INSIGHTS (10 MODELS DATA)
  // ═══════════════════════════════════════════════════════════

  // Model 1: Sentiment Analysis
  ai_sentiment: {
    overall: string,              // "positive" | "negative" | "neutral"
    score: number,                // -1.0 to +1.0
    confidence: number,           // 0.0 to 1.0
    distribution: {               // Sentiment breakdown
      positive: number,           // % of positive posts
      neutral: number,            // % of neutral posts
      negative: number            // % of negative posts
    }
  },

  // Model 2: Language Detection
  ai_language: {
    primary: string,              // Primary language code (e.g., "en")
    confidence: number,           // 0.0 to 1.0
    distribution: {               // Language breakdown
      [code: string]: number      // Language code -> percentage
    },
    supported_languages: string[] // List of detected languages
  },

  // Model 3: Content Classification
  ai_content_category: {
    primary: string,              // Main content category
    confidence: number,           // 0.0 to 1.0
    top_3_categories: Array<{     // Top 3 categories
      category: string,
      percentage: number,
      confidence: number
    }>,
    top_10_categories: Array<{    // Top 10 categories
      category: string,
      percentage: number,
      confidence: number
    }>,
    distribution: {               // Complete category breakdown
      [category: string]: number
    }
  },

  // Model 4: Audience Quality Analysis
  ai_audience_quality: {
    authenticity_score: number,   // 0.0 to 1.0 (higher = more authentic)
    engagement_quality: string,   // "high" | "medium" | "low"
    bot_likelihood: number,       // 0.0 to 1.0 (higher = more bots)
    follower_authenticity: number,// 0.0 to 1.0
    comment_quality_score: number,// 0.0 to 1.0
    spam_indicators: {
      detected: boolean,
      confidence: number,
      types: string[]             // Types of spam detected
    }
  },

  // Model 5: Visual Content Analysis
  ai_visual_content: {
    image_quality_score: number,  // 0.0 to 1.0
    aesthetic_score: number,      // 0.0 to 1.0
    color_palette: {
      dominant_colors: string[],  // Hex color codes
      color_harmony: number       // 0.0 to 1.0
    },
    composition: {
      balance: number,            // 0.0 to 1.0
      complexity: number,         // 0.0 to 1.0
      focal_points: number        // Count of focal points
    },
    content_types: {              // Visual content breakdown
      photos: number,             // Percentage
      videos: number,             // Percentage
      carousels: number,          // Percentage
      reels: number              // Percentage
    }
  },

  // Model 6: Audience Insights
  ai_audience_insights: {
    target_demographics: {
      age_groups: {
        [range: string]: number   // Age range -> percentage
      },
      gender_split: {
        male: number,
        female: number,
        other: number
    },
      interests: string[],        // Top audience interests
      locations: Array<{          // Top audience locations
        country: string,
        percentage: number
      }>
    },
    engagement_patterns: {
      best_posting_times: string[],  // Best times to post
      peak_engagement_days: string[], // Best days
      avg_response_time: number      // Hours
    }
  },

  // Model 7: Trend Detection
  ai_trend_detection: {
    trending_topics: Array<{
      topic: string,
      trend_score: number,        // 0.0 to 1.0
      momentum: string            // "rising" | "stable" | "declining"
    }>,
    hashtag_performance: Array<{
      hashtag: string,
      usage_count: number,
      engagement_boost: number    // Percentage
    }>,
    viral_potential: number,      // 0.0 to 1.0
    trend_alignment: number       // 0.0 to 1.0 (alignment with current trends)
  },

  // Model 8: Advanced NLP
  ai_advanced_nlp: {
    topics: Array<{               // Topic modeling results
      topic: string,
      relevance: number,          // 0.0 to 1.0
      keywords: string[]
    }>,
    entities: {                   // Named entity recognition
      people: string[],
      brands: string[],
      locations: string[],
      products: string[]
    },
    semantic_themes: string[],    // High-level themes
    writing_style: {
      tone: string,               // "professional" | "casual" | "inspirational"
      complexity: number,         // 0.0 to 1.0
      readability_score: number   // 0.0 to 1.0
    }
  },

  // Model 9: Fraud Detection
  ai_fraud_detection: {
    fraud_score: number,          // 0.0 to 1.0 (higher = more suspicious)
    risk_level: string,           // "low" | "medium" | "high"
    indicators: {
      fake_followers: number,     // Percentage
      engagement_manipulation: number, // 0.0 to 1.0
      content_authenticity: number,    // 0.0 to 1.0
      account_age_risk: number    // 0.0 to 1.0
    },
    warnings: string[],           // List of fraud warnings
    brand_safety_score: number    // 0.0 to 1.0 (higher = safer)
  },

  // Model 10: Behavioral Patterns
  ai_behavioral_patterns: {
    posting_frequency: {
      posts_per_week: number,
      consistency_score: number,  // 0.0 to 1.0
      pattern: string            // "consistent" | "sporadic" | "declining"
    },
    engagement_behavior: {
      response_rate: number,      // Percentage
      avg_response_time: number,  // Hours
      community_interaction: number // 0.0 to 1.0
    },
    content_evolution: {
      style_consistency: number,  // 0.0 to 1.0
      topic_diversity: number,    // 0.0 to 1.0
      innovation_score: number    // 0.0 to 1.0
    },
    collaboration_patterns: {
      brand_mentions: number,     // Count
      user_tags: number,          // Count
      collaboration_frequency: number // Per month
    }
  },

  // ═══════════════════════════════════════════════════════════
  // SECTION 5: POSTS DATA (12+ posts with AI)
  // ═══════════════════════════════════════════════════════════
  posts: Array<{
    // Basic Post Data
    id: string,                   // Instagram post ID
    shortcode: string,            // Instagram shortcode
    caption: string | null,       // Post caption

    // Engagement Metrics
    likes_count: number,
    comments_count: number,
    engagement_rate: number | null,

    // Media URLs
    display_url: string,          // Original Instagram URL
    cdn_thumbnail_url: string | null, // CDN-optimized thumbnail (use this!)

    // Timestamp
    taken_at: string,             // ISO timestamp

    // AI Analysis (Per Post)
    ai_analysis: {
      // Core AI Fields
      content_category: string | null,     // Post category
      category_confidence: number | null,  // 0.0 to 1.0
      sentiment: string | null,            // "positive" | "negative" | "neutral"
      sentiment_score: number | null,      // -1.0 to +1.0
      sentiment_confidence: number | null, // 0.0 to 1.0
      language_code: string | null,        // ISO language code
      language_confidence: number | null,  // 0.0 to 1.0
      analyzed_at: string | null,          // ISO timestamp

      // Advanced AI Analysis
      full_analysis: object,        // Complete category analysis
      visual_analysis: object,      // Visual content analysis
      text_analysis: object,        // NLP analysis
      engagement_prediction: object,// Predicted engagement
      brand_safety: object,         // Fraud detection
      hashtag_analysis: object,     // Hashtag insights
      entity_extraction: object,    // Entities found
      topic_modeling: object,       // Topics identified

      data_size_chars: number      // Size of AI data
    },

    // Raw AI Data (Complete)
    ai_analysis_raw: object | null  // Complete raw AI analysis
  }>,

  // ═══════════════════════════════════════════════════════════
  // SECTION 6: METADATA
  // ═══════════════════════════════════════════════════════════
  last_refreshed: string | null,    // ISO timestamp
  data_quality_score: number | null,// 0.0 to 1.0
  created_at: string,               // ISO timestamp
  updated_at: string                // ISO timestamp
}
```

---

## 📈 ANALYTICS SUMMARY

```typescript
analytics_summary: {
  total_posts_analyzed: number,     // Total posts returned
  posts_with_ai: number,            // Posts with AI analysis
  ai_completion_rate: number,       // AI completion percentage
  avg_engagement_rate: number,      // Average engagement rate
  content_categories_found: number  // Number of unique categories
}
```

---

## ⚙️ BACKGROUND PROCESSING STATUS

```typescript
background_processing: {
  unified_processing: boolean,      // Whether processing is running
  already_complete: boolean,        // Whether processing is complete
  note: string                      // Processing status note
}
```

---

## 🎯 How to Access Data (Examples)

### Example 1: Get Basic Profile Info
```typescript
const response = await fetch('/api/v1/search/creator/a.kkhalid');
const data = await response.json();

// Access basic info
const username = data.profile.username;           // "a.kkhalid"
const followers = data.profile.followers_count;   // 123456
const bio = data.profile.biography;               // "Bio text..."
const avatar = data.profile.cdn_avatar_url;       // CDN URL
```

### Example 2: Get AI Analysis
```typescript
// Get primary content category
const mainCategory = data.profile.ai_analysis.primary_content_type;
// "Fashion"

// Get content distribution
const distribution = data.profile.ai_analysis.content_distribution;
// { "Fashion": 45.5, "Travel": 30.2, "Lifestyle": 24.3 }

// Get sentiment
const sentiment = data.profile.ai_sentiment.overall;
// "positive"

// Get audience quality
const authenticity = data.profile.ai_audience_quality.authenticity_score;
// 0.85
```

### Example 3: Get Posts with AI Analysis
```typescript
// Access posts array
const posts = data.profile.posts;

// Loop through posts
posts.forEach(post => {
  const caption = post.caption;
  const likes = post.likes_count;
  const thumbnail = post.cdn_thumbnail_url;  // Use this for images!

  // AI analysis per post
  const category = post.ai_analysis.content_category;
  const sentiment = post.ai_analysis.sentiment;
  const language = post.ai_analysis.language_code;
});
```

### Example 4: Get Advanced AI Insights
```typescript
// Visual content analysis
const imageQuality = data.profile.ai_visual_content.image_quality_score;
const aestheticScore = data.profile.ai_visual_content.aesthetic_score;

// Fraud detection
const fraudScore = data.profile.ai_fraud_detection.fraud_score;
const brandSafety = data.profile.ai_fraud_detection.brand_safety_score;

// Behavioral patterns
const postsPerWeek = data.profile.ai_behavioral_patterns.posting_frequency.posts_per_week;
const responseRate = data.profile.ai_behavioral_patterns.engagement_behavior.response_rate;

// Trend detection
const trendingTopics = data.profile.ai_trend_detection.trending_topics;
const viralPotential = data.profile.ai_trend_detection.viral_potential;
```

---

## 🚨 Common Issues & Solutions

### Issue 1: "Can't see AI data"
**Solution**: AI data is nested in multiple locations:
- `profile.ai_analysis` - Core AI metrics
- `profile.ai_sentiment` - Sentiment analysis
- `profile.ai_content_category` - Content classification
- `profile.ai_audience_quality` - Audience insights
- `profile.ai_visual_content` - Visual analysis
- `profile.ai_audience_insights` - Audience demographics
- `profile.ai_trend_detection` - Trend insights
- `profile.ai_advanced_nlp` - NLP insights
- `profile.ai_fraud_detection` - Fraud detection
- `profile.ai_behavioral_patterns` - Behavioral insights

### Issue 2: "Posts don't have images"
**Solution**: Use `post.cdn_thumbnail_url` instead of `post.display_url`. The CDN URL is optimized and faster.

### Issue 3: "Some AI fields are null"
**Solution**: Check `profile.ai_analysis.profile_analyzed_at`. If null, AI analysis hasn't completed yet. Also check `analytics_summary.ai_completion_rate`.

### Issue 4: "Can't find specific data"
**Solution**: Use browser DevTools to inspect the complete response:
```javascript
console.log(JSON.stringify(data, null, 2));
```

---

## 📋 Data Completeness Checklist

A profile is considered COMPLETE when:
- ✅ `profile.followers_count > 0`
- ✅ `profile.posts_count > 0`
- ✅ `profile.ai_analysis.profile_analyzed_at !== null`
- ✅ `profile.posts.length >= 12`
- ✅ `analytics_summary.posts_with_ai >= 12`
- ✅ `profile.cdn_avatar_url !== null`
- ✅ At least 12 posts have `cdn_thumbnail_url`

---

## 🎨 UI Display Recommendations

### Overview Section
```typescript
// Display these in the overview card
- profile.username
- profile.full_name
- profile.cdn_avatar_url
- profile.followers_count
- profile.following_count
- profile.posts_count
- profile.engagement_rate
- profile.ai_analysis.primary_content_type
```

### Analytics Section
```typescript
// Display these in analytics cards
- profile.avg_likes
- profile.avg_comments
- profile.influence_score
- profile.content_quality_score
- profile.ai_analysis.content_distribution (as chart)
- profile.ai_sentiment.distribution (as chart)
```

### AI Insights Section
```typescript
// Display these in AI insights cards
- profile.ai_audience_quality.authenticity_score
- profile.ai_fraud_detection.brand_safety_score
- profile.ai_visual_content.aesthetic_score
- profile.ai_behavioral_patterns.posting_frequency
- profile.ai_trend_detection.trending_topics
```

### Posts Grid
```typescript
// Display posts in a grid
posts.map(post => ({
  image: post.cdn_thumbnail_url,
  caption: post.caption,
  likes: post.likes_count,
  comments: post.comments_count,
  category: post.ai_analysis.content_category,
  sentiment: post.ai_analysis.sentiment
}))
```

---

## 🔍 Testing the API

### Using cURL (with auth)
```bash
curl -X GET "http://localhost:8000/api/v1/search/creator/a.kkhalid" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json"
```

### Using JavaScript/TypeScript
```typescript
const response = await fetch('http://localhost:8000/api/v1/search/creator/a.kkhalid', {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN_HERE',
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log(data);
```

---

## 📞 Need Help?

If you're still having trouble accessing specific data:
1. Check the response structure matches this guide
2. Verify authentication is working (no 401 errors)
3. Ensure the profile has completed AI analysis (`ai_analysis.profile_analyzed_at` is not null)
4. Check browser console for any JavaScript errors
5. Use `console.log(JSON.stringify(data, null, 2))` to see the complete response

---

**Last Updated**: January 2025
**API Version**: v1
**Backend**: FastAPI + SQLAlchemy + PostgreSQL + Supabase
