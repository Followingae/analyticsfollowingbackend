# Stripe Sandbox Account Report
**Generated:** December 17, 2025
**Account Type:** TEST MODE
**API Key:** sk_test_51Sf0ElAubhSg1bPI... (Valid)

## Account Overview
- **Status:** Active and operational
- **Balance:** $0.00 AED
- **Total Products:** 9
- **Total Prices:** 9
- **Active Subscriptions:** 5

---

## Subscription Tier Products

### 1. Analytics Following Free
- **Product ID:** `prod_TcGIzcnY6slrhg`
- **Price ID:** `price_1Sf1loAubhSg1bPI00UODTEY`
- **Amount:** $0.00/month
- **Credits:** 125 (monthly allowance)
- **Team Members:** 1
- **Status:** Active
- **Description:** Free tier with 5 profile searches per month, basic analytics, email support

### 2. Analytics Following Standard
- **Product ID:** `prod_TcGIEBscawTakQ`
- **Price ID:** `price_1Sf1lpAubhSg1bPIiTWvBncS`
- **Amount:** $199.00/month
- **Credits:** 500 (monthly allowance)
- **Team Members:** 2
- **Status:** Active
- **Description:** Professional tier with 500 profile searches, advanced analytics, team collaboration (2 members)

### 3. Analytics Following Premium
- **Product ID:** `prod_TcGIcOvHP9dv4e`
- **Price ID:** `price_1Sf1lqAubhSg1bPIJIcqgHu1`
- **Amount:** $499.00/month
- **Credits:** 2000 (monthly allowance)
- **Team Members:** 5
- **Topup Discount:** 20%
- **Status:** Active
- **Description:** Enterprise tier with 2000 profile searches, unlimited campaigns, API access, team collaboration (5 members)

---

## Credit Topup Products

### 1. Credit Topup - Starter (1000 credits)
- **Product ID:** `prod_TcGIRJl5rPzPPx`
- **Price ID:** `price_1Sf1lrAubhSg1bPIpuPgfqvK`
- **Amount:** $50.00/month (recurring)
- **Credits:** 1000
- **Status:** Active
- **Description:** Additional 1000 credits for profile searches

### 2. Credit Topup - Professional (2500 credits)
- **Product ID:** `prod_TcGIKy7UpOjfmw`
- **Price ID:** `price_1Sf1lsAubhSg1bPIxdUE0ISQ`
- **Amount:** $125.00/month (recurring)
- **Credits:** 2500
- **Status:** Active
- **Description:** Additional 2500 credits for profile searches

### 3. Credit Topup - Enterprise (10000 credits)
- **Product ID:** `prod_TcGIEXHKanuimA`
- **Price ID:** `price_1Sf1ltAubhSg1bPIZRkuvvDp`
- **Amount:** $500.00/month (recurring)
- **Credits:** 10000
- **Status:** Active
- **Description:** Additional 10000 credits for profile searches

---

## Test/CLI Products (Can be archived)

### 1. myproduct (oldest)
- **Product ID:** `prod_TcGW2lMMX2mSXq`
- **Price ID:** `price_1Sf1zoAubhSg1bPI34qijJ08`
- **Amount:** $15.00 (one-time)
- **Description:** (created by Stripe CLI)

### 2. myproduct (middle)
- **Product ID:** `prod_TcGrwD2hjm0do9`
- **Price ID:** `price_1Sf2JsAubhSg1bPI03CQX5Mx`
- **Amount:** $15.00 (one-time)
- **Description:** (created by Stripe CLI)

### 3. myproduct (newest)
- **Product ID:** `prod_TcGscQMcTjSF1s`
- **Price ID:** `price_1Sf2KbAubhSg1bPI139ZP0k4`
- **Amount:** $15.00 (one-time)
- **Description:** (created by Stripe CLI)

---

## Active Subscriptions

