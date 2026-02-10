# Superadmin Frontend Integration Guide

## Overview
The superadmin system has been streamlined to focus on core functionality only. All unnecessary monitoring, circuit breakers, and overly complex features have been removed.

## Removed Features
- ❌ 80+ unnecessary monitoring endpoints
- ❌ Circuit breaker systems
- ❌ Worker health monitoring
- ❌ CDN health checks
- ❌ System uptime monitoring
- ❌ Complex analytics completeness checks
- ❌ Overly detailed server monitoring

## Core Superadmin Features (What's Left)

### 1. Dashboard & Statistics
**Endpoint**: `GET /api/v1/admin/dashboard/stats`
**Authentication**: Admin only
**Response**:
```json
{
  "users": {
    "total": 150,
    "active": 120,
    "premium": 45,
    "new_this_month": 12
  },
  "revenue": {
    "total_mrr": 25000.00,
    "new_mrr_this_month": 3500.00,
    "churn_rate": 0.05,
    "average_revenue_per_user": 166.67
  },
  "content": {
    "total_profiles": 5000,
    "profiles_analyzed_today": 25,
    "total_posts": 50000,
    "ai_analyses_completed": 45000
  },
  "system": {
    "api_calls_today": 12500,
    "credits_consumed_today": 25000,
    "active_sessions": 85
  }
}
```

### 2. User Management

#### List All Users
**Endpoint**: `GET /api/v1/admin/users?page=1&limit=50`
**Authentication**: Admin only
**Query Parameters**:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50)
- `search`: Search by email or name
- `role`: Filter by role (admin, user, premium)
- `status`: Filter by status (active, inactive, suspended)

#### Get User Details
**Endpoint**: `GET /api/v1/admin/users/{user_id}`
**Authentication**: Admin only

#### Update User
**Endpoint**: `PUT /api/v1/admin/users/{user_id}`
**Authentication**: Admin only
**Request Body**:
```json
{
  "role": "premium",
  "status": "active",
  "credits": 5000,
  "subscription_tier": "premium"
}
```

#### Suspend/Activate User
**Endpoint**: `POST /api/v1/admin/users/{user_id}/suspend`
**Endpoint**: `POST /api/v1/admin/users/{user_id}/activate`
**Authentication**: Admin only

### 3. Billing & Credits Management

#### View All Transactions
**Endpoint**: `GET /api/v1/admin/billing/transactions?page=1&limit=50`
**Authentication**: Admin only
**Query Parameters**:
- `page`: Page number
- `limit`: Items per page
- `user_id`: Filter by user
- `type`: Filter by type (credit_purchase, subscription, refund)
- `date_from`: Start date filter
- `date_to`: End date filter

#### Add Credits to User
**Endpoint**: `POST /api/v1/admin/credits/add`
**Authentication**: Admin only
**Request Body**:
```json
{
  "user_id": "uuid",
  "amount": 5000,
  "reason": "Compensation for service issue"
}
```

#### Process Refund
**Endpoint**: `POST /api/v1/admin/billing/refund`
**Authentication**: Admin only
**Request Body**:
```json
{
  "transaction_id": "uuid",
  "amount": 99.99,
  "reason": "Customer request"
}
```

### 4. Content Management

#### View All Profiles
**Endpoint**: `GET /api/v1/admin/content/profiles?page=1&limit=50`
**Authentication**: Admin only
**Query Parameters**:
- `page`: Page number
- `limit`: Items per page
- `search`: Search by username
- `verified`: Filter verified profiles
- `min_followers`: Minimum followers filter

#### Delete Profile
**Endpoint**: `DELETE /api/v1/admin/content/profiles/{profile_id}`
**Authentication**: Admin only

#### Bulk Delete Profiles
**Endpoint**: `POST /api/v1/admin/content/profiles/bulk-delete`
**Authentication**: Admin only
**Request Body**:
```json
{
  "profile_ids": ["uuid1", "uuid2", "uuid3"]
}
```

### 5. System Health (Simplified)
**Endpoint**: `GET /api/v1/admin/health`
**Authentication**: Admin only
**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "ai_service": "operational",
  "external_apis": {
    "instagram": "operational",
    "stripe": "operational"
  },
  "last_check": "2025-01-15T10:30:00Z"
}
```

### 6. HRM (Human Resource Management)

#### Employee Management
**List Employees**: `GET /api/v1/hrm/employees`
**Create Employee**: `POST /api/v1/hrm/employees`
**Update Employee**: `PUT /api/v1/hrm/employees/{employee_id}`
**Delete Employee**: `DELETE /api/v1/hrm/employees/{employee_id}`

#### Attendance & Timesheets
**Upload CSV**: `POST /api/v1/hrm/attendance/upload-csv`
```javascript
const formData = new FormData();
formData.append('file', csvFile);
formData.append('month', '2025-01');

