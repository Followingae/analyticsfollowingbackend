# Complete Frontend Integration Guide - SuperAdmin User Management System

## 🎯 **100% Backend Complete - All APIs LIVE & Operational**

All SuperAdmin user management APIs are **fully implemented and operational**. This guide provides complete integration requirements for frontend implementation.

---

## 🔐 **Authentication Requirements**

### Current User Context
```typescript
interface CurrentUser {
  id: string;
  email: string;
  role: 'user' | 'super_admin';
  subscription_tier: 'free' | 'standard' | 'premium';
  billing_type: 'stripe' | 'offline';
}
```

### SuperAdmin Protection
**All SuperAdmin routes require:**
- Bearer token authentication
- `role: 'super_admin'` verification
- Frontend must check `currentUser.role === 'super_admin'` before rendering SuperAdmin interfaces

---

## 📊 **Complete API Reference**

### 1. **Create New User**
**Endpoint:** `POST /api/v1/admin/superadmin/users/create`

**Request:**
```typescript
interface CreateUserRequest {
  email: string;
  full_name: string;
  subscription_tier: 'free' | 'standard' | 'premium';
  billing_type: 'stripe' | 'offline';
  custom_permissions?: {
    [featureName: string]: boolean;
  };
  initial_credits?: number; // 0-100000
  admin_notes?: string;
  send_welcome_email?: boolean;
}
```

**Response:**
```typescript
interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: 'user' | 'super_admin';
  subscription_tier: 'free' | 'standard' | 'premium';
  billing_type: 'stripe' | 'offline';
  status: 'active' | 'inactive' | 'suspended' | 'pending';
  created_at: string;
  permissions: {
    [featureName: string]: {
      enabled: boolean;
      reason: string;
    };
  };
  limits: {
    source: 'individual' | 'team';
    subscription_tier: string;
    profiles_per_month: number;
    emails_per_month: number;
    posts_per_month: number;
    team_members: number;
    api_calls_per_month: number;
    bulk_export_enabled: boolean;
    campaign_management_enabled: boolean;
    lists_enabled: boolean;
    current_balance: number;
    credits_spent_this_month: number;
  };
  credit_balance: number;
  admin_notes?: string;
}
```

### 2. **Update User Subscription**
**Endpoint:** `PUT /api/v1/admin/superadmin/users/{user_id}/subscription`

**Request:**
```typescript
interface UpdateSubscriptionRequest {
  subscription_tier: 'free' | 'standard' | 'premium';
  billing_type?: 'stripe' | 'offline';
  custom_permissions?: {
    [featureName: string]: boolean;
  };
  admin_notes?: string;
}
```

**Response:** Same as `UserResponse`

### 3. **Give Credit Topup**
**Endpoint:** `POST /api/v1/admin/superadmin/credits/topup`

**Request:**
```typescript
interface CreditTopupRequest {
  user_id: string;
  package_type?: 'starter_100' | 'standard_500' | 'premium_1000' | 'enterprise_5000' | 'bonus';
  custom_credits?: number; // If not using package
  reason: string;
  expires_in_days?: number; // 1-365
}
```

**Response:**
```typescript
interface CreditTopupResponse {
  success: true;
  user_id: string;
  user_email: string;
  credits_added: number;
  new_balance: number;
  package_info: {
    package?: string;
    name: string;
    description: string;
  };
  reason: string;
  admin: string; // SuperAdmin email
}
```

**Available Packages:**
- `starter_100`: 100 credits (30 days)
- `standard_500`: 500 credits (60 days)
- `premium_1000`: 1000 credits (90 days)
- `enterprise_5000`: 5000 credits (180 days)
- `bonus`: Custom amount (no expiry)

### 4. **Bulk Credit Topup**
**Endpoint:** `POST /api/v1/admin/superadmin/credits/bulk-topup`

**Request:**
```typescript
interface BulkCreditTopupRequest {
  user_ids: string[];
  package_type?: string;
  custom_credits?: number;
  reason: string;
  expires_in_days?: number;
}
```

**Response:**
```typescript
interface BulkTopupResponse {
  success: number; // Count of successful topups
  failed: number;  // Count of failed topups
  results: CreditTopupResponse[];
  errors: Array<{
    user_id: string;
    error: string;
  }>;
}
```

### 5. **List All Users**
**Endpoint:** `GET /api/v1/admin/superadmin/users`