### Subscription 1
- **ID:** `sub_1Sf2ySAubhSg1bPICZxiHflq`
- **Customer:** `cus_TcHXdQicJZKt8O`
- **Email:** bilal@enoc.com
- **Plan:** Standard
- **Status:** Active

### Subscription 2
- **ID:** `sub_1Sf2gTAubhSg1bPIEDcn4joR`
- **Customer:** `cus_TcHEwTPU3bZDwZ`
- **Email:** zeek@testing.com
- **Plan:** Standard
- **Status:** Active

### Subscription 3
- **ID:** `sub_1Sf2c9AubhSg1bPIkzok6l0w`
- **Customer:** `cus_TcHA3w3CNG6BnK`
- **Email:** john@acme.com
- **Plan:** Standard
- **Status:** Active

### Subscription 4
- **ID:** `sub_1Sf2E4AubhSg1bPIbvYNbzbE`
- **Customer:** `cus_TcGlhJDPn5Rqe4`
- **Email:** another@paidtest.com
- **Plan:** Standard
- **Status:** Active

### Subscription 5
- **ID:** `sub_1Sf1uHAubhSg1bPIUjkxju1N`
- **Customer:** `cus_TcGRIVIcVXoaJq`
- **Email:** paid@user.com
- **Plan:** Premium
- **Status:** Active

---

## Environment Variable Mismatches

### Current .env Configuration (OLD ACCOUNT)
```
STRIPE_FREE_PRICE_ID=price_1SGatNADTNbHc8P6fCY0pBLS        ❌ Not found in sandbox
STRIPE_STANDARD_PRICE_ID=price_1SGasqADTNbHc8P6v7VNl7sc  ❌ Not found in sandbox
STRIPE_PREMIUM_PRICE_ID=price_1SGatBADTNbHc8P6FlTcQbWI   ❌ Not found in sandbox
```

### Required .env Updates (NEW SANDBOX ACCOUNT)
```
STRIPE_FREE_PRICE_ID=price_1Sf1loAubhSg1bPI00UODTEY
STRIPE_STANDARD_PRICE_ID=price_1Sf1lpAubhSg1bPIiTWvBncS
STRIPE_PREMIUM_PRICE_ID=price_1Sf1lqAubhSg1bPIJIcqgHu1
```

---

## Recommendations

### Immediate Actions Required
1. **Update Environment Variables** - Replace old price IDs with new sandbox price IDs
2. **Update stripe_billing_service.py** - Update STRIPE_PRODUCTS dictionary with correct price IDs
3. **Test Subscription Flow** - Verify checkout sessions work with new price IDs

### Product Cleanup
1. **Archive Test Products** - The 3 "myproduct" items can be archived (created by Stripe CLI during testing)
2. **Keep Active Products** - All 6 Analytics Following products should remain active

### Credit Topup Issue
**CRITICAL:** Credit topup products are configured as **recurring** subscriptions instead of **one-time purchases**. This needs to be fixed:

- Current: Topups are recurring monthly charges
- Expected: Topups should be one-time credit purchases
- Action: Create new one-time price objects for topup products

### Subscription Analysis
- **4 Standard subscriptions** ($199/month each = $796/month revenue)
- **1 Premium subscription** ($499/month)
- **Total Monthly Revenue:** $1,295 (test mode)

---

## Integration Status

### Connected Services
- Stripe API: Connected and operational
- Environment: Test mode (sandbox)
- Currency: USD, AED

### Next Steps
1. Update .env with correct price IDs
2. Fix topup product pricing (one-time vs recurring)
3. Test complete checkout flow
4. Verify webhook integration
5. Test subscription upgrades/downgrades
6. Validate credit allocation logic

---

## Files Created/Modified
- `scripts/check_stripe_sandbox.py` - Stripe account inspection tool
- `STRIPE_SANDBOX_REPORT.md` - This comprehensive report

## Command to Re-run Check
```bash
cd c:/Users/user/analyticsfollowingbackend
python scripts/check_stripe_sandbox.py
```
