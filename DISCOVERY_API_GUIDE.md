# 🔍 User Discovery API Guide

## Overview

The User Discovery API provides comprehensive profile discovery functionality for the frontend, allowing users to browse, search, filter, and unlock Instagram profiles with credit-based 30-day access.

**Key Features:**
- Browse ALL profiles in database (not just unlocked ones)
- Advanced search and filtering capabilities
- Credit-based profile unlocking (25 credits = 30 days access)
- User dashboard with discovery statistics
- Comprehensive profile management

**Base URL:** `/api/v1/discovery`

---

## 🎯 Main Discovery Endpoints

### 1. Browse All Profiles
**`GET /api/v1/discovery/browse`**

Main discovery endpoint for browsing all profiles with pagination and filtering.

**Query Parameters:**
```typescript
interface BrowseParams {
  page?: number;              // Page number (default: 1)
  page_size?: number;         // Results per page (max: 100, default: 20)
  search?: string;            // Search in username, name, biography
  category?: string;          // Filter by AI content category
  min_followers?: number;     // Minimum followers count
  max_followers?: number;     // Maximum followers count
  sort_by?: string;          // Sort order (followers_desc, followers_asc, recent, alphabetical)
  include_unlocked_status?: boolean; // Include user's unlock status (default: true)
}
```

**Response:**
```typescript
interface BrowseResponse {
  success: boolean;
  profiles: DiscoveryProfile[];
  pagination: {
    page: number;
    page_size: number;
    total_profiles: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
  filters_applied: {
    search_query?: string;
    category_filter?: string;
    min_followers?: number;
    max_followers?: number;
    sort_by: string;
  };
  unlocked_count: number; // How many user has unlocked on this page
}

interface DiscoveryProfile {
  id: string;
  username: string;
  full_name?: string;
  biography?: string;
  profile_pic_url?: string;
  followers_count: number;
  following_count: number;
  posts_count: number;
  is_verified: boolean;
  is_private: boolean;
  ai_analysis: {
    primary_content_type?: string;     // Fashion, Tech, Travel, etc.
    avg_sentiment_score?: number;     // -1.0 to 1.0
    content_quality_score?: number;   // 0.0 to 1.0
  };
  unlock_status: {
    is_unlocked: boolean;
    granted_at?: string;               // ISO datetime
    expires_at?: string;               // ISO datetime
    days_remaining?: number;           // Days until expiry
  };
  created_at?: string;
}
```

**Usage Example:**
```javascript
// Browse profiles with search and filtering
const response = await fetch('/api/v1/discovery/browse?' + new URLSearchParams({
  page: '1',
  page_size: '20',
  search: 'fashion',
  category: 'Fashion',
  min_followers: '10000',
  sort_by: 'followers_desc'
}), {
  headers: { 'Authorization': `Bearer ${token}` }
});

const data = await response.json();
// data.profiles contains array of DiscoveryProfile objects
```

### 2. Unlock Profile for Access
**`POST /api/v1/discovery/unlock-profile`**

Unlock a profile for 30-day access using credits.

**Request Body:**
```typescript
interface UnlockRequest {
  profile_id: string;        // UUID of profile to unlock
  credits_to_spend?: number; // Credits to spend (default: 25)
}
```

**Response:**
```typescript
interface UnlockResponse {
  success: boolean;
  unlocked?: boolean;        // True if newly unlocked
  already_unlocked?: boolean; // True if already had access
  credits_spent: number;
  credits_remaining: number;
  message: string;
  access_info: {
    granted_at: string;      // ISO datetime
    expires_at: string;      // ISO datetime
    days_remaining: number;
  };
  profile: {
    id: string;
    username: string;
    full_name?: string;
    followers_count: number;
    posts_count: number;
    is_verified: boolean;
    ai_primary_content_type?: string;
  };
  transaction_id?: string;

  // Error cases
  error?: string;            // 'insufficient_credits', 'profile_not_found'
  credits_available?: number;
  credits_required?: number;
}
```

