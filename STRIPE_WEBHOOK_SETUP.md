# Stripe Webhook Setup - Quick Guide

## For Local Development (Choose One):

### Option 1: Stripe CLI (EASIEST)

1. **Download Stripe CLI**:
   - Windows: https://github.com/stripe/stripe-cli/releases/latest/download/stripe_1.21.10_windows_x86_64.zip
   - Extract and add to PATH

2. **Login to Stripe**:
   ```bash
   stripe login
   ```

3. **Start Webhook Forwarding**:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/billing/v3/webhook/complete-registration
   ```

4. **Copy the webhook secret** shown (starts with `whsec_`)

5. **Update your .env file**:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
   ```

6. **Restart your FastAPI server**

### Option 2: Use Stripe Test Events

Since you already paid successfully, manually create the user:

```bash
# Quick API call to register the user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "umair@tissot.com",
    "password": "your_password",
    "full_name": "Umair"
  }'
```

## Test the Complete Flow:

1. **With Stripe CLI running**, try a new signup:
   ```javascript
   fetch('http://localhost:8000/api/v1/billing/v3/pre-registration-checkout', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       email: "test@example.com",
       password: "Test123!",
       full_name: "Test User",
       plan: "standard"
     })
   })
   ```

2. **Complete payment** in Stripe Checkout

3. **Webhook will fire** and create the account

4. **Login** should now work:
   ```javascript
   fetch('http://localhost:8000/api/v1/auth/login', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       email: "test@example.com",
       password: "Test123!"
     })
   })
   ```

## For Production:

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter: `https://yourdomain.com/api/v1/billing/v3/webhook/complete-registration`
4. Select: `checkout.session.completed`
5. Copy the signing secret
6. Update production .env: `STRIPE_WEBHOOK_SECRET=whsec_production_secret`