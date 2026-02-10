# 📋 Frontend Testing Guide for Signup System

## 🎯 Backend Status: FULLY OPERATIONAL

All backend signup endpoints are working perfectly. Here's what the frontend team needs to test using Chrome DevTools MCP.

### ⚠️ IMPORTANT: Password Requirements
Passwords must be complex and NOT commonly used. Requirements:
- Minimum 8 characters
- Mix of uppercase, lowercase, numbers, and special characters
- Cannot be common passwords like "Password123!" or "TestPassword123!"
- Recommended format: `ComplexPass2025#Secure$` or similar unique combinations

---

## 🔧 Chrome DevTools MCP Testing Instructions

### Prerequisites
1. Open Chrome DevTools (F12)
2. Go to Network tab
3. Enable "Preserve log" checkbox
4. Clear network history before each test

---

## 📝 Test 1: FREE PLAN SIGNUP

### API Endpoint (Two Options Available)

#### Option A: Standard Registration
```
POST http://localhost:8000/api/v1/auth/register
Content-Type: application/json
```

#### Option B: Billing V3 Free Tier (Recommended)
```
POST http://localhost:8000/api/v1/billing/v3/free-tier-registration
Content-Type: application/json
```

### Test Payload
```json
{
  "email": "frontend_test_free@example.com",
  "password": "ComplexPass2025#Secure$",
  "full_name": "Frontend Test Free User",
  "company": "Test Company",
  "job_title": "Marketing Manager",
  "phone_number": "+971501234567",
  "timezone": "UTC",
  "language": "en",
  "industry": "Technology",
  "company_size": "1-10",
  "use_case": "Influencer Discovery",
  "marketing_budget": "< $10,000"
}
```

