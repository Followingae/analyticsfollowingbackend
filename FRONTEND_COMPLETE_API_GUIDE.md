# Complete Frontend API Integration Guide

## ⚠️ IMPORTANT: Only Real Endpoints - No Mocks!
This guide contains ONLY endpoints that actually exist in the backend. Every endpoint listed here is implemented and working.

## 🔐 Authentication System

### Login
```javascript
POST /api/v1/auth/login
Body: {
  "email": "user@example.com",
  "password": "password123"
}
Response: {
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "role": "user|admin",
    "credits": 5000
  }
}
```

### Register
```javascript
POST /api/v1/auth/register
Body: {
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

### Current User
```javascript
GET /api/v1/auth/me
Headers: { "Authorization": "Bearer {token}" }
Response: {
  "id": "uuid",
  "email": "user@example.com",
  "role": "user",
  "credits": 5000,
  "subscription_tier": "premium"
}
```

## 💳 Credits System

### Get Balance
```javascript
GET /api/v1/credits/balance
Headers: { "Authorization": "Bearer {token}" }
Response: {
  "current_balance": 5000,
  "total_earned": 10000,
  "total_spent": 5000
}
```

### Get Wallet Summary
```javascript
GET /api/v1/credits/wallet/summary
Response: {
  "wallet": {
    "current_balance": 5000,
    "billing_cycle_start": "2025-01-01",
    "billing_cycle_end": "2025-01-31"
  },
  "usage": {
    "spent_this_month": 1500,
    "remaining": 3500
  }
}
```

### Get Transactions
```javascript
GET /api/v1/credits/transactions?page=1&limit=50
Response: {
  "transactions": [...],
  "total": 100,
  "page": 1,
  "pages": 2
}
```

### Get Pricing Rules
```javascript
GET /api/v1/credits/pricing
Response: {
  "actions": {
    "influencer_unlock": { "cost": 25, "free_monthly": 0 },
    "post_analytics": { "cost": 5, "free_monthly": 0 },
    "discovery_pagination": { "cost": 10, "free_monthly": 5 }
  }
}
```

## 🔍 Creator Search & Analytics

### Search Creator (Main Endpoint)
```javascript
GET /api/v1/search/creator/{username}
Headers: { "Authorization": "Bearer {token}" }
Response: {
  "status": "success",
  "data": {
    "overview": { ... },
    "audience": { ... },
    "engagement": { ... },
    "content": { ... },
    "posts": [ ... ]
  }
}
```

### Get Post Analytics
```javascript
POST /api/v1/post-analytics/analyze
Headers: { "Authorization": "Bearer {token}" }
Body: {
  "url": "https://instagram.com/p/shortcode"
}
Response: {
  "post_data": { ... },
  "ai_analysis": { ... },
  "engagement_metrics": { ... }
}
```

## 🔓 Discovery System

### Browse Profiles
```javascript
GET /api/v1/discovery/browse?page=1&page_size=20&min_followers=1000
Response: {
  "profiles": [
    {
      "id": "uuid",
      "username": "creator123",
      "followers_count": 50000,
      "is_unlocked": false,
      "unlock_expires_at": null
    }
  ],
  "total": 500,
  "page": 1
}
```

### Unlock Profile
```javascript
POST /api/v1/discovery/unlock-profile
Body: {
  "profile_id": "uuid",
  "credits_to_spend": 25
}
Response: {
  "success": true,
  "profile": { ... },
  "access_expires_at": "2025-02-15T00:00:00Z",
  "credits_spent": 25
}
```

### Get Unlocked Profiles
```javascript
GET /api/v1/discovery/unlocked-profiles
Response: {
  "profiles": [
    {
      "profile_id": "uuid",
      "username": "creator123",
      "accessed_at": "2025-01-15",
      "expires_at": "2025-02-15",
      "days_remaining": 30
    }
  ]
}
```

## 👥 Team Management

### Get Team
```javascript
GET /api/v1/teams/my-team
Response: {
  "team": {
    "id": "uuid",
    "name": "Marketing Team",
    "owner_id": "uuid",
    "subscription_tier": "premium"
  },
  "members": [ ... ]
}
```

### Invite Member
```javascript
POST /api/v1/teams/invite
Body: {
  "email": "newmember@example.com",
  "role": "member"
}
```

## 📊 Campaign Management

### List Campaigns
```javascript
GET /api/v1/campaigns?page=1&limit=20
Response: {
  "campaigns": [ ... ],
  "total": 50
}
```

### Create Campaign
```javascript
POST /api/v1/campaigns
Body: {
  "name": "Spring Campaign 2025",
  "description": "Product launch campaign",
  "start_date": "2025-03-01",
  "end_date": "2025-03-31",
  "budget": 10000
}
```

### Get Campaign AI Insights
```javascript
GET /api/v1/campaigns/{campaign_id}/ai-insights
Response: {
  "insights": {
    "predicted_performance": { ... },
    "recommendations": [ ... ],
    "risk_analysis": { ... }
  }
}
```

## 💰 Billing & Stripe Integration

### Create Checkout Session
```javascript
POST /api/v1/stripe/create-checkout-session
Body: {
  "price_id": "price_xxx",
  "quantity": 1,
  "success_url": "https://app.com/success",
  "cancel_url": "https://app.com/cancel"
}
Response: {
  "checkout_url": "https://checkout.stripe.com/..."
}
```

### Get Subscription Status
```javascript
GET /api/v1/billing/subscription/status
Response: {
  "active": true,
  "plan": "premium",
  "current_period_end": "2025-02-15",
  "cancel_at_period_end": false
}
```

## 🔨 Superadmin Panel (Admin Only)

### Dashboard Statistics
```javascript
GET /api/v1/admin/dashboard/stats
Headers: { "Authorization": "Bearer {admin_token}" }
Response: {
  "users": {
    "total": 150,
    "active": 120,
    "premium": 45,
    "new_this_month": 12
  },
  "revenue": {
    "total_mrr": 25000.00,
    "new_mrr_this_month": 3500.00
  },
  "content": {
    "total_profiles": 5000,
    "profiles_analyzed_today": 25
  }
}
```

### User Management
```javascript
GET /api/v1/admin/users?page=1&limit=50
PUT /api/v1/admin/users/{user_id}
DELETE /api/v1/admin/users/{user_id}
```

### Credit Management
```javascript
POST /api/v1/admin/credits/add
Body: {
  "user_id": "uuid",
  "amount": 5000,
  "reason": "Manual adjustment"
}

