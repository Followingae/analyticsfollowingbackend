# Analytics Following Backend - Complete API Endpoints Documentation

## 🎯 CRITICAL FRONTEND INTEGRATION NOTES

### ⚠️ ROUTING ISSUE DETECTED
**ISSUE**: Frontend is calling `/api/v1/api/v1/auth/login` (duplicate prefix)
**SOLUTION**: Frontend should call `/api/v1/auth/login` (single prefix)

### 🔗 Base URL Configuration
- **Production**: `https://api.analyticsfollowing.com`
- **Development**: `http://localhost:8000`

---

## 🚀 CORE CREATOR SEARCH ENDPOINTS (Primary Integration)

### **GET /api/v1/search/creator/{username}**
**PURPOSE**: Main creator search endpoint with complete 5-section analytics
**AUTHENTICATION**: Required (Bearer token)
**CREDITS**: Charges based on unlock status
**RESPONSE**: Complete creator analytics with AI insights

```typescript
// Frontend Usage
const response = await fetch(`/api/v1/search/creator/${username}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

### **GET /api/v1/instagram/profile/{username}**
**PURPOSE**: Instagram profile analysis with AI insights
**AUTHENTICATION**: Required
**CREDITS**: Uses credit gate for influencer unlock
**RESPONSE**: Detailed profile data + AI analysis

### **GET /api/v1/instagram/profile/{username}/posts**
**PURPOSE**: Get paginated posts with AI analysis
**AUTHENTICATION**: Required
**CREDITS**: Charges for post analytics
**QUERY PARAMS**: `limit`, `offset`

### **GET /api/v1/instagram/profile/{username}/ai-status**
**PURPOSE**: Check AI analysis status for a profile
**AUTHENTICATION**: Required
**RESPONSE**: AI processing completion status

---

## 🔐 AUTHENTICATION & USER MANAGEMENT

### **POST /api/v1/auth/register**
**PURPOSE**: User registration
**BODY**: `{ email, password, full_name }`
**RESPONSE**: User data + JWT tokens

### **POST /api/v1/auth/login**
**PURPOSE**: User authentication
**BODY**: `{ email, password }`
**RESPONSE**: JWT tokens + user data

### **POST /api/v1/auth/logout**
**PURPOSE**: User logout
**AUTHENTICATION**: Required

### **POST /api/v1/auth/refresh**
**PURPOSE**: Refresh JWT tokens
**BODY**: `{ refresh_token }`
**RESPONSE**: New access token

### **GET /api/v1/auth/me**
**PURPOSE**: Get current user profile
**AUTHENTICATION**: Required
**RESPONSE**: Complete user data

### **GET /api/v1/auth/dashboard**
**PURPOSE**: User dashboard with usage stats
**AUTHENTICATION**: Required
**RESPONSE**: Credits, usage, subscription info

### **GET /api/v1/auth/unlocked-profiles**
**PURPOSE**: Get user's unlocked profiles
**AUTHENTICATION**: Required
**RESPONSE**: List of unlocked Instagram profiles

### **GET /api/v1/auth/search-history**
**PURPOSE**: User's search history
**AUTHENTICATION**: Required
**RESPONSE**: Recent searches with timestamps

---

## 💳 CREDITS & BILLING SYSTEM

### **GET /api/v1/credits/balance**
**PURPOSE**: Get current credit balance
**AUTHENTICATION**: Required
**RESPONSE**: Current credits + billing cycle info

### **GET /api/v1/credits/total-plan-credits**
**PURPOSE**: Get subscription plan credit allowances
**AUTHENTICATION**: Required
**RESPONSE**: Monthly allowances by action type

### **GET /api/v1/credits/wallet/summary**
**PURPOSE**: Comprehensive wallet information
**AUTHENTICATION**: Required
**RESPONSE**: Balance, transactions, billing details

### **GET /api/v1/credits/dashboard**
**PURPOSE**: Credits dashboard for frontend
**AUTHENTICATION**: Required
**RESPONSE**: Complete credit analytics

### **GET /api/v1/credits/transactions**
**PURPOSE**: Credit transaction history
**AUTHENTICATION**: Required
**QUERY PARAMS**: `limit`, `offset`, `action_type`

### **GET /api/v1/credits/usage/monthly**
**PURPOSE**: Monthly usage summary
**AUTHENTICATION**: Required
**RESPONSE**: Usage by action type

### **GET /api/v1/credits/can-perform/{action_type}**
**PURPOSE**: Check if user can perform action
**AUTHENTICATION**: Required
**RESPONSE**: Permission + cost info

### **GET /api/v1/credits/pricing**
**PURPOSE**: Get all pricing rules
**AUTHENTICATION**: Required
**RESPONSE**: Action costs + free allowances

### **POST /api/v1/credits/top-up/estimate**
**PURPOSE**: Estimate top-up cost
**AUTHENTICATION**: Required
**BODY**: `{ credits_needed }`

---

## 👥 TEAM MANAGEMENT

### **GET /api/v1/teams/members**
**PURPOSE**: Get team members
**AUTHENTICATION**: Required
**RESPONSE**: List of team members with roles

### **POST /api/v1/teams/invite**
**PURPOSE**: Invite team member
**AUTHENTICATION**: Required (Admin only)
**BODY**: `{ email, role }`

### **GET /api/v1/teams/invitations**
**PURPOSE**: Get pending invitations
**AUTHENTICATION**: Required

### **PUT /api/v1/teams/invitations/{token}/accept**
**PURPOSE**: Accept team invitation
**AUTHENTICATION**: Required

### **DELETE /api/v1/teams/members/{user_id}**
**PURPOSE**: Remove team member
**AUTHENTICATION**: Required (Admin only)

