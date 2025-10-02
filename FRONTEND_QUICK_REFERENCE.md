# Quick Reference - AI Data Access

## 🎯 TL;DR: How to Get AI Data

### Visual Content & Audience Insights

**Endpoint**: `GET /api/v1/campaigns/{campaign_id}/posts`

**Access Path**:
```javascript
response.data.posts[0].post.ai_analysis_raw.advanced_models.visual_content
response.data.posts[0].post.ai_analysis_raw.advanced_models.audience_insights
```

---

## ✅ Visual Content - What You Get

```javascript
const visualData = post.ai_analysis_raw.advanced_models.visual_content;

// Quick Access
visualData.face_analysis.faces_detected        // 1
visualData.aesthetic_score                      // 69.22
visualData.professional_quality_score           // 58.84
visualData.image_quality_metrics.average_quality // 81.52
visualData.content_recognition.objects_detected  // [{object, confidence}, ...]
```

### Display Example
```jsx
<Card>
  <h3>Visual Analysis</h3>
  <Metric label="Aesthetic" value={visualData.aesthetic_score} max={100} />
  <Metric label="Professional Quality" value={visualData.professional_quality_score} max={100} />
  <Stat icon="👤" label="Faces" value={visualData.face_analysis.faces_detected} />
</Card>
```

---

## 🌍 Audience Insights - What You Get

```javascript
const audienceData = post.ai_analysis_raw.advanced_models.audience_insights;

// Geographic
audienceData.geographic_analysis.country_distribution  // {"Ethiopia": 1}
audienceData.geographic_analysis.location_distribution // {"Ethiopian Highlands": 1}
audienceData.geographic_analysis.geographic_reach      // "local" | "regional" | "international"

// Demographics
audienceData.demographic_insights.estimated_age_groups // {"18-24": 0.25, "25-34": 0.40, ...}
audienceData.demographic_insights.estimated_gender_split // {"female": 0.90, "male": 0.35, ...}

// Interests
audienceData.audience_interests.interest_distribution  // {"food": 0.889, "fashion": 0.111}

// Lookalikes
audienceData.lookalike_analysis.lookalike_profiles    // [{similarity_score, audience_overlap, ...}, ...]
```

### Display Example
```jsx
<Card>
  <h3>Audience Demographics</h3>

  {/* Age Distribution */}
  <DonutChart data={[
    {label: "18-24", value: 25},
    {label: "25-34", value: 40, highlight: true},
    {label: "35-44", value: 20}
  ]} />

  {/* Gender */}
  <BarChart data={[
    {label: "Female", value: 90},
    {label: "Male", value: 35}
  ]} />

  {/* Top Location */}
  <Stat>
    <Flag>🇪🇹</Flag>
    <Location>Ethiopia</Location>
    <Count>Primary market</Count>
  </Stat>
</Card>
```

---

## 📊 Campaign Aggregation (Recommended)

**Endpoint**: `GET /api/v1/campaigns/{campaign_id}/ai-insights`

**Aggregated across all posts:**

```javascript
const insights = response.data;

// Visual Content (Aggregated)
insights.visual_content.average_aesthetic_score        // 69.22
insights.visual_content.average_professional_quality   // 58.84
insights.visual_content.total_faces_detected           // 5
insights.visual_content.visual_rating                  // "professional" | "good" | "basic"

// Audience Insights (Aggregated)
insights.audience_insights.top_countries               // [{country, posts}, ...]
insights.audience_insights.age_distribution            // {"18-24": 25, "25-34": 40, ...}
insights.audience_insights.geographic_diversity        // 8
```

### Display Example
```jsx
<Dashboard>
  <VisualQualityCard
    aesthetic={insights.visual_content.average_aesthetic_score}
    professional={insights.visual_content.average_professional_quality}
    faces={insights.visual_content.total_faces_detected}
    rating={insights.visual_content.visual_rating}
  />

  <AudienceCard
    countries={insights.audience_insights.top_countries}
    ageDistribution={insights.audience_insights.age_distribution}
    diversity={insights.audience_insights.geographic_diversity}
  />
</Dashboard>
```

---

## 🎨 UI Components You Should Build

