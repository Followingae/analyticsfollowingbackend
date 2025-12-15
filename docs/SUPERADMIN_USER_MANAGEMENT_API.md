# SuperAdmin User Management API Documentation

## Overview
Complete user management system for SuperAdmins to control user accounts, subscriptions, permissions, and credit topups.

## Authentication
All endpoints require SuperAdmin authentication using Bearer token:
```
Authorization: Bearer <token>
```

## Base URL
```
/api/v1/admin/superadmin
```

## Endpoints

### 1. Create User with Permissions
**POST** `/users/create`

Create a new user with specific subscription tier and permissions.

**Request Body:**
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "subscription_tier": "standard",  // free, standard, premium
  "billing_type": "offline",        // offline (admin-created) or stripe (self-enrolled)
  "custom_permissions": {            // Optional: Override specific features
    "ai_analysis": true,
    "bulk_export": false
  },
  "initial_credits": 1000,          // Optional: Initial credit topup
  "admin_notes": "VIP customer",    // Optional: Admin notes
  "send_welcome_email": true
}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "user",
  "subscription_tier": "standard",
  "billing_type": "offline",
  "status": "active",
  "created_at": "2025-01-01T00:00:00Z",
  "permissions": {
    "creator_search": {"enabled": true, "reason": "Feature available in current tier"},
    "profile_analysis": {"enabled": true, "reason": "Feature available in current tier"},
    "post_analytics": {"enabled": true, "reason": "Feature available in current tier"},
    "ai_analysis": {"enabled": true, "reason": "Feature available in current tier"},
    "bulk_export": {"enabled": true, "reason": "Feature available in current tier"},
    "campaign_management": {"enabled": true, "reason": "Feature available in current tier"},
    "team_management": {"enabled": true, "reason": "Feature available in current tier"},
    "discovery": {"enabled": true, "reason": "Feature available in current tier"},
    "api_access": {"enabled": true, "reason": "Feature available in current tier"}
  },
  "limits": {
    "source": "individual",
    "subscription_tier": "standard",
    "profiles_per_month": 500,
    "emails_per_month": 250,
    "posts_per_month": 125,
    "team_members": 2,
    "api_calls_per_month": 10000,
    "ai_analysis_enabled": true,
    "bulk_export_enabled": true,
    "campaign_management_enabled": true,
    "current_balance": 1000,
    "credits_spent_this_month": 0
  },
  "credit_balance": 1000,
  "admin_notes": "VIP customer"
}
```

### 2. Update User Subscription
**PUT** `/users/{user_id}/subscription`

Update user's subscription tier and permissions.

**Request Body:**
```json
{
  "subscription_tier": "premium",
  "billing_type": "stripe",         // Optional
  "custom_permissions": {           // Optional
    "api_access": true
  },
  "admin_notes": "Upgraded to premium"
}
```

### 3. Give Credit Topup
**POST** `/credits/topup`

Give credit topup to a user.

**Request Body:**
```json
{
  "user_id": "uuid",
  "package_type": "standard_500",   // OR use custom_credits
  "custom_credits": 2000,           // If not using package
  "reason": "Customer compensation",
  "expires_in_days": 90            // Optional expiry
}
```

**Available Package Types:**
- `starter_100`: 100 credits (30 days expiry)
- `standard_500`: 500 credits (60 days expiry)
- `premium_1000`: 1000 credits (90 days expiry)
- `enterprise_5000`: 5000 credits (180 days expiry)
- `bonus`: Custom amount (no expiry)

**Response:**
```json
{
  "success": true,
  "user_id": "uuid",
  "user_email": "user@example.com",
  "credits_added": 500,
  "new_balance": 1500,
  "package_info": {
    "package": "standard_500",
    "name": "Standard Pack",
    "description": "Standard credit package"
  },
  "reason": "Customer compensation",
  "admin": "admin@example.com"
}
```

### 4. Bulk Credit Topup
**POST** `/credits/bulk-topup`

Give credit topup to multiple users at once.

**Request Body:**
```json
{
  "user_ids": ["uuid1", "uuid2", "uuid3"],
  "package_type": "starter_100",
  "custom_credits": null,
  "reason": "Monthly bonus",
  "expires_in_days": 30
}
```

**Response:**
```json
{
  "success": 3,
  "failed": 0,
  "results": [...],
  "errors": []
}
```

### 5. List All Users
**GET** `/users`

List all users with filtering options.

**Query Parameters:**
- `subscription_tier`: Filter by tier (free, standard, premium)
- `billing_type`: Filter by billing (stripe, offline)
- `status`: Filter by status (active, inactive, suspended, pending)
- `skip`: Pagination offset (default: 0)
- `limit`: Results per page (default: 100)

**Response:**
```json
[
  {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "user",
    "subscription_tier": "standard",
    "billing_type": "offline",
    "status": "active",
    "created_at": "2025-01-01T00:00:00Z",
    "permissions": {...},
    "limits": {...},
    "credit_balance": 1000,
    "admin_notes": "VIP customer"
  }
]
```

### 6. Update User Permissions
**PUT** `/users/{user_id}/permissions`

Update specific feature permissions for a user.

**Request Body:**
```json
{
  "creator_search": true,
  "profile_analysis": true,
  "post_analytics": false,
  "ai_analysis": true,
  "bulk_export": true,
  "campaign_management": false,
  "team_management": false,
  "discovery": true,
  "api_access": false
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "uuid",
  "email": "user@example.com",
  "permissions": {
    "creator_search": {"enabled": true, "reason": "Custom override"},
    ...
  },
  "custom_overrides": {...}
}
```

### 7. Get User Permissions
**GET** `/users/{user_id}/permissions`

Get detailed permission matrix for a user.

**Response:**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "user",
  "subscription_tier": "standard",
  "billing_type": "offline",
  "permissions": {
    "creator_search": {"enabled": true, "reason": "Feature available in current tier"},
    "profile_analysis": {"enabled": true, "reason": "Feature available in current tier"},
    ...
  },
  "limits": {
    "source": "individual",
    "subscription_tier": "standard",
    "profiles_per_month": 500,
    "emails_per_month": 250,
    "posts_per_month": 125,
    ...
  },
  "is_super_admin": false
}
```