POST /api/v1/admin/credits/remove
Body: {
  "user_id": "uuid",
  "amount": 1000,
  "reason": "Refund"
}
```

### Transaction History
```javascript
GET /api/v1/admin/billing/transactions?page=1&limit=50
Response: {
  "transactions": [ ... ],
  "total": 1000
}
```

### Revenue Report
```javascript
GET /api/v1/admin/billing/revenue?period=monthly
Response: {
  "revenue": [ ... ],
  "growth": 0.15,
  "churn": 0.05
}
```

### Content Management
```javascript
GET /api/v1/admin/content/profiles?page=1&limit=50
GET /api/v1/admin/content/unlocks?page=1&limit=50
```

### System Health
```javascript
GET /api/v1/admin/system/health
Response: {
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "ai_service": "operational"
}
```

## 👔 HRM System (Admin Only)

### Employee Management
```javascript
// Create Employee
POST /api/v1/hrm/employees
Body: {
  "employee_id": "EMP001",
  "full_name": "John Doe",
  "email": "john@company.com",
  "department": "Engineering",
  "position": "Senior Developer",
  "hire_date": "2024-01-15",
  "base_salary": 5000
}

// List Employees
GET /api/v1/hrm/employees

// Get Employee
GET /api/v1/hrm/employees/{employee_id}

// Update Employee
PUT /api/v1/hrm/employees/{employee_id}

// Delete Employee
DELETE /api/v1/hrm/employees/{employee_id}
```

### Attendance Management
```javascript
// Upload CSV from Fingerprint Machine
POST /api/v1/hrm/attendance/upload-csv
Headers: { "Content-Type": "multipart/form-data" }
Body: FormData with 'file' and 'month' fields

// Get Monthly Attendance
GET /api/v1/hrm/attendance/employee/{employee_id}/monthly?year=2025&month=1

// Get Monthly Report
GET /api/v1/hrm/attendance/monthly-report?year=2025&month=1
```

### Timesheet Management
```javascript
// Generate Timesheet
POST /api/v1/hrm/timesheets/generate/{employee_id}?year=2025&month=1