**Query Parameters:**
```typescript
interface UserListParams {
  subscription_tier?: 'free' | 'standard' | 'premium';
  billing_type?: 'stripe' | 'offline';
  status?: 'active' | 'inactive' | 'suspended' | 'pending';
  skip?: number; // Pagination offset (default: 0)
  limit?: number; // Results per page (default: 100, max: 100)
}
```

**Response:** `UserResponse[]`

### 6. **Update User Permissions**
**Endpoint:** `PUT /api/v1/admin/superadmin/users/{user_id}/permissions`

**Request:**
```typescript
interface UpdatePermissionsRequest {
  [featureName: string]: boolean;
}

// Available features:
interface FeaturePermissions {
  creator_search: boolean;      // Search Instagram profiles (AI built-in)
  post_analytics: boolean;      // Individual post analysis
  email_unlock: boolean;        // Unlock creator emails
  bulk_export: boolean;         // Export data to CSV/Excel
  campaign_management: boolean; // Create campaigns
  lists_management: boolean;    // Manage creator lists
  team_management: boolean;     // Add team members
  discovery: boolean;           // Browse database profiles
  api_access: boolean;         // Programmatic access
}
```

**Response:**
```typescript
interface UpdatePermissionsResponse {
  success: true;
  user_id: string;
  email: string;
  permissions: {
    [featureName: string]: {
      enabled: boolean;
      reason: string;
    };
  };
  custom_overrides: FeaturePermissions;
}
```

### 7. **Get User Permissions**
**Endpoint:** `GET /api/v1/admin/superadmin/users/{user_id}/permissions`

**Response:**
```typescript
interface UserPermissionsResponse {
  user_id: string;
  email: string;
  role: string;
  subscription_tier: string;
  billing_type: string;
  permissions: {
    [featureName: string]: {
      enabled: boolean;
      reason: string;
    };
  };
  limits: {
    source: 'individual' | 'team';
    subscription_tier: string;
    profiles_per_month: number;
    emails_per_month: number;
    posts_per_month: number;
    team_members: number;
    api_calls_per_month: number;
    bulk_export_enabled: boolean;
    campaign_management_enabled: boolean;
    lists_enabled: boolean;
    current_balance: number;
    credits_spent_this_month: number;
  };
  is_super_admin: boolean;
}
```

---

## 🎨 **Frontend Implementation Requirements**

### 1. **SuperAdmin Dashboard Page**
**Route:** `/admin/dashboard` (protect with SuperAdmin role check)

**Required Elements:**
- User statistics overview
- Quick actions section (Create User, Bulk Topup)
- Recent activity feed
- System health indicators

**API Calls:**
- `GET /api/v1/admin/superadmin/users?limit=10` (recent users)
- User count aggregations from list API

### 2. **User Management Page**
**Route:** `/admin/users`

**Required Elements:**
- Users data table with pagination
- Filter controls (tier, billing type, status)
- Search functionality
- Bulk selection with actions
- Create User button (opens modal/form)

**Data Table Columns:**
- Email
- Full Name
- Subscription Tier (with badge styling)
- Billing Type (with badge: "Self-Service" for stripe, "Admin-Managed" for offline)
- Status (with status indicator)
- Credit Balance
- Created Date
- Actions dropdown (Edit, Permissions, Topup)

**API Calls:**
- `GET /api/v1/admin/superadmin/users` with pagination and filters

### 3. **Create User Form/Modal**
**Required Form Fields:**
- Email (required, validation)
- Full Name (required)
- Subscription Tier (dropdown: Free/Standard/Premium)
- Billing Type (radio: Self-Service Stripe / Admin-Managed Offline)
- Initial Credits (number input, 0-100000)
- Admin Notes (textarea)
- Send Welcome Email (checkbox, default true)

**Advanced Permissions Section (collapsible):**
- Feature toggles for each permission
- Clear labels explaining each feature

**API Call:**
- `POST /api/v1/admin/superadmin/users/create`

### 4. **Edit User Modal/Page**
**Route:** `/admin/users/{userId}/edit`

**Required Sections:**

**A. Subscription Management:**
- Current tier display with upgrade/downgrade options
- Billing type change (with warnings)
- Admin notes field

**B. Permission Overrides:**
- Toggle switches for each feature
- Clear indication of tier-based vs custom permissions
- Warning messages for permission changes

**API Calls:**
- `GET /api/v1/admin/superadmin/users/{userId}/permissions`
- `PUT /api/v1/admin/superadmin/users/{userId}/subscription`
- `PUT /api/v1/admin/superadmin/users/{userId}/permissions`

### 5. **Credit Management Modal/Page**

