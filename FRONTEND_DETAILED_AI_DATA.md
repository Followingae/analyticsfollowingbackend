# Detailed AI Data - Frontend Access Guide

## How to Access AI Data

Frontend can access the detailed AI analysis in **3 ways**:

### Method 1: Individual Post Data (Most Detailed)
**GET** `/api/v1/campaigns/{campaign_id}/posts`

Each post includes `ai_analysis_raw` field with complete AI data from all 10 models.

### Method 2: Campaign Aggregation (Summarized)
**GET** `/api/v1/campaigns/{campaign_id}/ai-insights`

Aggregated AI insights across all campaign posts (recommended for dashboard).

### Method 3: Direct Post Endpoint
**POST** `/api/v1/campaigns/{campaign_id}/posts` (when adding a post)

Returns immediate post data with AI analysis.

---

## 📊 Visual Content AI - Complete Data Structure

### What Frontend Receives

```json
{
  "post": {
    "shortcode": "DPRPnq0kYde",
    "ai_analysis_raw": {
      "advanced_models": {
        "visual_content": {

          // ===== FACE DETECTION =====
          "face_analysis": {
            "faces_detected": 1,              // Total faces found
            "unique_faces": 0,                // Unique individuals
            "emotions": [],                   // Detected emotions (happy, sad, etc.)
            "celebrities": [],                // Any celebrity faces detected
            "face_quality_scores": []         // Quality scores per face
          },

          // ===== AESTHETIC QUALITY =====
          "aesthetic_score": 69.22,          // Overall visual appeal (0-100)
          "professional_quality_score": 58.84, // Professional photography quality

          // ===== IMAGE QUALITY METRICS =====
          "image_quality_metrics": {
            "average_quality": 81.52,        // Technical image quality
            "quality_consistency": 1,        // Consistency across images
            "average_resolution": [0, 0],    // Image dimensions
            "contrast_scores": [],           // Contrast analysis
            "sharpness_scores": [],          // Sharpness measurements
            "brightness_distribution": []    // Brightness levels
          },

          // ===== VISUAL ANALYSIS =====
          "visual_analysis": {
            "total_posts": 1,
            "images_processed": 1,
            "processing_success_rate": 1,    // 100% success
            "analysis_method": "computer_vision"
          },

          // ===== CONTENT RECOGNITION =====
          "content_recognition": {
            "objects_detected": [
              {
                "object": "class_923",       // Object type detected
                "confidence": 0.178          // Detection confidence
              },
              {
                "object": "class_926",
                "confidence": 0.172
              }
            ],
            "scenes_identified": [],         // Scene types (indoor, outdoor, etc.)
            "content_categories": {}         // Visual content categories
          },

          // ===== COLOR ANALYSIS =====
          "dominant_colors": [],             // Main colors in image
          "brand_logo_detected": []          // Any brand logos found
        }
      }
    }
  }
}
```

### UI Display Recommendations for Visual Content

```typescript
// Example: Display visual quality metrics
interface VisualQuality {
  aestheticScore: number;      // 69.22
  professionalScore: number;   // 58.84
  facesDetected: number;       // 1
  imageQuality: number;        // 81.52
}

// Visual Quality Card Component
const VisualQualityCard = ({ data }) => (
  <Card>
    <h3>Visual Content Analysis</h3>

    {/* Aesthetic Score */}
    <MetricBar
      label="Aesthetic Appeal"
      value={data.aesthetic_score}
      max={100}
      color="purple"
    />

    {/* Professional Quality */}
    <MetricBar
      label="Professional Quality"
      value={data.professional_quality_score}
      max={100}
      color="blue"
      rating={data.professional_quality_score > 70 ? "Professional" : "Good"}
    />

    {/* Face Detection */}
    <Stat>
      <Icon>👤</Icon>
      <Label>Faces Detected</Label>
      <Value>{data.face_analysis.faces_detected}</Value>
    </Stat>

    {/* Image Quality */}
    <MetricBar
      label="Technical Quality"
      value={data.image_quality_metrics.average_quality}
      max={100}
      color="green"
    />
  </Card>
);
```

---

## 🌍 Audience Insights AI - Complete Data Structure

