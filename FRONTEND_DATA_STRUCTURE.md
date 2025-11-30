# Frontend Data Structure - Campaign Post Addition Response

## Endpoint: `POST /api/v1/campaigns/{campaign_id}/posts`

## Complete Response Structure

After implementing **Option A: Wait for FULL CREATOR ANALYTICS completion**, the endpoint now returns complete analytics data with all 5 sections populated.

```typescript
interface CampaignPostResponse {
  // Campaign post data
  campaign_post: {
    id: string;
    post_id: string;
    instagram_post_url: string;
    added_at: string;
    campaign_id: string;
  };

  // Complete Profile Analytics (✅ ALL SECTIONS POPULATED)
  profile_analytics: {

    // 1. OVERVIEW - Basic profile metrics
    overview: {
      username: string;
      full_name: string;
      followers_count: number;
      following_count: number;
      posts_count: number;
      engagement_rate: number;
      ai_primary_content_type: string; // "Fashion", "Travel", "Tech", etc.
      ai_content_quality_score: number; // 0-1 scale
      profile_picture_url: string;
      biography: string;
      verified: boolean;
      business_category?: string;
    };

    // 2. AUDIENCE - Demographics & quality (✅ NOW FULLY POPULATED)
    audience: {
      demographics: {
        age_groups: {
          "13-17": number;
          "18-24": number;
          "25-34": number;
          "35-44": number;
          "45-54": number;
          "55-64": number;
          "65+": number;
        };
        gender_distribution: {
          male: number;
          female: number;
          other: number;
        };
        top_locations: Array<{
          location: string;
          percentage: number;
          country_code: string;
        }>;
      };
      language_distribution: { [languageCode: string]: number }; // {"en": 0.8, "ar": 0.2}
      ai_audience_quality_score: number; // 0-1 scale
      authenticity_indicators: {
        engagement_consistency: number;
        follower_growth_rate: number;
        bot_detection_score: number; // 0-1, higher = more authentic
        suspicious_activity_score: number;
      };
    };

    // 3. ENGAGEMENT - Behavioral patterns & metrics
    engagement: {
      avg_likes_per_post: number;
      avg_comments_per_post: number;
      engagement_rate_percentage: number;
      best_posting_times: Array<{
        hour: number; // 0-23
        day_of_week: string;
        engagement_score: number;
      }>;
      ai_avg_sentiment_score: number; // -1 to 1 (-1=negative, 0=neutral, 1=positive)
      sentiment_distribution: {
        positive: number; // percentage
        negative: number; // percentage
        neutral: number; // percentage
      };
      engagement_trends: {
        weekly_growth: number;
        monthly_growth: number;
        consistency_score: number;
      };
    };

    // 4. CONTENT - AI analysis & visual insights
    content: {
      ai_content_distribution: { [category: string]: number }; // {"Fashion": 0.4, "Travel": 0.3, "Lifestyle": 0.2}
      visual_content_analysis: {
        dominant_colors: Array<string>; // ["#FF5733", "#3498DB"]
        image_quality_score: number; // 0-1
        brand_consistency_score: number; // 0-1
        visual_themes: Array<string>; // ["minimalist", "vibrant", "professional"]
      };
      content_themes: Array<{
        theme: string;
        frequency: number; // 0-1
        relevance_score: number;
      }>;
      trend_analysis: {
        trending_hashtags: Array<string>;
        viral_content_indicators: Array<string>;
        content_performance_score: number;
      };
      posting_patterns: {
        posts_per_week: number;
        posting_consistency: number;
        optimal_posting_frequency: number;
      };
    };

    // 5. POSTS - Individual post data with complete AI analysis
    posts: Array<{
      id: string;
      instagram_post_id: string;
      shortcode: string;
      caption: string;
      likes_count: number;
      comments_count: number;
      created_at: string; // ISO date string
      updated_at: string;

      // CDN & Media (✅ NOW POPULATED)
      cdn_thumbnail_url: string; // Optimized thumbnail via CDN
      media_type: "image" | "video" | "carousel";
      media_urls: Array<string>; // All media URLs in post

      // AI Analysis (✅ ALL FIELDS POPULATED)
      ai_content_category: string; // "Fashion", "Lifestyle", "Tech", etc.
      ai_category_confidence: number; // 0-1
      ai_sentiment: "positive" | "negative" | "neutral";
      ai_sentiment_score: number; // -1 to 1
      ai_sentiment_confidence: number; // 0-1
      ai_language_code: string; // "en", "ar", "es", etc.
      ai_language_confidence: number; // 0-1
      ai_analysis_raw?: object; // Full AI analysis if needed
      ai_analyzed_at: string; // ISO date string

      // Engagement metrics
      engagement_rate: number;
      comments_to_likes_ratio: number;
      performance_score: number; // relative to profile average
    }>;
  };

  // Processing metadata
  processing_info: {
    total_processing_time_seconds: number;
    creator_analytics_completed: boolean;
    completion_stages: {
      apify_complete: boolean;
      cdn_complete: boolean;
      ai_complete: boolean;
    };
    cached_data_used: boolean;
  };
}
```