## Permission Model

### Subscription Tiers

#### Free Tier
- **Monthly Limits**: 5 profiles, 0 emails, 0 posts
- **Team Members**: 1
- **Features Disabled**: AI Analysis, Bulk Export, Campaign Management

#### Standard Tier ($199/month)
- **Monthly Limits**: 500 profiles, 250 emails, 125 posts
- **Team Members**: 2
- **API Calls**: 10,000/month
- **All Features Enabled**

#### Premium Tier ($499/month)
- **Monthly Limits**: 2000 profiles, 800 emails, 300 posts
- **Team Members**: 5
- **API Calls**: 50,000/month
- **All Features Enabled**
- **20% Topup Discount**

### Feature Permissions

| Feature | Free | Standard | Premium |
|---------|------|----------|---------|
| Creator Search | ✅ | ✅ | ✅ |
| Profile Analysis | ✅ | ✅ | ✅ |
| Post Analytics | ❌ | ✅ | ✅ |
| AI Analysis | ❌ | ✅ | ✅ |
| Bulk Export | ❌ | ✅ | ✅ |
| Campaign Management | ❌ | ✅ | ✅ |
| Team Management | ❌ | ✅ | ✅ |
| Discovery | ✅ | ✅ | ✅ |
| API Access | ❌ | ✅ | ✅ |

### Billing Types

#### Stripe Billing
- Self-enrolled users
- Manage subscription through Stripe
- Automatic renewal
- Can upgrade/downgrade via Stripe portal

#### Offline Billing
- Admin-created users
- Manual billing by SuperAdmin
- No Stripe access
- Subscription managed by SuperAdmin only

## Credit System

### Credit Costs
- Profile Analysis: 25 credits
- Email Unlock: 1 credit
- Post Analytics: 5 credits
- Campaign Analysis: 10 credits
- Bulk Export: 50 credits

### Credit Flow
1. Monthly allowance consumed first
2. Then credits from wallet
3. SuperAdmin can topup anytime
4. Credits can have expiry dates

## Error Responses

### 400 Bad Request
```json
{
  "detail": "User with this email already exists"
}
```

### 403 Forbidden
```json
{
  "detail": "Only SuperAdmin can perform this action"
}
```

### 404 Not Found
```json
{
  "detail": "User not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to create user: <error message>"
}
```

## Usage Examples

### Example 1: Create Standard Tier User
```bash
curl -X POST "https://api.example.com/api/v1/admin/superadmin/users/create" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@company.com",
    "full_name": "Client User",
    "subscription_tier": "standard",
    "billing_type": "offline",
    "initial_credits": 500,
    "admin_notes": "Enterprise client - monthly invoicing"
  }'
```

### Example 2: Bulk Credit Topup for Team
```bash
curl -X POST "https://api.example.com/api/v1/admin/superadmin/credits/bulk-topup" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": ["uuid1", "uuid2", "uuid3"],
    "custom_credits": 1000,
    "reason": "Q1 2025 bonus credits",
    "expires_in_days": 90
  }'
```

### Example 3: Override Permissions
```bash
curl -X PUT "https://api.example.com/api/v1/admin/superadmin/users/{user_id}/permissions" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_analysis": true,
    "api_access": true,
    "bulk_export": false
  }'
```