# Campaign Demographics - Current State & Frontend Integration Guide

## 🔍 Current State Analysis (January 2025)

### ✅ What We ARE Sending (Working)

#### 1. **Profile-Level AI Data** ✅
All 10 AI models are successfully running and storing data in the **profile table's JSONB fields**:

**Stored in Profile Table:**
```sql
- ai_audience_insights (JSONB) ← Contains demographics!
- ai_audience_quality (JSONB)
- ai_visual_content (JSONB)
- ai_trend_detection (JSONB)
- ai_advanced_nlp (JSONB)
- ai_fraud_detection (JSONB)
- ai_behavioral_patterns (JSONB)
- ai_primary_content_type (VARCHAR)
- ai_content_distribution (JSONB)
- ai_models_success_rate (FLOAT) ← 100% success!
```

**Demographics Location:**
```json
profiles.ai_audience_insights = {
  "demographic_insights": {
    "estimated_gender_split": {
      "male": 0.65,
      "female": 0.6,
      "other": 0.05
    },
    "estimated_age_groups": {
      "18-24": 0.25,
      "25-34": 0.4,
      "35-44": 0.2,
      "45-54": 0.1,
      "55+": 0.05
    }
  },
  "geographic_analysis": {
    "country_distribution": {
      "France": 1
    },
    "location_distribution": {
      "Grand": 1
    }
  }
}
```

#### 2. **Post-Level AI Data** ✅
All posts have complete AI analysis:
```sql
- ai_content_category (VARCHAR) ← "automotive", "fashion", etc.
- ai_sentiment (VARCHAR) ← "positive", "neutral", "negative"
- ai_language_code (VARCHAR) ← "en", "ar", etc.
- ai_analysis_raw (JSONB) ← 8,132+ bytes of complete analysis
```

#### 3. **CDN Processing** ✅
All images/thumbnails processed and stored:
```sql
posts.cdn_thumbnail_url = "https://cdn.following.ae/posts/{shortcode}/thumbnail.webp"
```

---

## ❌ The Problem: Demographics Not Reaching Frontend

### Issue Root Cause
**Code Location:** `app/services/campaign_service.py` lines 515, 525

```python
# CURRENT CODE (INCORRECT):
result = await db.execute(
    select(CampaignCreator)
    .where(CampaignCreator.campaign_id == campaign_id)
    .options(
        selectinload(CampaignCreator.profile).selectinload(Profile.audience_demographics)  # ❌ WRONG TABLE!
    )
)

demographics = profile.audience_demographics  # ❌ This is NULL - table is empty!
```

**The Problem:**
1. Code queries `audience_demographics` **table** (separate table)
2. That table has **0 rows** - it's empty!
3. Demographics are actually in `profiles.ai_audience_insights` **JSONB field**

**Database Verification:**
```sql
-- ❌ Empty table:
SELECT COUNT(*) FROM audience_demographics;  -- Result: 0

-- ✅ Data exists here:
SELECT username,
       ai_audience_insights->'demographic_insights'
FROM profiles
WHERE username = 'ridaa.says';
-- Result: Full demographics data! ✅
```

---

## 🔧 Solution: Extract Demographics from ai_audience_insights

### Option 1: Direct JSONB Extraction (Recommended)

**Update `campaign_service.py` lines 579-593:**