**Usage Example:**
```javascript
// Unlock a profile
const response = await fetch('/api/v1/discovery/unlock-profile', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    profile_id: 'profile-uuid-here',
    credits_to_spend: 25
  })
});

const result = await response.json();
if (result.success) {
  if (result.already_unlocked) {
    console.log(`Already unlocked! ${result.access_info.days_remaining} days remaining`);
  } else {
    console.log(`Successfully unlocked @${result.profile.username}!`);
  }
} else {
  console.error(`Unlock failed: ${result.message}`);
}
```

### 3. Get User's Unlocked Profiles
**`GET /api/v1/discovery/unlocked-profiles`**

Get paginated list of all profiles the user has unlocked.

**Query Parameters:**
```typescript
interface UnlockedProfilesParams {
  page?: number;              // Page number (default: 1)
  page_size?: number;         // Results per page (default: 20)
  include_expired?: boolean;  // Include expired access (default: false)
}
```

**Response:**
```typescript
interface UnlockedProfilesResponse {
  success: boolean;
  profiles: UnlockedProfile[];
  pagination: {
    page: number;
    page_size: number;
    total_unlocked: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
  summary: {
    active_unlocks: number;    // Currently active unlocks
    expired_unlocks: number;   // Expired unlocks (if included)
    total_unlocks: number;
  };
}

interface UnlockedProfile {
  profile: DiscoveryProfile;   // Full profile data
  access_info: {
    granted_at?: string;       // When access was granted
    expires_at?: string;       // When access expires
    is_active: boolean;        // Whether access is still valid
    days_remaining: number;    // Days until expiry
    hours_remaining: number;   // Hours until expiry
  };
}
```

**Usage Example:**
```javascript
// Get user's unlocked profiles
const response = await fetch('/api/v1/discovery/unlocked-profiles?page=1&page_size=20', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const data = await response.json();
// Show "My Creators" page with access info
data.profiles.forEach(item => {
  if (item.access_info.is_active) {
    console.log(`@${item.profile.username} - ${item.access_info.days_remaining} days left`);
  }
});
```

### 4. Discovery Dashboard
**`GET /api/v1/discovery/dashboard`**

Get comprehensive discovery statistics for user dashboard.

**Response:**
```typescript
interface DiscoveryDashboard {
  success: boolean;
  discovery_overview: {
    total_profiles_available: number;  // Total profiles in discovery
    user_unlocked_profiles: number;    // User's active unlocks
    user_expired_profiles: number;     // User's expired unlocks
    discovery_percentage: number;      // % of database explored
  };
  content_categories: Array<{
    category: string;                  // Content category name
    count: number;                     // Number of profiles
  }>;
  user_credits: {
    current_balance: number;           // Available credits
    total_earned: number;              // All-time credits earned
    total_spent: number;               // All-time credits spent
    unlock_cost: number;               // Cost per unlock (25)
    possible_unlocks: number;          // How many more unlocks possible
  };
  discovery_tips: string[];            // Helpful tips for users
}
```

