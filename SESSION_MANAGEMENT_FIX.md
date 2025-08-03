# 🔐 Session Management Fix Guide

## Current Issue
Users are being redirected to login repeatedly, indicating session persistence problems.

## Root Cause Analysis
The issue is likely in the frontend implementation. The backend is working correctly (24-hour JWT tokens), but the frontend may not be:
1. Storing tokens properly after login
2. Sending Authorization headers consistently
3. Handling token refresh

## 🛠️ Frontend Implementation Fix

### 1. **Proper Token Storage After Login**
```javascript
// In your login function
const loginUser = async (email, password) => {
  try {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    if (response.ok) {
      const data = await response.json();
      
      // CRITICAL: Store tokens immediately
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('user_data', JSON.stringify(data.user));
      
      // Optional: Log success for debugging
      console.log('✅ Login successful, tokens stored');
      
      return data.user;
    }
    throw new Error('Login failed');
  } catch (error) {
    console.error('❌ Login error:', error);
    throw error;
  }
};
```

### 2. **Global API Call Function**
Create a single function that ALL API calls use:

```javascript
// utils/api.js
const API_BASE = '/api/v1';

export const apiCall = async (endpoint, options = {}) => {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    // No token found, redirect to login
    window.location.href = '/login';
    throw new Error('No authentication token');
  }

  const config = {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  };

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    
    if (response.status === 401) {
      // Token invalid/expired
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_data');
      window.location.href = '/login';
      throw new Error('Authentication failed');
    }
    
    return response;
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
};
```

### 3. **Update ALL API Calls**
Replace ALL direct fetch calls with the apiCall function:

```javascript
// ❌ OLD (Direct fetch)
const response = await fetch('/api/v1/auth/dashboard');

// ✅ NEW (Using apiCall)
const response = await apiCall('/auth/dashboard');
```

### 4. **Route Protection**
Add authentication checking to your router/navigation:

```javascript
// utils/auth.js
export const isAuthenticated = () => {
  const token = localStorage.getItem('access_token');
  return token !== null;
};

export const requireAuth = () => {
  if (!isAuthenticated()) {
    window.location.href = '/login';
    return false;
  }
  return true;
};

// In your React router or page components
useEffect(() => {
  requireAuth();
}, []);
```

### 5. **Login State Management**
```javascript
// In your main App component or auth context
const [isLoggedIn, setIsLoggedIn] = useState(false);
const [user, setUser] = useState(null);

useEffect(() => {
  // Check if user is logged in on app start
  const token = localStorage.getItem('access_token');
  const userData = localStorage.getItem('user_data');
  
  if (token && userData) {
    setIsLoggedIn(true);
    setUser(JSON.parse(userData));
  }
}, []);

const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user_data');
  setIsLoggedIn(false);
  setUser(null);
  window.location.href = '/login';
};
```

## 🧪 Testing Your Implementation

### Test 1: Check Token Storage
After login, open browser console and run:
```javascript
console.log('Token:', localStorage.getItem('access_token'));
console.log('User:', localStorage.getItem('user_data'));
```

### Test 2: Test API Calls
```javascript
// Test authenticated endpoint
fetch('/api/v1/auth/debug/session', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  }
}).then(r => r.json()).then(console.log);
```

### Test 3: Check Network Tab
1. Open browser DevTools → Network tab
2. Navigate to any page that makes API calls
3. Verify every request has `Authorization: Bearer <token>` header

## 🚨 Common Mistakes to Avoid

1. **Not storing tokens after login**
2. **Forgetting Authorization header on some API calls**
3. **Using different fetch functions in different components**
4. **Not handling 401 responses**
5. **Not clearing tokens on logout**

## 🔍 Debug Endpoints

Use these backend endpoints to debug session issues:

```bash
# Test basic token validation
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/auth/token-test

# Get detailed session info
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/auth/debug/session
```

## 📝 Implementation Checklist

- [ ] Update login function to store tokens
- [ ] Create global apiCall function
- [ ] Replace all fetch calls with apiCall
- [ ] Add route protection
- [ ] Add logout functionality
- [ ] Test token storage in browser console
- [ ] Verify Authorization headers in Network tab
- [ ] Test session persistence across page refreshes

## ⚡ Quick Fix

If you want the fastest fix, add this to every page component:

```javascript
useEffect(() => {
  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/login';
  }
}, []);
```

This ensures users are redirected to login if they don't have a token.