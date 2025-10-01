# Campaign Demographics - Frontend Integration Guide

## 🎯 Overview

The backend now provides **complete audience demographics** for campaigns by extracting AI-generated insights from all creators. This guide explains what data you receive and how to integrate it.

---

## 📡 API Endpoints & Response Structure

### 1. Campaign Audience Endpoint

**Endpoint:** `GET /api/v1/campaigns/{campaign_id}/audience`

**What You Receive:**

```typescript
interface CampaignAudienceResponse {
  success: boolean;
  data: {
    // Summary Statistics
    total_reach: number;              // Total combined followers
    total_creators: number;           // Number of creators in campaign

    // Complete Distributions (for charts/graphs)
    gender_distribution: {
      [gender: string]: number;       // Percentage 0-100
      // Example: { "MALE": 55.2, "FEMALE": 44.8 }
    };

    age_distribution: {
      [ageRange: string]: number;     // Percentage 0-100
      // Example: { "18-24": 25.3, "25-34": 45.2, "35-44": 20.1 }
    };

    country_distribution: {
      [country: string]: number;      // Percentage 0-100
      // Example: { "United Arab Emirates": 35.2, "Saudi Arabia": 25.8 }
    };

    city_distribution: {
      [city: string]: number;         // Percentage 0-100
      // Example: { "Dubai": 28.5, "Abu Dhabi": 15.2, "Riyadh": 12.8 }
    };

    // Top Items (for quick stats/summary cards)
    topGender: {
      name: string;                   // e.g., "FEMALE"
      percentage: number;             // e.g., 65.5
    } | null;

    topAgeGroup: {
      name: string;                   // e.g., "25-34"
      percentage: number;             // e.g., 45.2
    } | null;

    topCountry: {
      name: string;                   // e.g., "United Arab Emirates"
      percentage: number;             // e.g., 35.2
    } | null;

    topCity: {
      name: string;                   // e.g., "Dubai"
      percentage: number;             // e.g., 28.5
    } | null;
  };
}
```

---

## 🎨 Frontend Implementation Examples

### Summary Stats Display

```typescript
import { useQuery } from '@tanstack/react-query';

function CampaignAudienceSummary({ campaignId }: { campaignId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (isLoading) return <LoadingSkeleton />;

  const { total_reach, total_creators, topGender, topAgeGroup, topCountry, topCity } = data.data;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {/* Total Reach */}
      <StatCard
        label="Total Reach"
        value={total_reach.toLocaleString()}
        subtitle="followers"
      />

      {/* Total Creators */}
      <StatCard
        label="Creators"
        value={total_creators}
      />

      {/* Top Gender */}
      <StatCard
        label="Top Gender"
        value={topGender ? topGender.name : 'No data'}
        subtitle={topGender ? `${topGender.percentage.toFixed(1)}%` : ''}
      />

      {/* Top Age Group */}
      <StatCard
        label="Top Age"
        value={topAgeGroup ? topAgeGroup.name : 'No data'}
        subtitle={topAgeGroup ? `${topAgeGroup.percentage.toFixed(1)}%` : ''}
      />

      {/* Top Country */}
      <StatCard
        label="Top Country"
        value={topCountry ? topCountry.name : 'No data'}
        subtitle={topCountry ? `${topCountry.percentage.toFixed(1)}%` : ''}
      />

      {/* Top City */}
      <StatCard
        label="Top City"
        value={topCity ? topCity.name : 'No data'}
        subtitle={topCity ? `${topCity.percentage.toFixed(1)}%` : ''}
      />
    </div>
  );
}
```

---

### Gender Distribution Chart

```typescript
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

function GenderDistributionChart({ campaignId }: { campaignId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (!data?.data?.gender_distribution) {
    return <EmptyState message="No gender data available" />;
  }

  const genderData = Object.entries(data.data.gender_distribution).map(([name, value]) => ({
    name,
    value: Number(value),
    percentage: Number(value).toFixed(1)
  }));

  const COLORS = {
    'MALE': '#3B82F6',
    'FEMALE': '#EC4899',
    'OTHER': '#8B5CF6'
  };

  return (
    <div className="w-full h-[300px]">
      <h3 className="text-lg font-semibold mb-4">Gender Distribution</h3>

      {genderData.length === 0 ? (
        <EmptyState message="No gender data available yet" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={genderData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percentage }) => `${name}: ${percentage}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {genderData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[entry.name] || '#94A3B8'} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