### What Frontend Receives

```json
{
  "post": {
    "shortcode": "DPRPnq0kYde",
    "ai_analysis_raw": {
      "advanced_models": {
        "audience_insights": {

          // ===== GEOGRAPHIC ANALYSIS =====
          "geographic_analysis": {
            "country_distribution": {
              "ኢትዮጵያ إثيوبيا": 1         // Ethiopia (multilingual display)
            },
            "location_distribution": {
              "Ethiopian Highlands": 1     // Specific regions
            },
            "primary_regions": ["Other"],
            "geographic_reach": "local",   // local | regional | international
            "geographic_diversity_score": 0.1,  // 0-1 scale
            "geographic_influence_score": 0.5,  // 0-1 scale
            "international_reach": false,
            "timezone_analysis": {},
            "engagement_heatmap": [],
            "location_performance": {
              "ኢትዮጵያ إثيوبيا": {
                "post_count": 1,
                "avg_engagement": 0.02
              }
            }
          },

          // ===== DEMOGRAPHIC INSIGHTS =====
          "demographic_insights": {
            // AGE DISTRIBUTION
            "estimated_age_groups": {
              "18-24": 0.25,               // 25% of audience
              "25-34": 0.40,               // 40% (PRIMARY)
              "35-44": 0.20,               // 20%
              "45-54": 0.10,               // 10%
              "55+": 0.05                  // 5%
            },

            // GENDER DISTRIBUTION
            "estimated_gender_split": {
              "female": 0.90,              // 90% (heavily female)
              "male": 0.35,                // 35%
              "other": 0.05                // 5%
            },

            // INTEREST CATEGORIES
            "interest_categories": {
              "food": 2,                   // Primary interest
              "fashion": 1,
              "travel": 0,
              "tech": 0,
              "fitness": 0,
              "lifestyle": 0
            },

            "demographic_confidence": 0.34,  // Confidence level
            "audience_sophistication": "high" // high | medium | low
          },

          // ===== AUDIENCE INTERESTS =====
          "audience_interests": {
            "interest_distribution": {
              "food": 0.889,               // 88.9% food interest
              "fashion": 0.111             // 11.1% fashion
            },
            "content_preferences": {
              "fashion": 1
            },
            "brand_affinities": {
              "@hodikiani": 1              // Brand/account mentions
            },
            "niche_interests": [],
            "trend_awareness": 1           // 0-1 scale
          },

          // ===== CULTURAL ANALYSIS =====
          "cultural_analysis": {
            "social_context": "general",
            "language_indicators": {
              "french": 3,
              "spanish": 1
            },
            "cultural_markers": [],
            "cultural_events": [],
            "lifestyle_patterns": {}
          },

          // ===== LOOKALIKE ANALYSIS =====
          "lookalike_analysis": {
            "profile_archetype": "influencer",
            "audience_cluster": "fashion_lifestyle",
            "similarity_score": 0.85,
            "similar_characteristics": [
              "fashion_content",
              "ኢትዮጵያ إثيوبيا_audience",
              "high_engagement"
            ],
            "lookalike_profiles": [
              {
                "profile_id": "lookalike_1",
                "similarity_score": 0.85,
                "audience_overlap_estimate": 0.6,  // 60% overlap
                "geographic_overlap": true,
                "shared_characteristics": ["fashion", "similar_audience"],
                "content_similarity": {
                  "themes": ["fashion"],
                  "style_match": "high"
                }
              },
              {
                "profile_id": "lookalike_2",
                "similarity_score": 0.8,
                "audience_overlap_estimate": 0.5
              },
              {
                "profile_id": "lookalike_3",
                "similarity_score": 0.75,
                "audience_overlap_estimate": 0.4
              }
            ]
          },

          // ===== AUDIENCE SEGMENTATION =====
          "audience_segmentation": {
            "segments": {
              "primary_segment": "food_focused",
              "content_segment": "fashion_specialist",
              "engagement_segment": "high_engagement",
              "geographic_segment": "ኢትዮጵያ_إثيوبيا_focused",
              "temporal_segment": "irregular_posting"
            },
            "segmentation_summary": "food_focused_high_engagement_fashion_specialist",
            "segment_confidence": 0.545,
            "feature_vector": [1, 0.5, 0.3, 0, 1, 0, 0, 0, 0, 642, 0.275]
          },

          // ===== ENGAGEMENT GEOGRAPHY =====
          "engagement_geography": {
            "geographic_reach": "local",
            "engagement_heatmap": [],
            "timezone_engagement": {},
            "location_performance": {
              "ኢትዮጵያ إثيوبيا": {
                "post_count": 1,
                "avg_engagement": 0.02
              }
            }
          }
        }
      }
    }
  }
}
```