### 1. Visual Quality Card
- Radial progress: Aesthetic score
- Radial progress: Professional quality
- Number badge: Faces detected
- Star rating: Visual rating

### 2. Audience Demographics Card
- Donut chart: Age distribution (5 groups)
- Horizontal bars: Gender split
- World map: Geographic distribution
- Number: Geographic diversity score

### 3. Audience Interests Card
- Pie chart: Interest distribution
- Tag cloud: Interest categories
- Brand affinity list
- Sophistication level badge

### 4. Lookalike Profiles Card
- Profile cards: 3 similar creators
- Similarity percentage badges
- Audience overlap meters
- Shared characteristics tags

---

## 🚀 Complete Working Example

```typescript
import { useEffect, useState } from 'react';

interface VisualData {
  aesthetic_score: number;
  professional_quality_score: number;
  face_analysis: { faces_detected: number };
}

interface AudienceData {
  demographic_insights: {
    estimated_age_groups: Record<string, number>;
    estimated_gender_split: Record<string, number>;
  };
  geographic_analysis: {
    country_distribution: Record<string, number>;
    location_distribution: Record<string, number>;
  };
  audience_interests: {
    interest_distribution: Record<string, number>;
  };
}

const CampaignInsights = ({ campaignId }: { campaignId: string }) => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      // Get posts with AI data
      const response = await fetch(`/api/v1/campaigns/${campaignId}/posts`);
      const data = await response.json();
      setPosts(data.data.posts);
      setLoading(false);
    };
    fetchData();
  }, [campaignId]);

  if (loading) return <Spinner />;

  return (
    <div className="campaign-insights">
      {posts.map((item) => {
        const post = item.post;
        const ai = post.ai_analysis_raw?.advanced_models;

        if (!ai) return null;

        const visual: VisualData = ai.visual_content;
        const audience: AudienceData = ai.audience_insights;

        return (
          <div key={post.id} className="post-insights">
            {/* Visual Content */}
            <Card>
              <h3>Visual Quality</h3>
              <Progress
                label="Aesthetic"
                value={visual.aesthetic_score}
                max={100}
              />
              <Progress
                label="Professional"
                value={visual.professional_quality_score}
                max={100}
              />
              <Badge>
                👤 {visual.face_analysis.faces_detected} faces
              </Badge>
            </Card>

            {/* Demographics */}
            <Card>
              <h3>Audience Demographics</h3>
              <DonutChart
                data={Object.entries(audience.demographic_insights.estimated_age_groups).map(
                  ([age, pct]) => ({
                    label: age,
                    value: pct * 100
                  })
                )}
              />
            </Card>

            {/* Geography */}
            <Card>
              <h3>Geographic Reach</h3>
              <LocationList>
                {Object.entries(audience.geographic_analysis.country_distribution).map(
                  ([country, count]) => (
                    <LocationItem key={country}>
                      <span>{country}</span>
                      <span>{count} posts</span>
                    </LocationItem>
                  )
                )}
              </LocationList>
            </Card>

            {/* Interests */}
            <Card>
              <h3>Audience Interests</h3>
              <PieChart
                data={Object.entries(audience.audience_interests.interest_distribution).map(
                  ([interest, pct]) => ({
                    label: interest,
                    value: pct * 100
                  })
                )}
              />
            </Card>
          </div>
        );
      })}
    </div>
  );
};

export default CampaignInsights;
```

---

## 📚 Full Documentation

- **Complete AI Data**: See `FRONTEND_DETAILED_AI_DATA.md`
- **Campaign Integration**: See `FRONTEND_CAMPAIGN_AI_INSIGHTS.md`

---

## ✅ Checklist for Frontend

- [ ] Build Visual Quality card (aesthetic, professional, faces)
- [ ] Build Demographics charts (age donut, gender bars)
- [ ] Build Geographic map/list (countries, diversity)
- [ ] Build Interests visualization (pie chart, tags)
- [ ] Build Lookalike profiles section
- [ ] Implement polling for background processing updates
- [ ] Handle `available: false` states gracefully
- [ ] Add loading states for AI data processing

**All data is already in the database - just fetch and display!** 🚀
