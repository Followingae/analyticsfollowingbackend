# 🎯 Active Superadmin Endpoints - January 2025

**Status:** ✅ Production Ready
**Last Updated:** January 6, 2025

---

## 📡 Currently Active Endpoints

### **Base URL:** `/api/v1/superadmin`

All endpoints require **superadmin** authentication via Bearer token.

---

## 1️⃣ **Dashboard & Analytics**

### **GET /api/v1/superadmin/dashboard**
**Comprehensive dashboard overview with real-time metrics**

**Response:**
```typescript
{
  system_health: {
    status: "healthy" | "warning",
    cpu_usage: number,
    memory_usage: number,
    disk_usage: number,
    uptime_hours: number
  },
  user_metrics: {
    total_users: number,
    active_users: number,
    new_today: number,
    new_this_week: number,
    new_this_month: number
  },
  revenue_metrics: {
    total_revenue: number,
    total_topups: number,
    monthly_revenue: number,
    active_wallets: number
  },
  activity_metrics: {
    profiles_analyzed: number,
    total_accesses: number,
    accesses_today: number
  },
  security_alerts: Array<{
    type: string,
    severity: "low" | "medium" | "high",
    message: string,
    timestamp: string
  }>,
  recent_activities: Array<{
    user: string,
    action: string,
    target: string,
    timestamp: string
  }>,
  performance_metrics: {
    avg_response_time: number,
    cache_hit_rate: number,
    error_rate: number,
    active_connections: number
  }
}
```

---

### **GET /api/v1/superadmin/analytics**
**Comprehensive business analytics**

**Query Parameters:**
- `time_range`: `7d` | `30d` | `90d` | `1y` (default: `30d`)

**Response:**
```typescript
{
  revenue_analytics: {
    daily_revenue: Array<{date: string, revenue: number}>,
    total_revenue: number,
    average_daily_revenue: number,
    total_topups: number
  },
  user_growth_analytics: {
    daily_signups: Array<{date: string, signups: number}>,
    total_new_users: number,
    role_breakdown: Record<string, number>,
    growth_rate: number
  },
  platform_usage_analytics: {
    daily_usage: Array<{
      date: string,
      accesses: number,
      active_users: number
    }>,
    total_accesses: number,
    average_daily_users: number
  },
  content_analytics: {
    total_profiles: number,
    total_posts: number,
    new_profiles_period: number
  }
}
```

---

## 2️⃣ **User Management**

### **GET /api/v1/superadmin/users**
**Get user list with filtering and pagination**

**Query Parameters:**
- `limit`: number (default: 50, max: 100)
- `offset`: number (default: 0)
- `role_filter`: string (optional)
- `status_filter`: string (optional)
- `search`: string (optional)

**Response:**
```typescript
{
  users: Array<{
    id: string,
    email: string,
    full_name: string,
    role: string,
    status: string,
    created_at: string,
    teams: Array<{name: string, role: string}>,
    credits: {
      balance: number,
      spent: number
    },
    recent_activity: number
  }>,
  total_count: number,
  pagination: {
    limit: number,
    offset: number,
    has_next: boolean
  },
  role_distribution: Record<string, number>,
  status_distribution: Record<string, number>,
  recent_registrations: Array<{
    id: string,
    email: string,
    role: string,
    created_at: string
  }>
}
```

---

### **POST /api/v1/superadmin/users/create** ⭐ NEW
**Create complete brand account with Supabase auth + team**

**Request Body:**
```typescript
{
  // REQUIRED
  email: string;                    // Unique email
  password: string;                 // Min 8 characters
  full_name: string;                // User's name

  // OPTIONAL - Profile
  company?: string;                 // Company name
  phone_number?: string;            // Contact number
  role?: string;                    // Default: "user"
  status?: string;                  // Default: "active"

  // OPTIONAL - Subscription
  subscription_tier?: "free" | "standard" | "premium";
  initial_credits?: number;         // Credits to add
  credit_package_id?: number;       // Link to package

  // OPTIONAL - Team
  create_team?: boolean;            // Create team
  team_name?: string;               // Team name
  max_team_members?: number;        // Max members
  monthly_profile_limit?: number;   // Monthly limits
  monthly_email_limit?: number;
  monthly_posts_limit?: number;
}
```

