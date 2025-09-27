# 📋 User Management API Guide - Complete Frontend Reference

## Overview
Comprehensive API reference for building **View User** and **Edit User** pages with clear **Superadmin vs User** access control.

---

## 🔴 **SUPERADMIN VIEW/EDIT USER PAGE**
*Access: `/admin/users/{user_id}` - Superadmin managing ANY user*

### **Basic Information**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `id` | ✅ View | ❌ | `GET /admin/users/{user_id}` |
| `email` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `full_name` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `company` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `job_title` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `phone_number` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |

### **Account Control (Superadmin Only)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `role` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `status` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `subscription_tier` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |
| `subscription_expires_at` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |

### **Credits Management (Superadmin Only)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `credits` | ✅ View | ✅ Edit | `POST /admin/credits/adjust` |
| `credits_used_this_month` | ✅ View | ❌ | `GET /admin/users/{user_id}` |
| `current_balance` | ✅ View | ✅ Edit | `POST /admin/credits/adjust` |
| `package_id` | ✅ View | ✅ Edit | `PUT /admin/users/{user_id}` |

### **Team Management (Superadmin Only)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `team_name` | ✅ View | ✅ Edit | `PUT /api/v1/teams/{team_id}` |
| `team_role` | ✅ View | ✅ Edit | `PUT /api/v1/teams/{team_id}/members/{user_id}` |
| `monthly_profile_limit` | ✅ View | ✅ Edit | `PUT /api/v1/teams/{team_id}` |
| `monthly_email_limit` | ✅ View | ✅ Edit | `PUT /api/v1/teams/{team_id}` |

### **Currency Control (Superadmin Only)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `currency_code` | ✅ View | ✅ Edit | `PUT /api/v1/currency/team/{team_id}` |
| `currency_symbol` | ✅ View | ✅ Edit | `PUT /api/v1/currency/team/{team_id}` |
| `decimal_places` | ✅ View | ✅ Edit | `PUT /api/v1/currency/team/{team_id}` |

### **Security Override (Superadmin Only)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `email_verified` | ✅ View | ✅ Edit | `POST /admin/users/{user_id}/verify-email` |
| `two_factor_enabled` | ✅ View | ✅ Edit | `POST /admin/users/{user_id}/reset-2fa` |
| `last_sign_in_at` | ✅ View | ❌ | `GET /admin/users/{user_id}` |
| `login_count` | ✅ View | ❌ | `GET /admin/users/{user_id}` |

### **Superadmin Actions**
```typescript
// Account Actions
DELETE /admin/users/{user_id}                    // Archive/delete user
POST /admin/users/bulk-update                    // Bulk operations
GET /admin/users/{user_id}/activity              // View user activity

// Credit Actions
POST /admin/credits/adjust                       // Add/remove credits
GET /api/v1/credits/transactions?user_id={id}    // View credit history

// Team Actions
POST /api/v1/teams/{team_id}/invite              // Invite to team
DELETE /api/v1/teams/{team_id}/members/{user_id} // Remove from team

// Currency Actions
PUT /api/v1/currency/team/{team_id}              // Change team currency
```

---

## 🔵 **USER SETTINGS PAGE**
*Access: `/settings` - User managing their OWN account only*

### **Personal Information**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `email` | ✅ View | ❌ | `GET /api/v1/settings/profile` |
| `full_name` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |
| `company` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |
| `job_title` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |
| `phone_number` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |
| `bio` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |
| `profile_picture_url` | ✅ View | ✅ Edit | `PUT /api/v1/settings/profile` |

### **Account Status (Read-Only for User)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `role` | ✅ View | ❌ | `GET /api/v1/settings/account` |
| `subscription_tier` | ✅ View | ❌ | `GET /api/v1/settings/account` |
| `subscription_expires_at` | ✅ View | ❌ | `GET /api/v1/settings/account` |
| `created_at` | ✅ View | ❌ | `GET /api/v1/settings/account` |

### **Credits & Usage (Read-Only for User)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `current_balance` | ✅ View | ❌ | `GET /api/v1/credits/balance` |
| `credits_used_this_month` | ✅ View | ❌ | `GET /api/v1/credits/dashboard` |
| `package_name` | ✅ View | ❌ | `GET /api/v1/credits/dashboard` |

### **Team Information (Read-Only for User)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `team_name` | ✅ View | ❌ | `GET /api/v1/teams/my-team` |
| `team_role` | ✅ View | ❌ | `GET /api/v1/teams/my-team` |
| `monthly_limits` | ✅ View | ❌ | `GET /api/v1/teams/my-team` |
| `usage_this_month` | ✅ View | ❌ | `GET /api/v1/teams/my-team/usage` |

