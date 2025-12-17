# Stripe Frontend Integration Guide

## Complete Signup → Checkout Flow

### 1. Signup Flow with Billing Type Selection

```typescript
// SignupForm.tsx
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export function SignupForm() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    billing_type: 'online_payment', // or 'admin_managed'
    role: 'free' // free, standard, or premium
  });
  const router = useRouter();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      // 1. Register the user
      const response = await fetch('http://localhost:8000/api/v1/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) throw new Error('Signup failed');

      const data = await response.json();

      // 2. IMPORTANT: Store the access token immediately
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_data', JSON.stringify(data.user));

      // 3. Route based on billing type
      if (formData.billing_type === 'online_payment' && formData.role !== 'free') {
        // Redirect to checkout for paid plans
        router.push(`/checkout?plan=${formData.role}`);
      } else if (formData.billing_type === 'admin_managed') {
        // Show pending approval message
        router.push('/pending-approval');
      } else {
        // Free plan - go straight to dashboard
        router.push('/dashboard');
      }

    } catch (error) {
      console.error('Signup error:', error);
    }
  };

  return (
    <form onSubmit={handleSignup}>
      {/* Email, Password, Name fields */}

      {/* Billing Type Toggle */}
      <div className="flex gap-4 my-4">
        <button
          type="button"
          className={`px-4 py-2 ${formData.billing_type === 'online_payment' ? 'bg-blue-500' : 'bg-gray-300'}`}
          onClick={() => setFormData({...formData, billing_type: 'online_payment'})}
        >
          Pay Online (Instant Activation)
        </button>
        <button
          type="button"
          className={`px-4 py-2 ${formData.billing_type === 'admin_managed' ? 'bg-blue-500' : 'bg-gray-300'}`}
          onClick={() => setFormData({...formData, billing_type: 'admin_managed'})}
        >
          Admin Managed Billing
        </button>
      </div>

      {/* Plan Selection (only for online payment) */}
      {formData.billing_type === 'online_payment' && (
        <select
          value={formData.role}
          onChange={(e) => setFormData({...formData, role: e.target.value})}
        >
          <option value="free">Free - $0/month</option>
          <option value="standard">Standard - $199/month</option>
          <option value="premium">Premium - $499/month</option>
        </select>
      )}

      <button type="submit">Sign Up</button>
    </form>
  );
}
```

### 2. Checkout Page (After Signup)

```typescript
// app/checkout/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { loadStripe } from '@stripe/stripe-js';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function CheckoutPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const plan = searchParams.get('plan') || 'standard';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initializeCheckout = async () => {
      try {
        // 1. Get the access token that was stored during signup
        const accessToken = localStorage.getItem('access_token');

        if (!accessToken) {
          setError('No authentication token found. Please sign up first.');
          router.push('/signup');
          return;
        }

        // 2. Create checkout session with proper authentication
        const response = await fetch('http://localhost:8000/api/v1/billing/create-checkout-session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}` // CRITICAL: Include the token!
          },
          body: JSON.stringify({
            price_id: getPriceId(plan),
            mode: 'subscription',
            success_url: `${window.location.origin}/dashboard?subscription=success`,
            cancel_url: `${window.location.origin}/pricing?cancelled=true`
          })
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to create checkout session');
        }

        const { sessionId } = await response.json();

        // 3. Redirect to Stripe Checkout
        const stripe = await stripePromise;
        if (!stripe) throw new Error('Stripe failed to load');

        const { error: stripeError } = await stripe.redirectToCheckout({ sessionId });
        if (stripeError) {
          throw new Error(stripeError.message);
        }

      } catch (err) {
        console.error('Checkout error:', err);
        setError(err.message || 'Failed to initialize checkout');
        setLoading(false);
      }
    };

    initializeCheckout();
  }, [plan, router]);

  const getPriceId = (planType: string): string => {
    // TEST MODE Price IDs (create these in your Stripe test dashboard)
    const prices = {
      free: 'price_test_free', // Won't actually charge
      standard: 'price_test_standard', // Replace with your test price ID
      premium: 'price_test_premium'    // Replace with your test price ID
    };
    return prices[planType] || prices.standard;
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg">
          <h2 className="text-red-800 font-bold mb-2">Checkout Error</h2>
          <p className="text-red-600">{error}</p>
          <button
            onClick={() => router.push('/pricing')}
            className="mt-4 bg-red-600 text-white px-4 py-2 rounded"
          >
            Back to Pricing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4">Redirecting to Stripe Checkout...</p>
        <p className="text-sm text-gray-500 mt-2">Plan: {plan}</p>
      </div>
    </div>
  );
}
```

### 3. Customer Portal (Manage Subscription)

```typescript
// components/ManageSubscription.tsx
import { useState } from 'react';

export function ManageSubscriptionButton() {
  const [loading, setLoading] = useState(false);

  const openCustomerPortal = async () => {
    setLoading(true);

    try {
      const accessToken = localStorage.getItem('access_token');

      if (!accessToken) {
        window.location.href = '/login';
        return;
      }

      const response = await fetch('http://localhost:8000/api/v1/billing/portal-session', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      if (!response.ok) throw new Error('Failed to create portal session');

      const { url } = await response.json();
      window.location.href = url; // Redirect to Stripe Customer Portal

    } catch (error) {
      console.error('Portal error:', error);
      alert('Failed to open billing portal');
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={openCustomerPortal}
      disabled={loading}
      className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
    >
      {loading ? 'Loading...' : 'Manage Subscription'}
    </button>
  );
}
```

### 4. Authentication Helper

```typescript
// utils/auth.ts
export const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    'Authorization': token ? `Bearer ${token}` : ''
  };
};

export const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('access_token');
};
```

## Key Points for Frontend Implementation

### 1. **Authentication Flow**
- After signup, immediately store `access_token` from response
- Include `Bearer ${access_token}` in ALL subsequent API calls
- The 403 error happens when token is missing

### 2. **Billing Type Handling**
- `online_payment`: Requires Stripe checkout
- `admin_managed`: Goes to pending approval
- Free plan with `online_payment`: No checkout needed

### 3. **Test Mode**
- Using test keys (pk_test_... and sk_test_...)
- Use test card: `4242 4242 4242 4242`
- Any future date, any 3-digit CVC

### 4. **API Endpoints**
```
POST /api/v1/auth/register
- Returns: { access_token, user: {...} }

POST /api/v1/billing/create-checkout-session
- Headers: Authorization: Bearer <token>
- Body: { price_id, mode, success_url, cancel_url }
- Returns: { sessionId, sessionUrl }

POST /api/v1/billing/portal-session
- Headers: Authorization: Bearer <token>
- Returns: { url }

GET /api/v1/billing/subscription-status
- Headers: Authorization: Bearer <token>
- Returns: { status, current_plan, ... }
```

## Troubleshooting

### "403 Forbidden" on checkout
- Check if access_token is stored in localStorage
- Verify Authorization header is being sent
- Check if user billing_type is 'online_payment'

### "Failed to create checkout session"
- Ensure Stripe test keys are configured
- Check if price IDs exist in Stripe test dashboard
- Verify backend is running on correct port

### Testing Flow
1. Sign up with billing_type: 'online_payment'
2. Select 'standard' or 'premium' plan
3. Should redirect to /checkout with token
4. Checkout page creates Stripe session
5. Redirects to Stripe hosted checkout
6. Use test card 4242 4242 4242 4242
7. Returns to success_url after payment