**Single User Topup:**
- User selector (if accessed from dashboard)
- User info display (email, current balance)
- Package selection (radio buttons with descriptions)
- Custom credits input (alternative to packages)
- Reason field (required)
- Expiry setting (optional)

**Bulk Topup:**
- Multiple user selection interface
- Same package/credits options
- Bulk reason field
- Progress indicator during processing
- Results summary (success/failed counts)

**API Calls:**
- `POST /api/v1/admin/superadmin/credits/topup`
- `POST /api/v1/admin/superadmin/credits/bulk-topup`

### 6. **User Permissions Detail View**
**Route:** `/admin/users/{userId}/permissions`

**Required Elements:**
- User info header (email, tier, billing type)
- Current subscription limits display
- Feature permissions grid with status indicators
- Permission source (tier-based vs custom override)
- Credit usage and balance information

**API Call:**
- `GET /api/v1/admin/superadmin/users/{userId}/permissions`

---

## 📱 **Component Requirements**

### Data Components Needed:

**1. UserCard Component**
- Display user summary info
- Quick actions (edit, topup)
- Status indicators

**2. PermissionMatrix Component**
- Grid layout of all features
- Toggle switches with descriptions
- Visual indication of permission source

**3. CreditTopup Component**
- Package selection interface
- Custom amount input
- Expiry date picker
- Validation and submission

**4. BulkActions Component**
- Multi-select interface
- Bulk action buttons
- Progress tracking
- Results display

**5. SubscriptionBadge Component**
- Visual tier indicators
- Billing type badges
- Status indicators

---

## 🔧 **State Management Requirements**

### Required State:
```typescript
interface SuperAdminState {
  users: {
    list: UserResponse[];
    loading: boolean;
    total: number;
    filters: UserListParams;
  };
  currentEditUser: UserResponse | null;
  bulkSelection: string[]; // user IDs
  creditTopup: {
    loading: boolean;
    selectedUsers: string[];
  };
}
```

### Required Actions:
- `loadUsers(filters: UserListParams)`
- `createUser(userData: CreateUserRequest)`
- `updateUserSubscription(userId: string, data: UpdateSubscriptionRequest)`
- `updateUserPermissions(userId: string, permissions: FeaturePermissions)`
- `giveCreditTopup(data: CreditTopupRequest)`
- `bulkCreditTopup(data: BulkCreditTopupRequest)`
- `selectUser(userId: string)`
- `clearSelection()`

---

## 🚦 **Error Handling**

### Expected Error Responses:
```typescript
interface APIError {
  detail: string;
  status_code: number;
}

// Common errors:
// 400: "User with this email already exists"
// 403: "Only SuperAdmin can perform this action"
// 404: "User not found"
// 500: "Failed to create user: {error}"
```

### Error Handling Requirements:
- Form validation before API calls
- Loading states during API operations
- Clear error messages for users
- Retry mechanisms for failed operations
- Success confirmations for completed actions

---

## 🔍 **Testing Requirements**

### Test Scenarios:
1. **Create User Flow:**
   - All subscription tiers
   - Both billing types
   - With and without initial credits
   - Permission overrides

2. **Credit Topup:**
   - Single user with packages
   - Single user with custom amount
   - Bulk operations
   - Error handling (insufficient permissions, user not found)

3. **Permission Management:**
   - Tier-based permissions vs overrides
   - Permission updates and validation
   - Subscription tier changes

4. **List and Filter:**
   - Pagination functionality
   - Filter combinations
   - Search and sorting

---

## ✅ **Implementation Checklist**

### Phase 1: Core Functionality
- [ ] SuperAdmin route protection
- [ ] User list with pagination and filters
- [ ] Create user form
- [ ] Basic user editing

### Phase 2: Advanced Features
- [ ] Permission management interface
- [ ] Credit topup (single and bulk)
- [ ] Subscription management
- [ ] Advanced filtering and search

### Phase 3: Polish
- [ ] Loading states and error handling
- [ ] Success confirmations and notifications
- [ ] Responsive design
- [ ] Performance optimization

---

## 🎯 **Result: Complete SuperAdmin Control**

Frontend will provide SuperAdmins with:
- ✅ **Complete user lifecycle management** (create, edit, manage)
- ✅ **Flexible subscription control** (any tier, billing type changes)
- ✅ **Granular permission management** (feature-level overrides)
- ✅ **Comprehensive credit system** (individual and bulk topups)
- ✅ **Advanced user filtering** (tier, billing, status)
- ✅ **Real-time credit and usage tracking**

**All backend APIs are LIVE and ready for frontend integration!** 🚀