**Usage Example:**
```javascript
// Get dashboard data
const response = await fetch('/api/v1/discovery/dashboard', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const dashboard = await response.json();

// Display dashboard metrics
console.log(`You've discovered ${dashboard.discovery_overview.discovery_percentage}% of available creators`);
console.log(`${dashboard.user_credits.current_balance} credits = ${dashboard.user_credits.possible_unlocks} more unlocks`);
```

---

## 🔍 Advanced Discovery Features

### 5. Advanced Search
**`POST /api/v1/discovery/search-advanced`**

Advanced search with multiple criteria and complex filtering.

**Request Body:**
```typescript
interface AdvancedSearchRequest {
  query?: string;                    // Search query
  categories?: string[];             // Multiple categories
  follower_range?: {
    min?: number;
    max?: number;
  };
  sentiment_filter?: string;         // positive, neutral, negative
  verified_only?: boolean;           // Only verified profiles
  private_filter?: string;           // all, public, private
  sort_by?: string;                 // Sort order
  page?: number;
  page_size?: number;
}
```

**Response:** Same as browse endpoint with filtered results.

### 6. Available Categories
**`GET /api/v1/discovery/categories`**

Get all available content categories for filter dropdowns.

**Response:**
```typescript
interface CategoriesResponse {
  success: boolean;
  categories: Array<{
    name: string;                    // Category name
    count: number;                   // Number of profiles
    description: string;             // Category description
  }>;
  total_categories: number;
  message: string;
}
```

### 7. Discovery Pricing
**`GET /api/v1/discovery/pricing`**

Get current pricing information for discovery actions.

**Response:**
```typescript
interface PricingResponse {
  success: boolean;
  pricing: {
    profile_unlock: {
      cost: number;                  // 25 credits
      currency: string;              // "credits"
      duration: string;              // "30 days"
      description: string;
    };
    bulk_discounts: {
      [key: string]: {
        cost_per_profile: number;
        total_cost: number;
        savings?: string;
      };
    };
  };
  credit_packages: Array<{
    amount: number;
    price_usd: number;
    bonus: number;
  }>;
  message: string;
}
```

---

## 🎨 Frontend Integration Examples

### React Hook for Discovery
```typescript
import { useState, useEffect } from 'react';

interface UseDiscoveryOptions {
  page?: number;
  pageSize?: number;
  search?: string;
  category?: string;
  autoLoad?: boolean;
}