### Expected Response (201 Created)
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "frontend_test_free@example.com",
    "full_name": "Frontend Test Free User",
    "role": "free",
    "status": "active",
    "billing_type": "online_payment"
  },
  "email_confirmation_required": false,
  "message": "Registration successful...",
  "next_step": "email_confirmation_and_payment",
  "payment_setup_required": true
}
```

### Chrome DevTools Verification
1. Check Status: **201 Created**
2. Check Response Headers: `Content-Type: application/json`
3. Verify `access_token` exists
4. Verify `user.role` = "free"
5. Verify `user.status` = "active"

---

## 💳 Test 2: STANDARD PLAN ($199) SIGNUP

### Step 1: Create Checkout Session

#### API Endpoint
```
POST http://localhost:8000/api/v1/billing/v3/pre-registration-checkout
Content-Type: application/json
```

#### Test Payload
```json
{
  "email": "frontend_test_standard@example.com",
  "password": "ComplexPass2025#Secure$",
  "full_name": "Frontend Test Standard User",
  "plan": "standard",
  "company": "Test Company Standard",
  "job_title": "Marketing Director",
  "phone_number": "+971501234567",
  "timezone": "UTC",
  "language": "en",
  "industry": "E-commerce",
  "company_size": "11-50",
  "use_case": "Campaign Management",
  "marketing_budget": "$10,000 - $50,000",
  "success_url": "http://localhost:3000/success",
  "cancel_url": "http://localhost:3000/cancel"
}
```

#### Expected Response (200 OK)
```json
{
  "sessionId": "cs_test_...",
  "sessionUrl": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

### Step 2: Complete Payment (Manual)
1. Copy `sessionUrl` from response
2. Open in new browser tab
3. Use test card details:
   - **Number**: 4242 4242 4242 4242
   - **Expiry**: 04/44
   - **CVC**: 444
   - **Name**: Zain Khan
4. Complete payment

### Step 3: Verify Session Status

#### API Endpoint
```
GET http://localhost:8000/api/v1/billing/v3/verify-session/{sessionId}
```

#### Expected Response
```json
{
  "status": "payment_completed",
  "message": "Payment successful, account created",
  "can_login": true,
  "user": {
    "id": "uuid",
    "email": "frontend_test_standard@example.com",
    "billing_tier": "standard"
  }
}
```

---

## 💎 Test 3: PREMIUM PLAN ($499) SIGNUP

### Step 1: Create Checkout Session

#### API Endpoint
```
POST http://localhost:8000/api/v1/billing/v3/pre-registration-checkout
Content-Type: application/json
```

#### Test Payload
```json
{
  "email": "frontend_test_premium@example.com",
  "password": "ComplexPass2025#Secure$",
  "full_name": "Frontend Test Premium User",
  "plan": "premium",
  "company": "Test Company Premium",
  "job_title": "Marketing Director",
  "phone_number": "+971501234567",
  "timezone": "UTC",
  "language": "en",
  "industry": "E-commerce",
  "company_size": "51-200",
  "use_case": "Enterprise Analytics",
  "marketing_budget": "> $50,000",
  "success_url": "http://localhost:3000/success",
  "cancel_url": "http://localhost:3000/cancel"
}
```

#### Expected Response (200 OK)
```json
{
  "sessionId": "cs_test_...",
  "sessionUrl": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

### Payment & Verification
Same as Standard Plan - use test card 4242 4242 4242 4242

---

## 🔄 Test 4: WEBHOOK PROCESSING (Automatic)

### What Happens Automatically
1. After Stripe payment completion
2. Stripe sends webhook to: `/api/v1/billing/v3/webhook/complete-registration`
3. Backend creates user account with:
   - **Standard Plan**: 2,000 credits
   - **Premium Plan**: 5,000 credits
4. User can immediately login

### Manual Webhook Test (Optional)
```bash
# Using Stripe CLI
./stripe_new/stripe.exe trigger checkout.session.completed \
  --add checkout_session:id={sessionId} \
  --api-key sk_test_51Sf0ElAubhSg1bPIu0gnb86BfHI2iKO3P5YO9uaJZhtAEFNeQuzRcfwRjkuBba8dbInYafGmZCHqoNY5W0qbMgjg00eYoazmFC
```

---

## 🔐 Test 5: LOGIN AFTER SIGNUP

### API Endpoint
```
POST http://localhost:8000/api/v1/auth/login
Content-Type: application/json
```

### Test Payload
```json
{
  "email": "frontend_test_free@example.com",
  "password": "SecurePass#2025$Complex"
}
```

### Expected Response (200 OK)
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "frontend_test_free@example.com",
    "role": "free",
    "status": "active",
    "credits": 0,
    "subscription_tier": "free"
  }
}
```

---

## ✅ Chrome DevTools Checklist

### Network Tab Verification
- [ ] Request Method correct (POST/GET)
- [ ] Status Code correct (200/201)
- [ ] Response time < 2 seconds
- [ ] Content-Type: application/json
- [ ] CORS headers present

### Console Tab Verification
- [ ] No CORS errors
- [ ] No 4xx/5xx errors
- [ ] No JavaScript errors

### Application Tab Verification
- [ ] JWT token stored in localStorage/sessionStorage
- [ ] User data cached properly
- [ ] Session persistence works

---

## 🚨 Common Issues & Solutions

### Issue 1: CORS Error
**Solution**: Backend has CORS enabled for all origins. Check frontend is using correct URL.

### Issue 2: 400 Bad Request - Password Too Weak
**Solution**: Use a more complex password that's not commonly used. Avoid patterns like "Password123!" or "TestPassword123!". Use something unique like "ComplexPass2025#Secure$"

### Issue 3: Webhook Not Processing
**Solution**: Webhook works in DEBUG mode. For production, configure STRIPE_WEBHOOK_SECRET in .env

### Issue 4: User Can't Login After Payment
**Solution**: Wait 2-3 seconds for webhook processing, then retry login

---

## 📊 Database Verification Queries

### Check User Created
```sql
SELECT * FROM auth.users
WHERE email = 'frontend_test_free@example.com';
```

### Check Credit Wallet
```sql
SELECT * FROM credit_wallets cw
JOIN auth.users u ON cw.user_id = u.id
WHERE u.email = 'frontend_test_standard@example.com';
```

### Check Team Created
```sql
SELECT * FROM teams t
JOIN team_members tm ON t.id = tm.team_id
JOIN users u ON tm.user_id = u.id
WHERE u.email = 'frontend_test_premium@example.com';
```

---

## 🎯 Summary

### Working Endpoints
✅ `/api/v1/auth/register` - Free signup
✅ `/api/v1/billing/v3/pre-registration-checkout` - Paid plan checkout
✅ `/api/v1/billing/v3/verify-session/{sessionId}` - Session verification
✅ `/api/v1/billing/v3/webhook/complete-registration` - Webhook processing
✅ `/api/v1/auth/login` - User login

### Plan Features
- **Free**: Immediate activation, 0 credits
- **Standard ($199)**: 2,000 credits/month, 2 team members
- **Premium ($499)**: 5,000 credits/month, 5 team members

### Test Card for Stripe
- Number: `4242 4242 4242 4242`
- Expiry: `04/44`
- CVC: `444`
- Name: `Zain Khan`

---

## 📞 Support

If any issues arise during testing:
1. Check backend logs for detailed error messages
2. Verify all environment variables are set
3. Ensure database connection is active
4. Confirm Stripe API keys are valid

**Backend is 100% operational and ready for frontend integration!**