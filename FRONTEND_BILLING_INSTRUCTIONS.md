# Frontend Implementation - Monthly vs Annual Billing

## Overview
Your Stripe account now has both **monthly** and **annual** billing options with a 20% discount for annual plans. This guide shows how to implement the billing toggle in your frontend.

## Pricing Structure

### Available Plans
```javascript
const PRICING_PLANS = {
  free: {
    name: "Free",
    monthly: { price: 0, priceId: "price_1Sf1loAubhSg1bPI00UODTEY" },
    credits: 125,
    teamMembers: 1
  },
  standard: {
    name: "Standard",
    monthly: {
      price: 199,
      priceId: "price_1Sf1lpAubhSg1bPIiTWvBncS"
    },
    annual: {
      price: 1908, // $159/month
      priceId: "price_1SfDzAAubhSg1bPIwl0bIgs8",
      savings: 480
    },
    credits: 500,
    teamMembers: 2
  },
  premium: {
    name: "Premium",
    monthly: {
      price: 499,
      priceId: "price_1Sf1lqAubhSg1bPIJIcqgHu1"
    },
    annual: {
      price: 4788, // $399/month
      priceId: "price_1SfDzLAubhSg1bPIuSB7Tz5R",
      savings: 1200
    },
    credits: 2000,
    teamMembers: 5,
    topupDiscount: 0.20
  }
}
```

## Backend API Endpoints

### 1. Get Pricing Information
```typescript
GET /api/checkout/pricing

Response:
{
  "pricing": {
    "standard": {
      "name": "Analytics Following Professional",
      "credits": 500,
      "pricing": {
        "monthly": { "amount": 199, "interval": "month" },
        "annual": {
          "amount": 1908,
          "interval": "year",
          "savings": 480,
          "monthly_equivalent": 159
        }
      }
    }
    // ... other tiers
  }
}
```

### 2. Create Checkout Session
```typescript
POST /api/checkout/create-session

Request Body:
{
  "tier": "standard",  // or "premium"
  "billing_interval": "annual",  // or "monthly"
  "success_url": "https://yourdomain.com/success",
  "cancel_url": "https://yourdomain.com/cancel"
}

Response:
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_...",
  "tier": "standard",
  "billing_interval": "annual",
  "amount": 1908,
  "savings": 480
}
```

## React Implementation Example

### 1. Pricing Toggle Component
```jsx
import React, { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const PricingSection = () => {
  const [isAnnual, setIsAnnual] = useState(false);

  const calculatePrice = (plan) => {
    if (plan.name === 'Free') return 0;

    if (isAnnual && plan.annual) {
      return plan.annual.price / 12; // Show monthly equivalent
    }
    return plan.monthly.price;
  };

  const calculateSavings = (plan) => {
    if (isAnnual && plan.annual) {
      return plan.annual.savings;
    }
    return 0;
  };

  return (
    <div className="pricing-container">
      {/* Billing Toggle */}
      <div className="flex items-center justify-center gap-4 mb-8">
        <span className={!isAnnual ? 'font-bold' : ''}>Monthly</span>
        <Switch
          checked={isAnnual}
          onCheckedChange={setIsAnnual}
        />
        <span className={isAnnual ? 'font-bold' : ''}>
          Annual
          <Badge className="ml-2" variant="success">Save 20%</Badge>
        </span>
      </div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-3 gap-6">
        {Object.entries(PRICING_PLANS).map(([key, plan]) => (
          <PricingCard
            key={key}
            plan={plan}
            planKey={key}
            isAnnual={isAnnual}
            price={calculatePrice(plan)}
            savings={calculateSavings(plan)}
          />
        ))}
      </div>
    </div>
  );
};
```