### **Currency Settings (Read-Only for User)**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `currency_code` | ✅ View | ❌ | `GET /api/v1/currency/user/me` |
| `currency_symbol` | ✅ View | ❌ | `GET /api/v1/currency/user/me` |
| `formatted_balance` | ✅ View | ❌ | `GET /api/v1/currency/user/me` |

### **Personal Preferences**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `timezone` | ✅ View | ✅ Edit | `PUT /api/v1/settings/preferences` |
| `language` | ✅ View | ✅ Edit | `PUT /api/v1/settings/preferences` |
| `notification_preferences` | ✅ View | ✅ Edit | `PUT /api/v1/settings/preferences` |
| `profile_visibility` | ✅ View | ✅ Edit | `PUT /api/v1/settings/preferences` |
| `data_analytics_enabled` | ✅ View | ✅ Edit | `PUT /api/v1/settings/preferences` |

### **Security Settings**
| Field | View | Edit | **API Endpoint** |
|-------|------|------|------------------|
| `two_factor_enabled` | ✅ View | ✅ Edit | `POST/DELETE /api/v1/settings/2fa` |
| `email_verified` | ✅ View | ❌ | `GET /api/v1/settings/security` |
| `last_sign_in_at` | ✅ View | ❌ | `GET /api/v1/settings/security` |

### **User Actions**
```typescript
// Profile Actions
PUT /api/v1/settings/profile                    // Update personal info
POST /api/v1/settings/upload-avatar             // Upload profile picture
PUT /api/v1/settings/preferences                // Update preferences

// Security Actions
POST /api/v1/settings/change-password           // Change password
POST /api/v1/settings/2fa/enable                // Enable 2FA
DELETE /api/v1/settings/2fa/disable             // Disable 2FA

// Data Actions
GET /api/v1/credits/transactions                // View own transactions
GET /api/v1/settings/export-data               // Export own data
```

---

## 🔐 **Key Differences**

### **Superadmin Can:**
- ✅ **View/Edit ANY user's account**
- ✅ **Change roles, subscriptions, credits**
- ✅ **Manage team settings and currency**
- ✅ **Override security settings**
- ✅ **Bulk operations**
- ✅ **Access admin endpoints (`/admin/*`)**

### **User Can Only:**
- ✅ **View/Edit their OWN profile**
- ✅ **Change personal preferences**
- ✅ **View subscription/credit status (read-only)**
- ✅ **Manage 2FA and security**
- ✅ **Access user endpoints (`/api/v1/settings/*`)**
- ❌ **Cannot change role, credits, or team settings**

### **API Path Patterns**
- **Superadmin:** `/admin/users/{user_id}` (any user)
- **User:** `/api/v1/settings/*` (own account only)

---

## 📊 **Sample API Responses**

### **Superadmin User Details**
```typescript
GET /admin/users/{user_id}
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "premium",
    "subscription_tier": "standard",
    "status": "active",
    "credits": 5000,
    "team": {
      "name": "Company Team",
      "role": "member",
      "currency": {
        "code": "USD",
        "symbol": "$"
      }
    }
  }
}
```

### **User Settings**
```typescript
GET /api/v1/settings/profile
{
  "success": true,
  "data": {
    "full_name": "John Doe",
    "company": "Acme Corp",
    "timezone": "UTC",
    "preferences": {
      "notifications": true,
      "analytics": true
    }
  }
}
```

## 🔧 **Authentication Headers**
```typescript
headers: {
  'Authorization': 'Bearer <jwt_token>',
  'Content-Type': 'application/json'
}
```

**Permission Levels:**
- **Superadmin**: All endpoints + currency/credit management
- **Admin**: User management except role changes
- **User**: Own data via `/api/v1/settings/*` endpoints only

---

## 📋 **Implementation Notes**

### **Step 3 Removal Notice**
⚠️ **Important**: Step 3 (Content Planning) has been removed from the proposal creation flow at `http://localhost:3000/admin/proposals/create` as deliverables are now specified per influencer in subsequent steps.

### **Currency System**
✅ **Complete**: Industry-standard currency-per-team system implemented with superadmin management capabilities.

### **Company Name Requirement**
✅ **Required**: Company name is mandatory for all signups and user profiles.

This guide provides the frontend team with complete API reference for building both superadmin user management and user self-service settings interfaces.