// Get Current Month Timesheets
GET /api/v1/hrm/timesheets/current-month

// Get Timesheets by Month
GET /api/v1/hrm/timesheets/by-month/2025/1

// Approve Timesheet
POST /api/v1/hrm/timesheets/approve/{timesheet_id}
```

### Payroll Processing
```javascript
// Calculate Payroll
POST /api/v1/hrm/payroll/calculate/{employee_id}?year=2025&month=1

// Calculate All Payroll
POST /api/v1/hrm/payroll/calculate/2025/1

// Get Pending Payroll
GET /api/v1/hrm/payroll/pending

// Process Payment
POST /api/v1/hrm/payroll/process-payment/{payroll_id}

// Get Payslips
GET /api/v1/hrm/payroll/payslips/{employee_id}

// Get Monthly Summary
GET /api/v1/hrm/payroll/summary/2025/1
```

### Leave Management
```javascript
// Request Leave
POST /api/v1/hrm/leaves/request
Body: {
  "employee_id": "uuid",
  "leave_type": "annual|sick|personal",
  "start_date": "2025-02-01",
  "end_date": "2025-02-03",
  "reason": "Personal vacation"
}

// Get Pending Leaves
GET /api/v1/hrm/leaves/pending

// Approve Leave
POST /api/v1/hrm/leaves/approve/{leave_id}

// Reject Leave
POST /api/v1/hrm/leaves/reject/{leave_id}

// Get Leave Balance
GET /api/v1/hrm/leaves/balance/{employee_id}

// Get Leave Report
GET /api/v1/hrm/leaves/report?year=2025&month=1
```

### HRM Dashboard
```javascript
// Overview
GET /api/v1/hrm/dashboard/overview

// Attendance Summary
GET /api/v1/hrm/dashboard/attendance-summary

// Payroll Summary
GET /api/v1/hrm/dashboard/payroll-summary

// Employee Statistics
GET /api/v1/hrm/dashboard/employee-statistics
```

## 🚀 Implementation Example

### Axios Configuration
```javascript
// api/config.js
import axios from 'axios';

const API = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000
});

// Add auth token to requests
API.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default API;
```

### Service Layer
```javascript
// services/creatorService.js
import API from './config';

export const creatorService = {
  searchCreator: async (username) => {
    const response = await API.get(`/api/v1/search/creator/${username}`);
    return response.data;
  },

  unlockProfile: async (profileId) => {
    const response = await API.post('/api/v1/discovery/unlock-profile', {
      profile_id: profileId,
      credits_to_spend: 25
    });
    return response.data;
  },

  browseProfiles: async (params) => {
    const response = await API.get('/api/v1/discovery/browse', { params });
    return response.data;
  }
};
```

### React Hook Example
```javascript
// hooks/useCreatorSearch.js
import { useState, useCallback } from 'react';
import { creatorService } from '@/services/creatorService';

export function useCreatorSearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const searchCreator = useCallback(async (username) => {
    setLoading(true);
    setError(null);

    try {
      const result = await creatorService.searchCreator(username);
      setData(result.data);
      return result;
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { searchCreator, loading, error, data };
}
```

## 📝 Important Notes

1. **Authentication Required**: All endpoints except `/api/v1/auth/login` and `/api/v1/auth/register` require Bearer token

2. **Admin Endpoints**: All `/api/v1/admin/*` and `/api/v1/hrm/*` endpoints require admin role

3. **Credit Costs**:
   - Profile Unlock: 25 credits
   - Post Analytics: 5 credits
   - Discovery Browse: 10 credits per page (after 5 free pages)

4. **Rate Limits**:
   - Standard users: 100 requests/minute
   - Premium users: 500 requests/minute
   - Admin users: No limit

5. **File Uploads**: Use `multipart/form-data` for CSV uploads in HRM

6. **Error Format**:
   ```json
   {
     "detail": "Error message",
     "status_code": 400
   }
   ```

## 🧪 Test Credentials

### Admin Account
- Email: `zain@following.ae`
- Password: `Following0925_25`

### Test User Account
- Email: `client@analyticsfollowing.com`
- Password: Check with backend team

## ⚠️ CRITICAL: No Mock Endpoints!
Every endpoint in this document is real and implemented in the backend. Do not create mock data or fake endpoints in the frontend. If an endpoint is not listed here, it doesn't exist.