### 2. Pricing Card Component
```jsx
const PricingCard = ({ plan, planKey, isAnnual, price, savings }) => {
  const [loading, setLoading] = useState(false);

  const handleCheckout = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/checkout/create-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify({
          tier: planKey,
          billing_interval: isAnnual ? 'annual' : 'monthly',
          success_url: `${window.location.origin}/billing/success`,
          cancel_url: `${window.location.origin}/billing/cancel`
        })
      });

      const data = await response.json();

      if (data.checkout_url) {
        // Redirect to Stripe Checkout
        window.location.href = data.checkout_url;
      }
    } catch (error) {
      console.error('Checkout error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pricing-card p-6 border rounded-lg">
      <h3 className="text-xl font-bold">{plan.name}</h3>

      {/* Price Display */}
      <div className="my-4">
        <span className="text-3xl font-bold">${price}</span>
        <span className="text-gray-500">
          /{isAnnual ? 'mo' : 'month'}
        </span>

        {isAnnual && savings > 0 && (
          <div className="text-sm text-green-600 mt-2">
            Save ${savings}/year
            {planKey === 'standard' && ' ($480 total)'}
            {planKey === 'premium' && ' ($1,200 total)'}
          </div>
        )}

        {isAnnual && (
          <div className="text-xs text-gray-500 mt-1">
            Billed ${isAnnual ? plan.annual.price : plan.monthly.price * 12} annually
          </div>
        )}
      </div>

      {/* Features */}
      <ul className="space-y-2 mb-6">
        <li>✓ {plan.credits} profile searches/month</li>
        <li>✓ {plan.teamMembers} team members</li>
        {planKey === 'premium' && (
          <li>✓ 20% discount on credit topups</li>
        )}
      </ul>

      {/* CTA Button */}
      <Button
        onClick={handleCheckout}
        disabled={loading}
        className="w-full"
        variant={planKey === 'premium' ? 'primary' : 'outline'}
      >
        {loading ? 'Processing...' : 'Choose Plan'}
      </Button>
    </div>
  );
};
```

### 3. Stripe Integration Setup
```jsx
// utils/stripe.js
import { loadStripe } from '@stripe/stripe-js';

// Initialize Stripe with your publishable key
const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ||
  'pk_test_51Sf0ElAubhSg1bPI8Qhgb1Wzc5ZqTaUo0Zaw7TsdWfqDzHtKxS2xHanxnhruuP0eyc6iEiK6O4Xz6oHEEv4UvAzk00craCvcD1'
);

export default stripePromise;
```

## TypeScript Types

```typescript
// types/billing.ts
export interface PricingPlan {
  name: string;
  credits: number;
  teamMembers: number;
  monthly: {
    price: number;
    priceId: string;
  };
  annual?: {
    price: number;
    priceId: string;
    savings: number;
  };
  topupDiscount?: number;
}

export type BillingInterval = 'monthly' | 'annual';
export type SubscriptionTier = 'free' | 'standard' | 'premium';

export interface CheckoutSessionRequest {
  tier: SubscriptionTier;
  billing_interval: BillingInterval;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutSessionResponse {
  success: boolean;
  checkout_url: string;
  session_id: string;
  tier: string;
  billing_interval: string;
  amount: number;
  savings?: number;
}
```

## UI/UX Best Practices

### 1. Visual Pricing Toggle
```jsx
// Show clear savings indicator
<div className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
  Save 20% with annual billing
</div>
```

### 2. Price Comparison Table
```jsx
const PriceComparison = ({ plan, isAnnual }) => (
  <div className="price-comparison">
    {isAnnual && plan.annual ? (
      <>
        <div className="line-through text-gray-400">
          ${plan.monthly.price * 12}/year
        </div>
        <div className="text-green-600 font-bold">
          ${plan.annual.price}/year
        </div>
        <div className="text-sm">
          You save ${plan.annual.savings}
        </div>
      </>
    ) : (
      <div>${plan.monthly.price}/month</div>
    )}
  </div>
);
```

### 3. Loading States
```jsx
const CheckoutButton = ({ loading, ...props }) => (
  <Button disabled={loading} {...props}>
    {loading ? (
      <>
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Processing...
      </>
    ) : (
      'Start Subscription'
    )}
  </Button>
);
```

## Environment Variables

Add to your frontend `.env`:
```bash
# Stripe Publishable Key (safe for frontend)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_51Sf0ElAubhSg1bPI8Qhgb1Wzc5ZqTaUo0Zaw7TsdWfqDzHtKxS2xHanxnhruuP0eyc6iEiK6O4Xz6oHEEv4UvAzk00craCvcD1

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Testing Checklist

- [ ] Monthly to annual toggle updates prices correctly
- [ ] Savings amount displays for annual plans
- [ ] Free tier doesn't show annual option
- [ ] Checkout redirects to Stripe with correct price
- [ ] Success/cancel URLs work properly
- [ ] Loading states during checkout
- [ ] Error handling for failed requests
- [ ] Mobile responsive design
- [ ] Annual billing shows monthly equivalent price

## Stripe Test Cards

For testing in sandbox mode:
- **Success**: 4242 4242 4242 4242
- **Decline**: 4000 0000 0000 0002
- **3D Secure**: 4000 0025 0000 3155

## Support & Documentation

- [Stripe Checkout Docs](https://stripe.com/docs/checkout)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- Backend API: `/api/checkout/pricing`, `/api/checkout/create-session`