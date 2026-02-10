# 🚨 URGENT: Frontend Superadmin Dashboard Fix Guide

## Problem: Dashboard Shows 0 for All Values

## ✅ SOLUTION: Use These Exact API Endpoints

### 1. Main Dashboard Data
```typescript
GET /api/v1/admin/superadmin/dashboard
Headers: {
  'Authorization': 'Bearer {your_token}',
  'Content-Type': 'application/json'
}

Expected Response:
{
  "total_users": 150,
  "active_users": 45,
  "total_profiles": 2500,
  "total_revenue": 15000.00,
  "system_health": {
    "status": "healthy",
    "uptime_percentage": 99.9
  }
}
```

### 2. Detailed Statistics
```typescript
GET /api/v1/admin/superadmin/stats
Headers: {
  'Authorization': 'Bearer {your_token}'
}
```

### 3. Users List
```typescript
GET /api/v1/admin/superadmin/users?page=1&page_size=10
Headers: {
  'Authorization': 'Bearer {your_token}'
}
```

## 🔧 Frontend Implementation (Copy This Code)

```typescript
// superadminApi.ts
const API_BASE = 'http://localhost:8000'; // or your production URL

export const superadminApi = {
  async getDashboard() {
    const token = localStorage.getItem('authToken'); // or however you store token

    const response = await fetch(`${API_BASE}/api/v1/admin/superadmin/dashboard`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      console.error('Dashboard Error:', response.status);
      const text = await response.text();
      console.error('Response:', text);
      throw new Error(`Failed: ${response.status}`);
    }

    return response.json();
  }
};

// Component
useEffect(() => {
  superadminApi.getDashboard()
    .then(data => {
      console.log('Dashboard data:', data);
      setDashboardData(data);
    })
    .catch(err => {
      console.error('Failed to load dashboard:', err);
    });
}, []);
```

## 🐛 Quick Debugging Steps

### Step 1: Check User Role
```sql
-- Run this in Supabase to verify user is superadmin
SELECT email, role FROM users WHERE email = 'your_email@example.com';
-- Role MUST be 'superadmin', not 'admin'
```

### Step 2: Test API Directly
```bash
# Get your token from login response or localStorage
# Then test this command:
curl -X GET "http://localhost:8000/api/v1/admin/superadmin/dashboard" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Step 3: Check These Common Issues

#### ❌ WRONG Endpoints (Don't Use These):
- `/api/v1/superadmin/dashboard` (missing /admin)
- `/api/v1/admin/dashboard` (missing /superadmin)
- `/api/admin/superadmin/dashboard` (missing /v1)

#### ✅ CORRECT Endpoints (Use These):
- `/api/v1/admin/superadmin/dashboard`
- `/api/v1/admin/superadmin/stats`
- `/api/v1/admin/superadmin/users`

### Step 4: Check Authorization
```typescript
// Make sure token is included correctly:
console.log('Token being sent:', token);
console.log('Full auth header:', `Bearer ${token}`);
```

## 📋 Complete Checklist for Frontend Team

1. **API Base URL**: Confirm using correct backend URL
   ```typescript
   const API_BASE = 'http://localhost:8000'; // NOT http://localhost:3000
   ```

2. **User Authentication**: Verify user is logged in as superadmin
   ```typescript
   const user = getCurrentUser();
   console.log('User role:', user.role); // Must be 'superadmin'
   ```

3. **Include Token**: All requests need Authorization header
   ```typescript
   headers: {
     'Authorization': `Bearer ${token}` // Don't forget 'Bearer ' prefix
   }
   ```

4. **Check Network Tab**:
   - Open DevTools → Network
   - Look for `/api/v1/admin/superadmin/dashboard`
   - Check Status (should be 200, not 403 or 401)
   - Check Response (should have data, not empty)

## 🚀 Working Example Request

```javascript
// This is a complete working example
async function loadSuperadminDashboard() {
  try {
    const token = localStorage.getItem('authToken');

    if (!token) {
      console.error('No auth token found');
      return;
    }

    const response = await fetch('http://localhost:8000/api/v1/admin/superadmin/dashboard', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    console.log('Response status:', response.status);

    if (response.status === 403) {
      console.error('User is not superadmin');
      return;
    }

    if (response.status === 401) {
      console.error('Token is invalid or expired');
      return;
    }

    const data = await response.json();
    console.log('Dashboard data received:', data);

    // Update your UI with data
    updateDashboard(data);

  } catch (error) {
    console.error('Dashboard load failed:', error);
  }
}
```

## ⚡ If Still Showing 0

If dashboard still shows 0 after following above steps:

1. **Backend might have no data**: Check if database actually has users/profiles
2. **Cache issue**: Clear browser cache and localStorage
3. **Wrong environment**: Make sure frontend is pointing to correct backend environment
4. **CORS issue**: Backend must allow frontend origin

## Need More Help?

Share these details with backend team:
1. Screenshot of Network tab showing the API request
2. Console logs showing any errors
3. The exact token being used (first 10 characters only for security)
4. User email you're testing with