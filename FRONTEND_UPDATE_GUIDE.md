# 🚨 CRITICAL FRONTEND UPDATE GUIDE
## Backend Changes Requiring Immediate Frontend Updates

**Date**: August 3, 2025  
**Backend Version**: 2.0.1-comprehensive  
**Priority**: **CRITICAL** - Frontend integration broken without these updates

---

## ⚠️ **BREAKING CHANGES SUMMARY**

### **1. AUTHENTICATION NOW REQUIRED FOR ALL PROFILE ENDPOINTS**
**❌ OLD (No longer works):**
```javascript
fetch('/api/v1/instagram/profile/username')
```

**✅ NEW (Required):**
```javascript
fetch('/api/v1/instagram/profile/username', {
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json'
  }
})
```

### **2. API BASE URL CHANGED**
**❌ OLD:** `/api/` or `/`  
**✅ NEW:** `/api/v1/`

### **3. RESPONSE STRUCTURE CHANGED**
**❌ OLD Direct Access:**
```javascript
const followers = response.followers_count;
const username = response.username;
```

**✅ NEW Nested Structure:**
```javascript
const followers = response.profile.followers_count;
const username = response.profile.username;
const analytics = response.analytics.engagement_rate;
```

---

## 🔑 **AUTHENTICATION IMPLEMENTATION**

### **Token Storage & Management**
```javascript
// Store tokens after login
localStorage.setItem('access_token', loginResponse.access_token);
localStorage.setItem('refresh_token', loginResponse.refresh_token);

// Create authenticated fetch function
const apiCall = async (endpoint, options = {}) => {
  const token = localStorage.getItem('access_token');
  
  return fetch(`/api/v1${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
};
```

### **Login Flow Update**
```javascript
// POST /api/v1/auth/login
const loginUser = async (email, password) => {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  
  if (response.ok) {
    const data = await response.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return data.user;
  }
  throw new Error('Login failed');
};
```

### **Registration Flow Update**
```javascript
// POST /api/v1/auth/register
const registerUser = async (email, password, full_name) => {
  const response = await fetch('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name })
  });
  
  const data = await response.json();
  
  if (data.email_confirmation_required) {
    // Show email confirmation message
    return { requiresConfirmation: true, message: data.message };
  }
  
  return data.user;
};
```

---

## 📱 **UPDATED API ENDPOINTS**

### **Main Profile Analysis**
```javascript
// GET /api/v1/instagram/profile/{username}
// ⏱️ Response Time: 15-30 seconds (first time), <1 second (cached)
const analyzeProfile = async (username) => {
  const response = await apiCall(`/instagram/profile/${username}`, {
    timeout: 35000 // Set 35-second timeout
  });
  
  if (response.ok) {
    const data = await response.json();
    return {
      profile: data.profile,        // Basic profile info
      analytics: data.analytics,    // Engagement, influence scores
      meta: data.meta              // Access info, timestamps
    };
  }
  
  throw new Error(`Analysis failed: ${response.status}`);
};
```

### **Cached Analytics (Fast)**
```javascript
// GET /api/v1/instagram/profile/{username}/analytics
// ⏱️ Response Time: <1 second (database only)
const getCachedAnalytics = async (username) => {
  const response = await apiCall(`/instagram/profile/${username}/analytics`);
  
  if (response.status === 404) {
    // Profile not cached, redirect to main analysis
    return { needsAnalysis: true };
  }
  
  return await response.json();
};
```

### **User Dashboard**
```javascript
// GET /api/v1/auth/dashboard
const getUserDashboard = async () => {
  const response = await apiCall('/auth/dashboard');
  const data = await response.json();
  
  return {
    searchCount: data.total_searches,
    favoritesCount: data.favorites_count,
    recentSearches: data.recent_searches,
    credits: data.credits_remaining
  };
};
```

### **Search History**
```javascript
// GET /api/v1/auth/search-history?page=1&page_size=10
const getSearchHistory = async (page = 1, pageSize = 10) => {
  const response = await apiCall(`/auth/search-history?page=${page}&page_size=${pageSize}`);
  return await response.json();
};
```

---

## 🎛️ **SETTINGS ENDPOINTS**

### **Profile Settings**
```javascript
// GET /api/v1/settings/profile
const getProfileSettings = async () => {
  const response = await apiCall('/settings/profile');
  return await response.json();
};

// PUT /api/v1/settings/profile
const updateProfile = async (profileData) => {
  const response = await apiCall('/settings/profile', {
    method: 'PUT',
    body: JSON.stringify(profileData)
  });
  return await response.json();
};
```

### **Avatar Upload**
```javascript
// POST /api/v1/settings/profile/avatar
const uploadAvatar = async (imageFile) => {
  const formData = new FormData();
  formData.append('file', imageFile);
  
  const token = localStorage.getItem('access_token');
  const response = await fetch('/api/v1/settings/profile/avatar', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
      // Don't set Content-Type for FormData
    },
    body: formData
  });
  
  return await response.json();
};
```

### **Security Settings**
```javascript
// POST /api/v1/settings/security/password
const changePassword = async (currentPassword, newPassword) => {
  const response = await apiCall('/settings/security/password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword
    })
  });
  return await response.json();
};