export function useDiscovery(options: UseDiscoveryOptions = {}) {
  const [profiles, setProfiles] = useState<DiscoveryProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState(null);
  const [error, setError] = useState(null);

  const loadProfiles = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(options.page || 1),
        page_size: String(options.pageSize || 20),
        ...(options.search && { search: options.search }),
        ...(options.category && { category: options.category })
      });

      const response = await fetch(`/api/v1/discovery/browse?${params}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });

      const data = await response.json();

      if (data.success) {
        setProfiles(data.profiles);
        setPagination(data.pagination);
        setError(null);
      } else {
        setError(data.message || 'Discovery failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const unlockProfile = async (profileId: string) => {
    try {
      const response = await fetch('/api/v1/discovery/unlock-profile', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ profile_id: profileId })
      });

      const result = await response.json();

      if (result.success) {
        // Update the profile's unlock status in state
        setProfiles(prev => prev.map(p =>
          p.id === profileId
            ? {
                ...p,
                unlock_status: {
                  is_unlocked: true,
                  granted_at: result.access_info.granted_at,
                  expires_at: result.access_info.expires_at,
                  days_remaining: result.access_info.days_remaining
                }
              }
            : p
        ));
        return { success: true, result };
      } else {
        return { success: false, error: result.message };
      }
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  useEffect(() => {
    if (options.autoLoad !== false) {
      loadProfiles();
    }
  }, [options.page, options.search, options.category]);

  return {
    profiles,
    loading,
    pagination,
    error,
    loadProfiles,
    unlockProfile
  };
}
```

### Discovery Component Example
```tsx
import React from 'react';
import { useDiscovery } from './hooks/useDiscovery';

export function DiscoveryPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);

  const { profiles, loading, pagination, unlockProfile } = useDiscovery({
    page,
    search,
    category,
    pageSize: 20
  });

  const handleUnlock = async (profileId: string) => {
    const result = await unlockProfile(profileId);
    if (result.success) {
      toast.success(`Profile unlocked for 30 days!`);
    } else {
      toast.error(`Unlock failed: ${result.error}`);
    }
  };

  if (loading) return <DiscoveryLoader />;

  return (
    <div className="discovery-page">
      <SearchBar
        value={search}
        onChange={setSearch}
        categories={categories}
        selectedCategory={category}
        onCategoryChange={setCategory}
      />

      <div className="profiles-grid">
        {profiles.map(profile => (
          <ProfileCard
            key={profile.id}
            profile={profile}
            onUnlock={() => handleUnlock(profile.id)}
            isUnlocked={profile.unlock_status.is_unlocked}
            daysRemaining={profile.unlock_status.days_remaining}
          />
        ))}
      </div>

      <Pagination
        current={page}
        total={pagination?.total_pages || 0}
        onChange={setPage}
      />
    </div>
  );
}
```

---

## 💡 Implementation Guidelines

### 1. Profile Card UI States
```tsx
interface ProfileCardProps {
  profile: DiscoveryProfile;
  onUnlock: () => void;
  isUnlocked: boolean;
  daysRemaining?: number;
}

function ProfileCard({ profile, onUnlock, isUnlocked, daysRemaining }: ProfileCardProps) {
  return (
    <div className="profile-card">
      {/* Always show preview data */}
      <img src={profile.profile_pic_url} alt={profile.username} />
      <h3>{profile.username}</h3>
      <p>{profile.followers_count?.toLocaleString()} followers</p>
      <p>{profile.ai_analysis.primary_content_type}</p>

      {/* Unlock status and actions */}
      {isUnlocked ? (
        <div className="unlocked-status">
          <span>✅ Unlocked</span>
          <span>{daysRemaining} days left</span>
          <button onClick={() => openFullProfile(profile.id)}>
            View Full Analytics
          </button>
        </div>
      ) : (
        <div className="locked-status">
          <span>🔒 Unlock for full access</span>
          <button onClick={onUnlock} className="unlock-btn">
            Unlock (25 credits)
          </button>
        </div>
      )}
    </div>
  );
}
```

### 2. Credit Management Integration
```typescript
// Check credits before unlock
function useCreditsCheck() {
  const checkCreditsForUnlock = async (requiredCredits: number = 25) => {
    const dashboardResponse = await fetch('/api/v1/discovery/dashboard');
    const dashboard = await dashboardResponse.json();

    const availableCredits = dashboard.user_credits.current_balance;

    if (availableCredits < requiredCredits) {
      return {
        canUnlock: false,
        message: `Need ${requiredCredits} credits. You have ${availableCredits}.`,
        shortfall: requiredCredits - availableCredits
      };
    }

    return { canUnlock: true };
  };

  return { checkCreditsForUnlock };
}
```

### 3. Search and Filter Integration
```typescript
// Advanced search implementation
interface DiscoveryFilters {
  search: string;
  categories: string[];
  followerRange: { min?: number; max?: number };
  sortBy: string;
}

function useAdvancedSearch() {
  const [filters, setFilters] = useState<DiscoveryFilters>({
    search: '',
    categories: [],
    followerRange: {},
    sortBy: 'followers_desc'
  });

  const searchProfiles = async () => {
    const response = await fetch('/api/v1/discovery/search-advanced', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: filters.search,
        categories: filters.categories,
        follower_range: filters.followerRange,
        sort_by: filters.sortBy,
        page: 1,
        page_size: 20
      })
    });

    return await response.json();
  };

  return { filters, setFilters, searchProfiles };
}
```

---

## 🔧 Error Handling

### Common Error Scenarios
```typescript
interface DiscoveryError {
  success: false;
  error: string;
  message: string;
}

// Handle unlock errors
function handleUnlockError(error: DiscoveryError) {
  switch (error.error) {
    case 'insufficient_credits':
      showCreditTopupDialog();
      break;
    case 'profile_not_found':
      showError('Profile no longer available');
      break;
    case 'credit_spend_failed':
      showError('Payment processing failed. Please try again.');
      break;
    default:
      showError(error.message || 'Unknown error occurred');
  }
}
```

### Rate Limiting
- **Discovery Browse**: No rate limiting (read-only)
- **Profile Unlock**: Standard credit validation and transaction limits
- **Search**: Reasonable limits to prevent abuse

---

## 📱 Mobile Considerations

### Responsive Design
- Use infinite scroll for mobile discovery
- Implement pull-to-refresh for profile lists
- Optimize image loading for mobile networks
- Consider reduced data loading for mobile

### Performance Optimization
- Implement image lazy loading
- Use pagination for large result sets
- Cache frequently accessed data
- Optimize for slow network connections

---

This API provides everything needed for a comprehensive creator discovery experience! The frontend can build powerful discovery interfaces with search, filtering, unlocking, and management capabilities. 🚀