### UI Display Recommendations for Audience Insights

```typescript
// Example: Audience Demographics Dashboard
const AudienceDemographicsCard = ({ data }) => {
  const audience = data.ai_analysis_raw.advanced_models.audience_insights;

  return (
    <div className="audience-dashboard">

      {/* AGE DISTRIBUTION */}
      <Section title="Age Distribution">
        <DonutChart
          data={[
            { label: "18-24", value: 25, color: "#FF6B6B" },
            { label: "25-34", value: 40, color: "#4ECDC4", primary: true },
            { label: "35-44", value: 20, color: "#45B7D1" },
            { label: "45-54", value: 10, color: "#96CEB4" },
            { label: "55+", value: 5, color: "#DDA15E" }
          ]}
        />
        <Highlight>Primary: 25-34 years (40%)</Highlight>
      </Section>

      {/* GENDER DISTRIBUTION */}
      <Section title="Gender Split">
        <BarChart horizontal
          data={[
            { label: "Female", value: 90 },
            { label: "Male", value: 35 },
            { label: "Other", value: 5 }
          ]}
        />
      </Section>

      {/* GEOGRAPHIC REACH */}
      <Section title="Geographic Insights">
        <WorldMap
          markers={audience.geographic_analysis.country_distribution}
        />
        <StatGrid>
          <Stat>
            <Label>Geographic Reach</Label>
            <Value>{audience.geographic_analysis.geographic_reach}</Value>
          </Stat>
          <Stat>
            <Label>Diversity Score</Label>
            <Value>{(audience.geographic_analysis.geographic_diversity_score * 100).toFixed(0)}%</Value>
          </Stat>
          <Stat>
            <Label>International</Label>
            <Value>{audience.geographic_analysis.international_reach ? "Yes" : "No"}</Value>
          </Stat>
        </StatGrid>

        <LocationList>
          {Object.entries(audience.geographic_analysis.location_distribution).map(([loc, count]) => (
            <LocationItem>
              <Flag location={loc} />
              <LocationName>{loc}</LocationName>
              <Count>{count} posts</Count>
            </LocationItem>
          ))}
        </LocationList>
      </Section>

      {/* INTEREST CATEGORIES */}
      <Section title="Audience Interests">
        <PieChart
          data={[
            { label: "Food", value: 88.9, color: "#FF6B6B" },
            { label: "Fashion", value: 11.1, color: "#4ECDC4" }
          ]}
        />
        <InterestTags>
          {Object.entries(audience.demographic_insights.interest_categories)
            .filter(([_, count]) => count > 0)
            .map(([interest, count]) => (
              <Tag size={count}>{interest}</Tag>
            ))
          }
        </InterestTags>
      </Section>

      {/* LOOKALIKE PROFILES */}
      <Section title="Similar Creators">
        <LookalikeList>
          {audience.lookalike_analysis.lookalike_profiles.map((profile) => (
            <LookalikeCard>
              <SimilarityScore>{(profile.similarity_score * 100).toFixed(0)}%</SimilarityScore>
              <AudienceOverlap>
                {(profile.audience_overlap_estimate * 100).toFixed(0)}% audience overlap
              </AudienceOverlap>
              <Characteristics>
                {profile.shared_characteristics.join(", ")}
              </Characteristics>
            </LookalikeCard>
          ))}
        </LookalikeList>
      </Section>

      {/* AUDIENCE SEGMENTATION */}
      <Section title="Audience Profile">
        <SegmentBadges>
          <Badge primary>{audience.audience_segmentation.segments.primary_segment}</Badge>
          <Badge>{audience.audience_segmentation.segments.engagement_segment}</Badge>
          <Badge>{audience.audience_segmentation.segments.content_segment}</Badge>
        </SegmentBadges>
        <Summary>{audience.audience_segmentation.segmentation_summary}</Summary>
        <Confidence>
          Confidence: {(audience.audience_segmentation.segment_confidence * 100).toFixed(0)}%
        </Confidence>
      </Section>

      {/* CULTURAL INSIGHTS */}
      <Section title="Cultural Context">
        <Grid>
          <Stat>
            <Label>Social Context</Label>
            <Value>{audience.cultural_analysis.social_context}</Value>
          </Stat>
          <Stat>
            <Label>Audience Sophistication</Label>
            <Value>{audience.demographic_insights.audience_sophistication}</Value>
          </Stat>
          <Stat>
            <Label>Profile Archetype</Label>
            <Value>{audience.lookalike_analysis.profile_archetype}</Value>
          </Stat>
        </Grid>

        {/* Language Indicators */}
        {Object.keys(audience.cultural_analysis.language_indicators).length > 0 && (
          <LanguageIndicators>
            <Label>Language Signals:</Label>
            {Object.entries(audience.cultural_analysis.language_indicators).map(([lang, count]) => (
              <LanguageTag>
                {lang} ({count})
              </LanguageTag>
            ))}
          </LanguageIndicators>
        )}
      </Section>
    </div>
  );
};
```