// POST /api/v1/settings/security/2fa
const toggle2FA = async (enabled) => {
  const response = await apiCall('/settings/security/2fa', {
    method: 'POST',
    body: JSON.stringify({ enabled })
  });
  return await response.json();
};
```

---

## ⚡ **RESPONSE FORMATS**

### **Profile Analysis Response**
```javascript
{
  "success": true,
  "profile": {
    "username": "example_user",
    "full_name": "Example User",
    "followers_count": 50000,
    "following_count": 1000,
    "posts_count": 500,
    "is_verified": false,
    "is_private": false,
    "profile_pic_url": "https://...",
    "biography": "User bio text",
    "external_url": "https://example.com"
  },
  "analytics": {
    "engagement_rate": 3.5,
    "influence_score": 75.2,
    "data_quality_score": 95.0
  },
  "meta": {
    "analysis_timestamp": "2025-08-03T12:00:00Z",
    "user_has_access": true,
    "access_expires_in_days": 30,
    "data_source": "fresh_fetch"
  }
}
```

### **User Dashboard Response**
```javascript
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "User Name",
    "role": "free",
    "credits": 8
  },
  "stats": {
    "total_searches": 15,
    "favorites_count": 5,
    "searches_this_month": 12
  },
  "recent_searches": [
    {
      "username": "example_user",
      "searched_at": "2025-08-03T10:00:00Z",
      "analysis_type": "comprehensive"
    }
  ]
}
```

---

## 🚨 **ERROR HANDLING**

### **Authentication Errors**
```javascript
const handleApiError = async (response) => {
  if (response.status === 401) {
    // Token expired or invalid
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    // Redirect to login
    window.location.href = '/login';
    return;
  }
  
  if (response.status === 403) {
    // Insufficient permissions
    throw new Error('Access denied');
  }
  
  const errorData = await response.json();
  throw new Error(errorData.detail || 'API request failed');
};
```

### **Timeout Handling**
```javascript
const fetchWithTimeout = async (url, options = {}) => {
  const controller = new AbortController();
  const timeout = options.timeout || 35000; // 35 seconds default
  
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timeout - analysis may take up to 30 seconds');
    }
    throw error;
  }
};
```

---

## 🎨 **UI/UX RECOMMENDATIONS**

### **Loading States**
```javascript
// Profile analysis can take 15-30 seconds
const [isAnalyzing, setIsAnalyzing] = useState(false);
const [analysisProgress, setAnalysisProgress] = useState(0);

const analyzeProfile = async (username) => {
  setIsAnalyzing(true);
  
  // Show progressive loading
  const progressInterval = setInterval(() => {
    setAnalysisProgress(prev => Math.min(prev + 1, 95));
  }, 300);
  
  try {
    const result = await apiCall(`/instagram/profile/${username}`);
    setAnalysisProgress(100);
    return result;
  } finally {
    clearInterval(progressInterval);
    setIsAnalyzing(false);
    setAnalysisProgress(0);
  }
};
```

### **Error Messages**
```javascript
const getErrorMessage = (error, endpoint) => {
  if (endpoint.includes('/analytics') && error.status === 404) {
    return 'Profile not analyzed yet. Click "Analyze Profile" to get detailed insights.';
  }
  
  if (error.status === 503) {
    return 'Instagram data service temporarily unavailable. Please try again in a few minutes.';
  }
  
  return error.message || 'An unexpected error occurred.';
};
```

---

## 🔄 **MIGRATION CHECKLIST**

### **Immediate Actions Required:**

- [ ] **Update all API calls to include `/api/v1/` prefix**
- [ ] **Add Authentication headers to all protected endpoints**
- [ ] **Update response data access patterns (nested structure)**
- [ ] **Increase request timeouts to 35+ seconds for profile analysis**
- [ ] **Implement proper error handling for new status codes**
- [ ] **Update login/registration flows for new response formats**
- [ ] **Test all authentication flows end-to-end**
- [ ] **Update loading states for long-running requests**

### **Testing Endpoints:**

1. **Test Authentication:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"password123"}'
   ```

2. **Test Profile Analysis:**
   ```bash
   curl -X GET http://localhost:8000/api/v1/instagram/profile/example_user \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Test Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```

---

## 🆘 **SUPPORT & TROUBLESHOOTING**

### **Common Issues:**

1. **"401 Unauthorized"** → Missing or invalid Authorization header
2. **"404 Not Found"** → Wrong endpoint URL or profile not cached
3. **"503 Service Unavailable"** → External Instagram API temporarily down
4. **Timeout errors** → Increase timeout to 35+ seconds
5. **CORS errors** → Check if credentials are included in requests

### **Debug Mode:**
```javascript
const DEBUG = true;

const apiCall = async (endpoint, options = {}) => {
  if (DEBUG) {
    console.log(`API Call: ${endpoint}`, options);
  }
  
  const response = await fetch(`/api/v1${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  
  if (DEBUG) {
    console.log(`Response: ${response.status}`, await response.clone().text());
  }
  
  return response;
};
```

---

## 🎯 **PRIORITY ORDER**

1. **HIGH:** Authentication implementation
2. **HIGH:** API endpoint URL updates  
3. **HIGH:** Response structure updates
4. **MEDIUM:** Error handling improvements
5. **MEDIUM:** Loading state optimization
6. **LOW:** UI/UX enhancements

**Estimated Implementation Time:** 2-4 hours for core updates, 1-2 hours for testing

---

**Questions or issues?** Check the backend logs at `/health` endpoint or contact the backend team.