**Response:**
```typescript
{
  success: true,
  message: string,
  user: {
    id: string,
    supabase_user_id: string,
    email: string,
    full_name: string,
    company: string | null,
    phone_number: string | null,
    role: string,
    status: string,
    subscription_tier: string,
    credits: number,
    created_at: string,
    created_by: string
  },
  wallet: {
    created: boolean,
    initial_balance: number,
    package_id: number | null
  },
  team: {
    id: string,
    name: string,
    subscription_tier: string,
    max_members: number,
    limits: {
      profiles: number,
      emails: number,
      posts: number
    }
  } | null,
  login_credentials: {
    email: string,
    password: string,  // "*** (as provided)"
    note: string       // "User can login immediately"
  }
}
```

---

### **POST /api/v1/superadmin/users/{user_id}/status**
**Update user status**

**Request Body:**
```typescript
{
  new_status: "active" | "inactive" | "suspended" | "pending",
  reason?: string
}
```

**Response:**
```typescript
{
  success: true,
  message: string,
  user: {
    id: string,
    email: string,
    old_status: string,
    new_status: string,
    updated_by: string,
    reason: string | null,
    updated_at: string
  }
}
```

---

## 3️⃣ **Security & Monitoring**

### **GET /api/v1/superadmin/security/alerts**
**Get real-time security alerts**

**Query Parameters:**
- `limit`: number (default: 10, max: 50)
- `severity`: `low` | `medium` | `high` (optional)

**Response:**
```typescript
{
  alerts: Array<{
    id: string,
    type: string,
    severity: "low" | "medium" | "high",
    title: string,
    message: string,
    timestamp: string,
    affected_user?: string,
    action_required: boolean,
    suggested_actions: string[]
  }>,
  alert_counts: {
    high: number,
    medium: number,
    low: number
  },
  suspicious_activities: Array<any>,
  security_score: number,
  recommendations: string[]
}
```

---

### **GET /api/v1/superadmin/system/stats**
**System statistics and metrics**

**Response:**
```typescript
{
  system_health: {
    status: "healthy" | "warning",
    uptime_hours: number,
    cpu_usage_percent: number,
    memory_usage_percent: number,
    disk_usage_percent: number
  },
  database_metrics: {
    total_users: number,
    active_users: number,
    active_days: number
  },
  timestamp: string
}
```

---

### **GET /api/v1/superadmin/system/health**
**System health check**

**Response:**
```typescript
{
  overall_status: "healthy" | "warning",
  timestamp: string,
  checks: {
    cpu: {status: string, value: number},
    memory: {status: string, value: number},
    disk: {status: string, value: number},
    network: {status: string, bytes_sent: number, bytes_recv: number}
  },
  uptime_seconds: number,
  load_average: [number, number, number]
}
```

---

## 🚫 **DEPRECATED / UNUSED Endpoints**

The following files exist but are **NOT registered** in the application:

### ❌ **user_management_routes.py**
- `POST /api/admin/users/` - **DUPLICATE** - Use superadmin endpoint instead
- This entire file is deprecated and not included in main.py

---

## 📊 **Endpoint Summary**

| Category | Active Endpoints | Status |
|----------|-----------------|--------|
| Dashboard | 2 | ✅ Production Ready |
| User Management | 3 | ✅ Production Ready (1 NEW) |
| Security | 2 | ✅ Production Ready |
| System | 2 | ✅ Production Ready |
| **TOTAL** | **9** | **100% Functional** |

---

## 🎯 **Key Features**

1. ✅ **Complete Brand Account Creation** - Single endpoint creates Supabase auth + database + wallet + team
2. ✅ **Real-time Monitoring** - Live system health and security alerts
3. ✅ **Comprehensive Analytics** - Revenue, user growth, platform usage
4. ✅ **User Management** - List, create, update user status
5. ✅ **No Duplicates** - Clean, single source of truth for all operations

---

## 📝 **Notes for Frontend**

1. **Only use these endpoints** - Ignore any other user creation endpoints you may find
2. **user_management_routes.py is NOT active** - Don't implement it
3. **All endpoints are under /api/v1/superadmin** - Consistent prefix
4. **Bearer token required** - Must be superadmin role
5. **Complete documentation** - See SUPERADMIN_USER_CREATION_API.md for detailed examples

---

## 🔄 **Migration from Old Endpoints**

If you were using any other user creation endpoints:

**OLD (Don't use):**
- ❌ `POST /api/admin/users/` (from user_management_routes.py)
- ❌ Any other user creation endpoints

**NEW (Use this):**
- ✅ `POST /api/v1/superadmin/users/create`

**Why?**
- Creates Supabase auth account (old one didn't)
- Creates teams (old one didn't)
- More complete functionality
- Production-ready with proper error handling

---

**Last Verified:** January 6, 2025
**Backend Team Contact:** Check main.py for active routers