---

## 🎯 How to Access This Data

### Option 1: Get Individual Post Data

```typescript
// Fetch all campaign posts with complete AI data
const response = await fetch(`/api/v1/campaigns/${campaignId}/posts`);
const data = await response.json();

// Access visual content for first post
const visualContent = data.data.posts[0].post.ai_analysis_raw.advanced_models.visual_content;
const audienceInsights = data.data.posts[0].post.ai_analysis_raw.advanced_models.audience_insights;

console.log("Faces detected:", visualContent.face_analysis.faces_detected);
console.log("Aesthetic score:", visualContent.aesthetic_score);
console.log("Primary age group:", audienceInsights.demographic_insights.estimated_age_groups);
console.log("Top countries:", audienceInsights.geographic_analysis.country_distribution);
```

### Option 2: Get Aggregated Campaign Insights

```typescript
// Fetch aggregated AI insights
const response = await fetch(`/api/v1/campaigns/${campaignId}/ai-insights`);
const data = await response.json();

// Access aggregated metrics
console.log("Average aesthetic:", data.data.visual_content.average_aesthetic_score);
console.log("Top countries:", data.data.audience_insights.top_countries);
console.log("Age distribution:", data.data.audience_insights.age_distribution);
```

---

## 📊 Complete Data Summary

### Visual Content Gives You:
- ✅ Face detection count
- ✅ Aesthetic score (0-100)
- ✅ Professional quality score (0-100)
- ✅ Image quality metrics
- ✅ Object/scene recognition
- ✅ Color analysis
- ✅ Brand logo detection

### Audience Insights Gives You:
- ✅ **Geographic**: Countries, regions, diversity scores
- ✅ **Demographic**: Age distribution (5 groups), gender split
- ✅ **Interests**: Content preferences, brand affinities
- ✅ **Cultural**: Language indicators, social context
- ✅ **Lookalikes**: 3 similar profiles with overlap estimates
- ✅ **Segmentation**: Audience clusters and archetypes
- ✅ **Engagement**: Location performance, heatmaps

---

## 🎨 Recommended UI Components

1. **Visual Quality Dashboard**:
   - Radial progress bars for aesthetic/professional scores
   - Face detection counter
   - Image quality metrics grid

2. **Geographic Heatmap**:
   - World map with country highlights
   - Top locations list
   - Diversity score indicator

3. **Demographics Charts**:
   - Donut chart for age distribution
   - Horizontal bar for gender split
   - Pie chart for interests

4. **Lookalike Profiles**:
   - Card grid showing similar creators
   - Similarity percentage badges
   - Audience overlap indicators

5. **Audience Segments**:
   - Tag cloud for characteristics
   - Confidence meter
   - Profile archetype badge

All data is **already stored in the database** and available via the endpoints! 🚀