---

### Age Distribution Chart

```typescript
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function AgeDistributionChart({ campaignId }: { campaignId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (!data?.data?.age_distribution) {
    return <EmptyState message="No age data available" />;
  }

  // Convert object to array and sort by age range
  const ageOrder = ['18-24', '25-34', '35-44', '45-54', '55+'];
  const ageData = Object.entries(data.data.age_distribution)
    .map(([name, value]) => ({
      name,
      percentage: Number(value)
    }))
    .sort((a, b) => ageOrder.indexOf(a.name) - ageOrder.indexOf(b.name));

  return (
    <div className="w-full h-[300px]">
      <h3 className="text-lg font-semibold mb-4">Age Distribution</h3>

      {ageData.length === 0 ? (
        <EmptyState message="No age data available yet" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={ageData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis label={{ value: 'Percentage (%)', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
            <Bar dataKey="percentage" fill="#3B82F6" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

---

### Geographic Distribution (Top Countries)

```typescript
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function CountryDistributionChart({ campaignId }: { campaignId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (!data?.data?.country_distribution) {
    return <EmptyState message="No country data available" />;
  }

  // Get top 5 countries by percentage
  const countryData = Object.entries(data.data.country_distribution)
    .map(([name, value]) => ({
      name,
      percentage: Number(value)
    }))
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 5);  // Top 5 countries

  return (
    <div className="w-full h-[300px]">
      <h3 className="text-lg font-semibold mb-4">Top Countries</h3>

      {countryData.length === 0 ? (
        <EmptyState message="No country data available yet" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={countryData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" label={{ value: 'Percentage (%)', position: 'insideBottom', offset: -5 }} />
            <YAxis type="category" dataKey="name" width={150} />
            <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
            <Bar dataKey="percentage" fill="#10B981" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

---

### City Distribution (Top Cities)

```typescript
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function CityDistributionChart({ campaignId }: { campaignId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (!data?.data?.city_distribution) {
    return <EmptyState message="No city data available" />;
  }

  // Get top 5 cities by percentage
  const cityData = Object.entries(data.data.city_distribution)
    .map(([name, value]) => ({
      name,
      percentage: Number(value)
    }))
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 5);  // Top 5 cities

  return (
    <div className="w-full h-[300px]">
      <h3 className="text-lg font-semibold mb-4">Top Cities</h3>

      {cityData.length === 0 ? (
        <EmptyState message="No city data available yet" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={cityData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" label={{ value: 'Percentage (%)', position: 'insideBottom', offset: -5 }} />
            <YAxis type="category" dataKey="name" width={150} />
            <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
            <Bar dataKey="percentage" fill="#F59E0B" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

---

## 🎭 Complete Audience Tab Component

```typescript
function CampaignAudienceTab({ campaignId }: { campaignId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  if (isLoading) {
    return <LoadingState />;
  }

  if (error || !data?.success) {
    return <ErrorState message="Failed to load audience data" />;
  }

  const { total_reach, total_creators } = data.data;
  const hasData = total_creators > 0;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <CampaignAudienceSummary campaignId={campaignId} />

      {!hasData ? (
        <EmptyState
          title="No Audience Data Yet"
          message="Add creators to your campaign to see audience demographics"
        />
      ) : (
        <>
          {/* Charts Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Gender Distribution */}
            <div className="bg-white rounded-lg p-6 shadow">
              <GenderDistributionChart campaignId={campaignId} />
            </div>

            {/* Age Distribution */}
            <div className="bg-white rounded-lg p-6 shadow">
              <AgeDistributionChart campaignId={campaignId} />
            </div>

            {/* Country Distribution */}
            <div className="bg-white rounded-lg p-6 shadow">
              <CountryDistributionChart campaignId={campaignId} />
            </div>

            {/* City Distribution */}
            <div className="bg-white rounded-lg p-6 shadow">
              <CityDistributionChart campaignId={campaignId} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

---

## 🔄 Data Update Flow

### When Demographics Are Available

1. **Immediately After Adding Post**: Demographics available within 30-40 seconds
   - Post Analytics runs (~10s)
   - Background Creator Analytics triggers automatically
   - Unified processor runs ALL 10 AI models (~20s)
   - Demographics stored in database

2. **Frontend Should**:
   - Show loading state during initial processing
   - Poll or refetch after 30-40 seconds
   - Display demographics once available

### Handling Empty/Partial Data

```typescript
function SafeAudienceDisplay({ campaignId }: { campaignId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign', campaignId, 'audience'],
    queryFn: () => fetch(`/api/v1/campaigns/${campaignId}/audience`).then(r => r.json())
  });

  // Check if we have any distribution data
  const hasGenderData = data?.data?.gender_distribution &&
    Object.keys(data.data.gender_distribution).length > 0;

  const hasAgeData = data?.data?.age_distribution &&
    Object.keys(data.data.age_distribution).length > 0;

  const hasCountryData = data?.data?.country_distribution &&
    Object.keys(data.data.country_distribution).length > 0;

  return (
    <div className="space-y-4">
      {/* Show appropriate message based on data availability */}
      {!hasGenderData && !hasAgeData && !hasCountryData && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            🔄 Processing creator analytics... Demographics will appear in 30-40 seconds
          </p>
        </div>
      )}

      {/* Show charts only when data is available */}
      {hasGenderData && <GenderDistributionChart campaignId={campaignId} />}
      {hasAgeData && <AgeDistributionChart campaignId={campaignId} />}
      {hasCountryData && <CountryDistributionChart campaignId={campaignId} />}
    </div>
  );
}
```

---

## 📊 Data Format Details

### Percentages
- All distribution values are **percentages** (0-100 range)
- Example: `{ "MALE": 55.2 }` means 55.2% of the audience is male
- Always use `.toFixed(1)` for display to show one decimal place

### Gender Keys
- Values: `"MALE"`, `"FEMALE"`, `"OTHER"`
- Already uppercase from backend

### Age Range Keys
- Common values: `"18-24"`, `"25-34"`, `"35-44"`, `"45-54"`, `"55+"`
- Sort in this order for charts

### Country/City Names
- Full country names (e.g., "United Arab Emirates", "Saudi Arabia")
- Full city names (e.g., "Dubai", "Abu Dhabi")
- No country codes - use names directly

### Null Handling
- `topGender`, `topAgeGroup`, `topCountry`, `topCity` may be `null` if no data
- Distribution objects may be empty `{}` if no data
- Always check for existence before rendering

---

## 🎯 Best Practices

### 1. Loading States
```typescript
if (isLoading) {
  return <Skeleton className="h-[300px]" />;
}
```

### 2. Empty States
```typescript
if (!data?.data || Object.keys(data.data.gender_distribution).length === 0) {
  return (
    <EmptyState
      title="No Data Yet"
      message="Demographics will appear after processing"
      icon={<ChartIcon />}
    />
  );
}
```

### 3. Error Handling
```typescript
if (error) {
  return (
    <ErrorState
      title="Failed to Load"
      message="Please refresh the page"
      onRetry={() => refetch()}
    />
  );
}
```

### 4. Auto-refresh for New Data
```typescript
useQuery({
  queryKey: ['campaign', campaignId, 'audience'],
  queryFn: fetchAudience,
  refetchInterval: (data) => {
    // If no data yet, poll every 10 seconds
    const hasData = data?.data && Object.keys(data.data.gender_distribution).length > 0;
    return hasData ? false : 10000;
  }
});
```

---

## 🚨 Important Notes

1. **Demographics Are AI-Estimated**
   - Not from Instagram API (Instagram doesn't provide this)
   - Estimated based on content, language, hashtags, engagement patterns
   - Confidence scores typically 70-85%

2. **Weighted Aggregation**
   - Campaign demographics are weighted by creator follower counts
   - Larger creators have proportionally more influence on aggregates

3. **Processing Time**
   - ~30-40 seconds after adding first post to campaign
   - Demographics available after complete AI processing
   - Use loading/polling states during initial processing

4. **Data Availability**
   - Only available for creators added via Post Analytics
   - Old creators (pre-fix) may not have demographics
   - New creators (post-fix) will have complete demographics

---

## 📞 Support

If demographics are not appearing:
1. Wait 30-40 seconds after adding posts
2. Check browser console for API errors
3. Verify campaign has creators with posts
4. Contact backend team if data still missing

---

**Last Updated:** January 2025
**Backend Version:** v2.0 (AI Demographics Integration)