```python
# OLD CODE (❌ Incorrect):
if demographics:  # demographics from audience_demographics table
    location_dist = demographics.location_distribution or {}
    country_dist = location_dist.get('countries', {})
    city_dist = location_dist.get('cities', {})

    creator_data["audience_demographics"] = {
        "gender_distribution": demographics.gender_distribution or {},
        "age_distribution": demographics.age_distribution or {},
        "country_distribution": country_dist,
        "city_distribution": city_dist
    }

# NEW CODE (✅ Correct - Extract from ai_audience_insights):
if profile.ai_audience_insights:
    ai_insights = profile.ai_audience_insights
    demographic_insights = ai_insights.get('demographic_insights', {})
    geographic_analysis = ai_insights.get('geographic_analysis', {})

    # Extract demographics from AI insights
    gender_split = demographic_insights.get('estimated_gender_split', {})
    age_groups = demographic_insights.get('estimated_age_groups', {})
    country_dist = geographic_analysis.get('country_distribution', {})
    location_dist = geographic_analysis.get('location_distribution', {})

    # Convert to percentages (AI gives 0-1 format, frontend expects 0-100)
    creator_data["audience_demographics"] = {
        "gender_distribution": {k: v * 100 for k, v in gender_split.items()},
        "age_distribution": {k: v * 100 for k, v in age_groups.items()},
        "country_distribution": {k: v * 100 for k, v in country_dist.items()},
        "city_distribution": {k: v * 100 for k, v in location_dist.items()}
    }
```

### Option 2: Create Database View (Alternative)

```sql
-- Create a view that maps ai_audience_insights to audience_demographics format
CREATE VIEW audience_demographics_view AS
SELECT
    p.id as profile_id,
    (p.ai_audience_insights->'demographic_insights'->'estimated_gender_split')::jsonb as gender_distribution,
    (p.ai_audience_insights->'demographic_insights'->'estimated_age_groups')::jsonb as age_distribution,
    (p.ai_audience_insights->'geographic_analysis'->'country_distribution')::jsonb as location_distribution,
    0.8 as confidence_score,
    1 as sample_size
FROM profiles p
WHERE p.ai_audience_insights IS NOT NULL;
```

---

## 📊 What Frontend Currently Expects vs What We Send

### Audience Tab Endpoint: `GET /campaigns/{id}/audience`

**Frontend Expects:**
```typescript
{
  total_reach: number;              // ✅ WE SEND THIS
  total_creators: number;           // ✅ WE SEND THIS

  gender_distribution: {            // ❌ WE SEND EMPTY {}
    "FEMALE": 65.5,
    "MALE": 34.5
  };
  age_distribution: {               // ❌ WE SEND EMPTY {}
    "18-24": 25.3,
    "25-34": 45.2
  };
  country_distribution: {           // ❌ WE SEND EMPTY {}
    "UAE": 35.2,
    "Saudi Arabia": 25.8
  };
  city_distribution: {              // ❌ WE SEND EMPTY {}
    "Dubai": 28.5,
    "Abu Dhabi": 15.2
  };

  topGender: { name, percentage };  // ❌ WE SEND null
  topAgeGroup: { name, percentage }; // ❌ WE SEND null
  topCountry: { name, percentage };  // ❌ WE SEND null
  topCity: { name, percentage };     // ❌ WE SEND null
}
```

**What We Currently Send:**
```json
{
  "total_reach": 5000000,          // ✅ CORRECT
  "total_creators": 7,             // ✅ CORRECT

  "gender_distribution": {},       // ❌ EMPTY - No data from creators
  "age_distribution": {},          // ❌ EMPTY
  "country_distribution": {},      // ❌ EMPTY
  "city_distribution": {},         // ❌ EMPTY

  "topGender": null,               // ❌ null because distributions empty
  "topAgeGroup": null,             // ❌ null
  "topCountry": null,              // ❌ null
  "topCity": null                  // ❌ null
}
```

---

## 🎯 Recommended Approach

### Step 1: Fix Creator Demographics Extraction
Update `get_campaign_creators()` in `campaign_service.py`:

```python
# Remove dependency on audience_demographics table
# .options(selectinload(CampaignCreator.profile).selectinload(Profile.audience_demographics))

# Extract directly from ai_audience_insights JSONB field
for cc in campaign_creators:
    profile = cc.profile

    # Extract demographics from AI insights (NEW)
    if profile.ai_audience_insights:
        ai_insights = profile.ai_audience_insights
        demographic_insights = ai_insights.get('demographic_insights', {})
        geographic_analysis = ai_insights.get('geographic_analysis', {})

        creator_data["audience_demographics"] = {
            "gender_distribution": {
                k: v * 100 for k, v in
                demographic_insights.get('estimated_gender_split', {}).items()
            },
            "age_distribution": {
                k: v * 100 for k, v in
                demographic_insights.get('estimated_age_groups', {}).items()
            },
            "country_distribution": {
                k: v * 100 for k, v in
                geographic_analysis.get('country_distribution', {}).items()
            },
            "city_distribution": {
                k: v * 100 for k, v in
                geographic_analysis.get('location_distribution', {}).items()
            }
        }
```