await fetch('/api/v1/hrm/attendance/upload-csv', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});
```

**Generate Timesheet**: `POST /api/v1/hrm/timesheets/generate`
**Get Timesheet**: `GET /api/v1/hrm/timesheets/{timesheet_id}`
**Approve Timesheet**: `POST /api/v1/hrm/timesheets/{timesheet_id}/approve`

#### Payroll
**Calculate Payroll**: `POST /api/v1/hrm/payroll/calculate`
**Get Payroll**: `GET /api/v1/hrm/payroll/{payroll_id}`
**Process Payment**: `POST /api/v1/hrm/payroll/{payroll_id}/process`

#### Leave Management
**Request Leave**: `POST /api/v1/hrm/leaves`
**Approve/Reject Leave**: `POST /api/v1/hrm/leaves/{leave_id}/approve`
**Get Leave Balance**: `GET /api/v1/hrm/employees/{employee_id}/leave-balance`

## Frontend Implementation Example

### React Component Structure
```jsx
// src/pages/superadmin/Dashboard.jsx
import { useEffect, useState } from 'react';
import { adminApi } from '@/api/admin';

export function SuperadminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const data = await adminApi.getDashboardStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="dashboard">
      <h1>Superadmin Dashboard</h1>

      <div className="stats-grid">
        <StatCard
          title="Total Users"
          value={stats.users.total}
          change={stats.users.new_this_month}
        />
        <StatCard
          title="Monthly Revenue"
          value={`$${stats.revenue.total_mrr}`}
          change={stats.revenue.new_mrr_this_month}
        />
        <StatCard
          title="Profiles Analyzed"
          value={stats.content.profiles_analyzed_today}
        />
        <StatCard
          title="Active Sessions"
          value={stats.system.active_sessions}
        />
      </div>

      <div className="quick-actions">
        <button onClick={() => navigate('/superadmin/users')}>
          Manage Users
        </button>
        <button onClick={() => navigate('/superadmin/billing')}>
          View Transactions
        </button>
        <button onClick={() => navigate('/superadmin/hrm')}>
          HRM System
        </button>
      </div>
    </div>
  );
}
```

### API Service Layer
```javascript
// src/api/admin.js
const API_BASE = '/api/v1/admin';

export const adminApi = {
  // Dashboard
  getDashboardStats: async () => {
    const response = await fetch(`${API_BASE}/dashboard/stats`, {
      headers: getAuthHeaders()
    });
    return response.json();
  },

  // User Management
  getUsers: async (params) => {
    const query = new URLSearchParams(params);
    const response = await fetch(`${API_BASE}/users?${query}`, {
      headers: getAuthHeaders()
    });
    return response.json();
  },

  updateUser: async (userId, data) => {
    const response = await fetch(`${API_BASE}/users/${userId}`, {
      method: 'PUT',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    return response.json();
  },

  // Credits
  addCredits: async (userId, amount, reason) => {
    const response = await fetch(`${API_BASE}/credits/add`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user_id: userId, amount, reason })
    });
    return response.json();
  },

  // HRM
  uploadAttendanceCSV: async (file, month) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('month', month);

    const response = await fetch('/api/v1/hrm/attendance/upload-csv', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    return response.json();
  }
};
```

### HRM CSV Upload Component
```jsx
// src/pages/superadmin/HRM/AttendanceUpload.jsx
import { useState } from 'react';
import { adminApi } from '@/api/admin';

export function AttendanceUpload() {
  const [file, setFile] = useState(null);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const handleUpload = async () => {
    if (!file) {
      alert('Please select a CSV file');
      return;
    }

    setUploading(true);
    try {
      const data = await adminApi.uploadAttendanceCSV(file, month);
      setResult(data);
      alert(`Successfully uploaded ${data.records_processed} attendance records`);
    } catch (error) {
      alert('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="attendance-upload">
      <h2>Upload Attendance from Fingerprint Machine</h2>

      <div className="upload-form">
        <div className="form-group">
          <label>Select Month:</label>
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>CSV File:</label>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </div>

        <button
          onClick={handleUpload}
          disabled={uploading || !file}
        >
          {uploading ? 'Uploading...' : 'Upload Attendance'}
        </button>
      </div>

      {result && (
        <div className="upload-result">
          <h3>Upload Results:</h3>
          <p>Records Processed: {result.records_processed}</p>
          <p>Employees Updated: {result.employees_updated}</p>
          <p>Errors: {result.errors || 0}</p>
        </div>
      )}
    </div>
  );
}
```

## Authentication
All superadmin endpoints require admin authentication. Include the JWT token in the Authorization header:
```javascript
const getAuthHeaders = () => ({
  'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
});
```

## Error Handling
All endpoints return standard error responses:
```json
{
  "detail": "Error message",
  "status_code": 403
}
```

## Testing Credentials
- **Admin User**: `zain@following.ae`
- **Password**: `Following0925_25`

## Notes
- All complex monitoring and health check features have been removed
- Focus is on core functionality only: users, billing, content, and HRM
- The system is now much simpler and easier to maintain
- No more circuit breakers, worker monitoring, or detailed system analytics