## Response Time Expectations

### Fast Path (Existing Creator)
- **Duration:** <5 seconds
- **Scenario:** Creator already analyzed within last 24 hours
- **Data:** Complete analytics from cache

### Full Processing (New Creator)
- **Duration:** 2-5 minutes
- **Scenario:** First time analyzing this creator
- **Process:** Apify → Database → CDN → AI (10 models) → Response
- **Data:** Fresh complete analytics

### Timeout Handling
- **Duration:** 5 minutes maximum
- **Scenario:** System overload or external API issues
- **Behavior:** Returns partial data with warning

## Frontend Implementation Guide

### 1. Loading State Management
```typescript
// Show processing status during wait
const [processingStatus, setProcessingStatus] = useState({
  stage: 'starting', // 'apify', 'cdn', 'ai', 'complete'
  elapsed: 0,
  estimated_remaining: 0
});

// Handle long processing times (2-5 minutes)
const [showLongProcessingMessage, setShowLongProcessingMessage] = useState(false);

useEffect(() => {
  const timer = setTimeout(() => {
    setShowLongProcessingMessage(true);
  }, 30000); // Show after 30 seconds

  return () => clearTimeout(timer);
}, []);
```

### 2. Data Validation
```typescript
// Ensure all required sections are populated
function validateAnalyticsData(data: CampaignPostResponse): boolean {
  const analytics = data.profile_analytics;

  return (
    analytics.overview.followers_count > 0 &&
    analytics.audience.demographics.age_groups &&
    analytics.engagement.avg_likes_per_post >= 0 &&
    analytics.content.ai_content_distribution &&
    analytics.posts.length > 0 &&
    analytics.posts.every(post =>
      post.cdn_thumbnail_url &&
      post.ai_content_category &&
      post.ai_analyzed_at
    )
  );
}
```

### 3. Error Handling
```typescript
// Handle processing timeout
if (data.processing_info.total_processing_time_seconds > 300) {
  showWarning("Analysis took longer than expected. Some data may be incomplete.");
}

// Handle retry for failed analytics
if (!data.processing_info.creator_analytics_completed) {
  showRetryOption("Creator analysis failed. Would you like to retry?");
}
```

### 4. UI Display Recommendations

**Overview Section:**
- Display follower count, engagement rate, content quality score
- Show AI-detected primary content type prominently

**Audience Section (Previously Empty - Now Populated):**
- Age group chart/graph
- Gender distribution pie chart
- Top locations map/list
- Language distribution
- Authenticity score badge

**Engagement Section:**
- Sentiment analysis chart (positive/negative/neutral)
- Best posting times heatmap
- Engagement trends graph

**Content Section:**
- Content category distribution pie chart
- Visual themes tags
- Brand consistency indicators

**Posts Section:**
- Grid view with CDN thumbnails
- Individual post AI analysis on hover/click
- Performance indicators per post

## Testing Scenarios

1. **Known Creator Test:** Use @ola.alnomairi (should be fast <5s)
2. **New Creator Test:** Use a random creator (should take 2-5 minutes)
3. **Timeout Test:** Use creator during system peak hours

## Migration Notes

**Before:** Response in ~80 seconds with empty Audience tab
**After:** Response in 2-5 minutes (new) or <5s (cached) with complete data

**Critical:** Update frontend timeout from 2 minutes to 6 minutes minimum to handle full processing.