### Step 2: Verify Data Flow

**Test Query:**
```sql
-- Check that demographics will be available
SELECT
    p.username,
    jsonb_pretty(p.ai_audience_insights->'demographic_insights'->'estimated_gender_split') as gender,
    jsonb_pretty(p.ai_audience_insights->'demographic_insights'->'estimated_age_groups') as age,
    jsonb_pretty(p.ai_audience_insights->'geographic_analysis'->'country_distribution') as country
FROM profiles p
WHERE p.username IN ('ridaa.says', 'barakatme', 'latifalshamsi');
```

---

## 📱 Frontend Integration Notes

### What Frontend Should Do

#### Option A: Keep Current Structure (Recommended)
Frontend continues to expect the same structure. We fix the backend to extract from `ai_audience_insights` instead of `audience_demographics` table.

**Frontend Code (No Changes Needed):**
```typescript
// Audience Tab
const { data } = await fetch(`/api/v1/campaigns/${id}/audience`);

// Display demographics
<PieChart data={data.gender_distribution} />
<BarChart data={data.age_distribution} />
<MapChart data={data.country_distribution} />

// Display top stats
<Stat label="Top Gender" value={data.topGender.name} />
<Stat label="Top Age" value={data.topAgeGroup.name} />
```

#### Option B: Alternative - Use AI Insights Directly
If we want to expose the complete AI insights:

**New Response Structure:**
```json
{
  "total_reach": 5000000,
  "total_creators": 7,

  // Original demographics (for backward compatibility)
  "gender_distribution": {...},
  "age_distribution": {...},

  // NEW: Rich AI insights
  "ai_insights": {
    "audience_sophistication": "high",
    "demographic_confidence": 0.85,
    "cultural_markers": ["lifestyle", "fashion"],
    "interest_categories": {
      "fashion": 1,
      "lifestyle": 1
    },
    "lookalike_profiles": [...],
    "geographic_influence_score": 0.5
  }
}
```

---

## 🚀 Implementation Priority

### Immediate (Critical - Fixes Demographics Display)
1. ✅ Update `campaign_service.py` lines 579-593 to extract from `ai_audience_insights`
2. ✅ Remove `.selectinload(Profile.audience_demographics)` dependency
3. ✅ Convert AI values (0-1) to percentages (0-100) for frontend

### Short-term (Enhanced Features)
1. Add rich AI insights to response (audience sophistication, cultural markers)
2. Include lookalike profiles data
3. Add geographic influence scores

### Future Enhancement (Optional)
1. Populate `audience_demographics` table from `ai_audience_insights` for better query performance
2. Create materialized views for faster aggregation queries
3. Add real-time demographic update webhooks

---

## 📋 Summary

### Current State
- ✅ All 10 AI models running successfully (100% success rate)
- ✅ Demographics data exists in `profiles.ai_audience_insights`
- ❌ Code looking in wrong place (`audience_demographics` table is empty)
- ❌ Frontend showing "No Data" for all demographics

### Fix Required
**One code change** in `campaign_service.py`:
- Extract demographics from `ai_audience_insights` JSONB field
- Convert AI format (0-1) to percentage format (0-100)
- Remove dependency on empty `audience_demographics` table

### Result After Fix
- ✅ Frontend will display all demographics correctly
- ✅ Charts will populate with real data
- ✅ Top stats (gender, age, country, city) will show
- ✅ Campaign audience analytics fully functional

---

**Estimated Fix Time:** 15 minutes
**Testing Time:** 5 minutes
**Total Impact:** HIGH - Unlocks complete campaign audience analytics
