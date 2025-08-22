# FRONTEND API REFERENCE - CORRECT ENDPOINTS

## 🚨 CRITICAL: Frontend is calling WRONG URLs!

### ❌ Current Frontend Calls (WRONG):
```
GET /api/v1/balance         -> 404 NOT FOUND
GET /api/v1/dashboard       -> 404 NOT FOUND  
```

### ✅ Correct API Endpoints:

## 🏠 **DASHBOARD ENDPOINTS**
```
GET /api/v1/auth/dashboard     -> User dashboard stats (working ✅)
GET /api/v1/credits/dashboard  -> Credit system dashboard
```

## 💳 **CREDIT ENDPOINTS**
```
GET /api/v1/credits/balance           -> Current credit balance
GET /api/v1/credits/wallet/summary    -> Detailed wallet info
GET /api/v1/credits/transactions      -> Transaction history
GET /api/v1/credits/usage/monthly     -> Monthly usage stats
GET /api/v1/credits/allowances        -> Free allowances status
```

## 🔐 **AUTHENTICATION ENDPOINTS**
```
POST /api/v1/login                    -> User login
POST /api/v1/logout                   -> User logout
POST /api/v1/refresh                  -> Refresh JWT token
GET  /api/v1/me                       -> Current user info
```

## 👤 **USER PROFILE ENDPOINTS**
```
GET /api/v1/profile                   -> User profile settings
PUT /api/v1/profile                   -> Update profile
GET /api/v1/preferences               -> User preferences
PUT /api/v1/preferences               -> Update preferences
```

## 📱 **INSTAGRAM ANALYSIS ENDPOINTS**
```
GET /api/v1/instagram/profile/{username}           -> Full profile analysis
GET /api/v1/instagram/profile/{username}/posts     -> Profile posts
GET /api/v1/instagram/profile/{username}/analytics -> Profile analytics
GET /api/v1/search/suggestions/{partial_username}  -> Search suggestions
```

## 🎯 **DISCOVERY & SEARCH ENDPOINTS**
```
POST /api/v1/search                               -> Start discovery search
GET  /api/v1/page/{session_id}/{page_number}      -> Get search results
GET  /api/v1/filters                              -> Available filters
```

## 📊 **ENGAGEMENT ENDPOINTS**
```
GET  /api/v1/engagement/stats                     -> Engagement statistics
POST /api/v1/engagement/calculate/profile/{username} -> Calculate engagement
```

## 🏥 **HEALTH & STATUS ENDPOINTS**
```
GET /api/v1/health                                -> Service health
GET /api/v1/status                                -> System status
GET /api/health                                   -> Main health check
```

---

## 📋 **AUTHENTICATION HEADERS**

All endpoints require JWT token:
```
Authorization: Bearer <your_jwt_token>
```

## 📊 **RESPONSE FORMATS**

### Success Response:
```json
{
  "status": "success", 
  "data": { ... },
  "message": "Optional message"
}
```

### Error Response:
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## 🎯 **PRIORITY FIXES FOR FRONTEND**

1. **Change** `/api/v1/balance` → `/api/v1/credits/balance`
2. **Change** `/api/v1/dashboard` → `/api/v1/auth/dashboard` 
3. **Add** JWT token to all requests
4. **Use** `/api/v1/credits/dashboard` for credit-specific dashboard

## 🔄 **COMMON USER FLOW ENDPOINTS**

### Login Flow:
1. `POST /api/v1/login` - Login user
2. `GET /api/v1/auth/dashboard` - Get dashboard
3. `GET /api/v1/credits/balance` - Get credit balance
4. `GET /api/v1/me` - Get user profile

### Profile Search Flow:
1. `GET /api/v1/search/suggestions/{partial}` - Search suggestions
2. `GET /api/v1/instagram/profile/{username}` - Get full analysis
3. `GET /api/v1/credits/balance` - Check remaining credits

### Dashboard Refresh:
1. `GET /api/v1/auth/dashboard` - User stats
2. `GET /api/v1/credits/balance` - Credit balance
3. `GET /api/v1/credits/transactions` - Recent transactions

---

**⚡ Quick Fix: Update frontend to use `/api/v1/credits/balance` instead of `/api/v1/balance`**