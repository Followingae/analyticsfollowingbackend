# Creators Page - Unlocked Profiles Endpoint

## 🎯 Problem Solved

**Issue**: Creators page was empty because there was no endpoint to fetch unlocked profiles for a user.

**Solution**: Created new endpoint to get all profiles that the current user has access to.

## ✅ New Endpoint

### `GET /api/v1/auth/unlocked-profiles`

**Description**: Get all profiles the user has unlocked/has access to

**Authentication**: Required (Bearer token)

**Parameters**:
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (max 50, default: 20)

## 📝 Frontend Integration

### Basic Usage
```javascript
const getUnlockedProfiles = async (page = 1, pageSize = 20) => {
  const response = await fetch(`/api/v1/auth/unlocked-profiles?page=${page}&page_size=${pageSize}`, {
    headers: {
      'Authorization': `Bearer ${userToken}`,
      'Content-Type': 'application/json'
    }
  });
  
  const data = await response.json();
  return data;
};
```

### Response Format
```json
{
  "profiles": [
    {
      "username": "shaq",
      "full_name": "Shaq",
      "profile_pic_url": "/api/proxy-image?url=https://scontent-...",
      "profile_pic_url_hd": "/api/proxy-image?url=https://scontent-...",
      "followers_count": 28500000,
      "posts_count": 150,
      "is_verified": true,
      "is_private": false,
      "engagement_rate": 2.34,
      "influence_score": 8.7,
      
      "access_granted_at": "2025-08-03T16:15:00Z",
      "access_expires_at": "2025-09-02T16:15:00Z", 
      "days_remaining": 30,
      "profile_id": "ff5f144c-3f39-4687-97e6-6b5610f130f2"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_count": 5,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false
  },
  "meta": {
    "user_id": "12345",
    "retrieved_at": "2025-08-03T16:30:00Z",
    "note": "All image URLs are pre-proxied to eliminate CORS issues"
  }
}
```

## 🔄 React Implementation Example

```jsx
import React, { useState, useEffect } from 'react';

const CreatorsPage = () => {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({});

  useEffect(() => {
    loadUnlockedProfiles();
  }, []);

  const loadUnlockedProfiles = async (page = 1) => {
    try {
      setLoading(true);
      const data = await getUnlockedProfiles(page, 20);
      
      setProfiles(data.profiles);
      setPagination(data.pagination);
    } catch (error) {
      console.error('Failed to load unlocked profiles:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading your unlocked profiles...</div>;

  if (profiles.length === 0) {
    return (
      <div>
        <h2>No Unlocked Profiles</h2>
        <p>Search for Instagram profiles to unlock them and see them here.</p>
      </div>
    );
  }

  return (
    <div>
      <h2>Your Unlocked Profiles ({pagination.total_count})</h2>
      
      <div className="profiles-grid">
        {profiles.map(profile => (
          <div key={profile.username} className="profile-card">
            <img 
              src={profile.profile_pic_url_hd || profile.profile_pic_url} 
              alt={profile.full_name}
              className="profile-picture"
            />
            <div className="profile-info">
              <h3>{profile.full_name}</h3>
              <p>@{profile.username}</p>
              <p>{profile.followers_count.toLocaleString()} followers</p>
              <p>Access expires in {profile.days_remaining} days</p>
              
              <button onClick={() => viewProfile(profile.username)}>
                View Analytics
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {pagination.total_pages > 1 && (
        <div className="pagination">
          <button 
            disabled={!pagination.has_previous}
            onClick={() => loadUnlockedProfiles(pagination.page - 1)}
          >
            Previous
          </button>
          
          <span>Page {pagination.page} of {pagination.total_pages}</span>
          
          <button 
            disabled={!pagination.has_next}
            onClick={() => loadUnlockedProfiles(pagination.page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
```

## 🎨 Key Features

✅ **Paginated Results**: Handle large numbers of unlocked profiles efficiently

✅ **Pre-proxied URLs**: All image URLs work without CORS issues

✅ **Access Information**: Shows when access was granted and when it expires

✅ **Profile Metrics**: Includes key stats like followers, engagement rate, influence score

✅ **Expiry Tracking**: Shows days remaining for each profile access

## 🔧 Error Handling

```javascript
const handleUnlockedProfilesError = (error) => {
  if (error.status === 401) {
    // Token expired - redirect to login
    redirectToLogin();
  } else if (error.status === 500) {
    // Server error - show retry button
    showRetryOption();
  } else {
    // Other errors - show generic message
    showErrorMessage('Failed to load profiles');
  }
};
```

## 📋 Frontend TODO

1. **Update Creators Page**: Replace empty state with call to new endpoint
2. **Add Loading State**: Show loading spinner while fetching profiles  
3. **Handle Empty State**: Show message when user has no unlocked profiles
4. **Add Pagination**: Implement pagination controls for large lists
5. **Profile Cards**: Design profile cards showing key metrics and access info
6. **Navigation**: Add "View Analytics" buttons that navigate to profile details

## 🚀 Benefits

✅ **Solves Empty Creators Page**: Users now see their unlocked profiles

✅ **Efficient Loading**: Paginated responses prevent performance issues

✅ **Rich Profile Data**: Shows engagement metrics and access information  

✅ **CORS-Free Images**: All profile pictures load without issues

✅ **Real-time Access**: Shows current access status and expiry

---

**Status**: ✅ **Ready for Frontend Integration**

The endpoint is live and ready to use. Update your creators page to call this endpoint and display the unlocked profiles!