### **GET /api/v1/teams/overview**
**PURPOSE**: Team dashboard overview
**AUTHENTICATION**: Required
**RESPONSE**: Team stats, usage, members

---

## 📋 USER LISTS & ORGANIZATION

### **GET /api/v1/lists**
**PURPOSE**: Get user's lists
**AUTHENTICATION**: Required
**RESPONSE**: List of saved creator lists

### **POST /api/v1/lists**
**PURPOSE**: Create new list
**AUTHENTICATION**: Required
**BODY**: `{ name, description, template_id? }`

### **GET /api/v1/lists/{list_id}**
**PURPOSE**: Get specific list details
**AUTHENTICATION**: Required
**RESPONSE**: List with items and metadata

### **PUT /api/v1/lists/{list_id}**
**PURPOSE**: Update list details
**AUTHENTICATION**: Required
**BODY**: `{ name?, description? }`

### **DELETE /api/v1/lists/{list_id}**
**PURPOSE**: Delete list
**AUTHENTICATION**: Required

### **POST /api/v1/lists/{list_id}/items**
**PURPOSE**: Add item to list
**AUTHENTICATION**: Required
**BODY**: `{ profile_id, notes? }`

### **DELETE /api/v1/lists/{list_id}/items/{item_id}**
**PURPOSE**: Remove item from list
**AUTHENTICATION**: Required

### **POST /api/v1/lists/{list_id}/duplicate**
**PURPOSE**: Duplicate list
**AUTHENTICATION**: Required

### **GET /api/v1/lists/templates**
**PURPOSE**: Get list templates
**RESPONSE**: Available list templates

### **GET /api/v1/lists/available-profiles**
**PURPOSE**: Get profiles available for lists
**AUTHENTICATION**: Required
**RESPONSE**: Unlocked profiles for list creation

---

## 💰 STRIPE SUBSCRIPTION MANAGEMENT

### **POST /api/v1/stripe/create-customer**
**PURPOSE**: Create Stripe customer
**AUTHENTICATION**: Required
**BODY**: User payment details

### **GET /api/v1/stripe/portal-url**
**PURPOSE**: Get customer portal URL
**AUTHENTICATION**: Required
**RESPONSE**: Stripe portal redirect URL

### **GET /api/v1/stripe/status**
**PURPOSE**: Get subscription status
**AUTHENTICATION**: Required
**RESPONSE**: Current subscription details

### **GET /api/v1/stripe/config**
**PURPOSE**: Get Stripe configuration
**RESPONSE**: Public Stripe keys

### **POST /api/v1/stripe/webhooks/stripe**
**PURPOSE**: Stripe webhook handler
**AUTHENTICATION**: Stripe signature
**BODY**: Stripe webhook payload

---

## 📄 PROPOSALS SYSTEM - REMOVED
**STATUS**: Completely removed from the system
**NOTE**: All proposal-related endpoints, database tables, and functionality have been deleted

---

## 🔧 SYSTEM HEALTH & MONITORING

### **GET /api/health**
**PURPOSE**: System health check
**RESPONSE**: Overall system status

### **GET /api/metrics**
**PURPOSE**: System performance metrics
**RESPONSE**: Performance data

### **GET /api/database/schema-check**
**PURPOSE**: Database schema validation
**RESPONSE**: Schema health status

### **GET /api/v1/status/comprehensive**
**PURPOSE**: Comprehensive system status
**AUTHENTICATION**: Required
**RESPONSE**: Detailed system diagnostics

---

## 🎯 SETTINGS & PREFERENCES

### **GET /api/v1/settings/user**
**PURPOSE**: Get user settings
**AUTHENTICATION**: Required
**RESPONSE**: User preferences

### **PUT /api/v1/settings/user**
**PURPOSE**: Update user settings
**AUTHENTICATION**: Required
**BODY**: Settings object

---

## 🔍 LEGACY & UTILITY ENDPOINTS

### **GET /**
**PURPOSE**: Root endpoint
**RESPONSE**: API information

### **GET /health**
**PURPOSE**: Basic health check
**RESPONSE**: Service status

### **GET /health/db**
**PURPOSE**: Database health check
**RESPONSE**: Database connection status

### **GET /api**
**PURPOSE**: API information
**RESPONSE**: Available API versions

### **GET /api/test**
**PURPOSE**: Test endpoint
**RESPONSE**: Test response

---

## 🚨 DEPRECATED ENDPOINTS (DO NOT USE)

The following endpoints have duplicate `/api/v1` prefixes and should NOT be used:
- `/api/v1/api/v1/simple/creator/system/stats`
- `/api/v1/api/v1/simple/creator/unlocked`

---

## 📊 FRONTEND INTEGRATION CHECKLIST

### ✅ Essential Endpoints for MVP
1. **Authentication**: `/api/v1/auth/login`, `/api/v1/auth/me`
2. **Creator Search**: `/api/v1/search/creator/{username}`
3. **Credits**: `/api/v1/credits/balance`, `/api/v1/credits/dashboard`
4. **User Lists**: `/api/v1/lists`, `/api/v1/lists/{list_id}`

### ⚠️ Error Handling
- **401**: Token expired → Redirect to login
- **403**: Insufficient credits → Show top-up options
- **429**: Rate limited → Show retry message
- **500**: Server error → Show error page

### 💡 Performance Optimization
- Use `/api/v1/search/creator/{username}` for complete analytics
- Cache user data from `/api/v1/auth/me`
- Implement progressive loading for large lists
- Use pagination for transaction history

---

## 🎆 SYSTEM STATUS
**✅ PRODUCTION READY**: All endpoints documented, tested, and ready for frontend integration with bulletproof error handling and comprehensive authentication.