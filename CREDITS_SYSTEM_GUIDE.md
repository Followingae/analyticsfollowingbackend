# Credits System - Complete Integration Guide

## System Overview

We've implemented a comprehensive credits-based monetization system for the Instagram analytics platform with a **simplified 3-action pricing model** that maximizes user experience while enabling flexible revenue generation.

## Simplified Pricing Model (3 Actions Only)

### 1. Discovery - **1 Credit** (Super Affordable)
- **Purpose**: Browsing profiles and discovery pages
- **Strategy**: Encourage exploration and platform engagement  
- **Free Allowance**: **50 uses per month**
- **Use Case**: General browsing, finding influencers, platform exploration
- **Business Goal**: Drive user engagement and platform stickiness

### 2. Profile Analysis - **25 Credits** (All-Inclusive Package)
- **Purpose**: Complete comprehensive Instagram profile analysis
- **What's Included in ONE payment**:
  - ✅ **AI-powered content insights** and sentiment analysis
  - ✅ **Detailed engagement analytics** and performance metrics  
  - ✅ **Influencer unlock** (access to contact information)
  - ✅ **Full posts viewing** and analysis within the profile
  - ✅ **Audience demographics** and growth trends
- **Free Allowance**: **2 complete analyses per month**
- **Use Case**: Deep dive into influencer profiles for campaign planning
- **Business Goal**: High-value, comprehensive service in one transaction

### 3. Posts Analytics - **10 Credits**  
- **Purpose**: Campaign-specific individual post URL analysis
- **What's Included**: Detailed metrics for specific posts added to campaigns
- **Important**: Posts within profiles (from Profile Analysis) are viewable for free
- **Free Allowance**: **5 post analyses per month**
- **Use Case**: Analyzing specific campaign posts or competitor content
- **Business Goal**: Campaign management and competitive analysis

## Credit Package Tiers

| Package | Credits/Month | Target Audience | Equivalent Usage |
|---------|--------------|----------------|------------------|
| **Basic** | 100 credits | Individual users, small businesses | ~4 profile analyses OR ~10 posts analytics |
| **Professional** | 500 credits | Growing agencies, marketing teams | ~20 profile analyses OR ~50 posts analytics |
| **Enterprise** | 2000 credits | Large agencies, enterprises | ~80 profile analyses OR ~200 posts analytics |

## Monthly Free Allowances

| Action Type | Credit Cost | Free Monthly Allowance | Reset Date |
|------------|-------------|----------------------|------------|
| **Discovery** | 1 | **50 uses** | 1st of each month |
| **Profile Analysis** | 25 | **2 uses** | 1st of each month |
| **Posts Analytics** | 10 | **5 uses** | 1st of each month |

## API Endpoints Available

### Credit Balance & Wallet Management
```
GET /api/v1/api/credits/balance                 # Current credit balance
GET /api/v1/api/credits/wallet/summary          # Comprehensive wallet info  
GET /api/v1/api/credits/dashboard               # Complete dashboard data
POST /api/v1/api/credits/wallet/create          # Create wallet if missing
```

### Transaction History & Analytics
```
GET /api/v1/api/credits/transactions            # Paginated transaction history
GET /api/v1/api/credits/transactions/search     # Advanced transaction search
GET /api/v1/api/credits/usage/monthly           # Monthly usage summary
GET /api/v1/api/credits/analytics/spending      # Spending analytics
```

### Action Permissions & Pricing  
```
GET /api/v1/api/credits/can-perform/{action_type}   # Check if action is allowed
GET /api/v1/api/credits/pricing                     # All pricing rules
GET /api/v1/api/credits/pricing/{action_type}       # Specific action pricing
POST /api/v1/api/credits/pricing/calculate          # Bulk pricing calculation
```

### Allowances & System Info
```
GET /api/v1/api/credits/allowances              # Free allowance status
GET /api/v1/api/credits/system/stats            # System statistics
```

### Future Payment Integration (Ready for Stripe)
```
POST /api/v1/api/credits/top-up/estimate        # Estimate credit purchase cost
GET /api/v1/api/credits/top-up/history          # Credit purchase history
```

## Protected Instagram Features

### Credit-Gated Endpoints:
- **Discovery** - Discovery page/profile browsing (**1 credit** - very minimal)
- **Profile Analysis** - `/api/v1/profile/{username}` (**25 credits** - includes complete analysis, AI insights, detailed analytics, influencer unlock, and posts view)  
- **Posts Analytics** - Campaign-specific post URL analysis (**10 credits**)

### Key Value Proposition:
- **Profile Analysis gives you EVERYTHING** - no separate charges for AI, analytics, or unlock features
- **Discovery is super cheap** - encourages platform exploration
- **Posts within profiles are free** - only campaign-specific post URLs cost extra

## Dashboard Data Structure

```json
{
  "wallet": {
    "current_balance": 150,
    "monthly_allowance": 500,
    "package_name": "Professional", 
    "billing_cycle_start": "2025-01-01",
    "wallet_status": "active"
  },
  "recent_transactions": [
    {
      "amount": 25,
      "action_type": "profile_analysis",
      "created_at": "2025-01-21T10:30:00",
      "description": "Credits spent for profile_analysis"
    }
  ],
  "monthly_usage": {
    "total_spent": 75,
    "actions_performed": 8,
    "top_actions": ["profile_analysis", "posts_analytics", "discovery"],
    "free_allowances_used": 3
  },
  "pricing_rules": [
    {
      "action_type": "discovery", 
      "credits_per_action": 1,
      "free_allowance_per_month": 50
    },
    {
      "action_type": "profile_analysis", 
      "credits_per_action": 25,
      "free_allowance_per_month": 2
    },
    {
      "action_type": "posts_analytics", 
      "credits_per_action": 10,
      "free_allowance_per_month": 5
    }
  ],
  "profiles_analyzed_count": 12
}
```

## Monthly Usage Analytics

```json
{
  "period": "2025-01",
  "total_credits_spent": 175,
  "total_actions": 15,
  "free_allowances_used": 5,
  "action_breakdown": {
    "discovery": {"count": 15, "credits": 15},
    "profile_analysis": {"count": 7, "credits": 175}, 
    "posts_analytics": {"count": 3, "credits": 30}
  },
  "daily_usage": [
    {"date": "2025-01-20", "credits": 25, "actions": 1}
  ]
}
```

## Free Allowances Status

```json
{
  "discovery": {
    "monthly_allowance": 50,
    "used_this_month": 12,
    "remaining": 38,
    "next_reset": "2025-02-01"
  },
  "profile_analysis": {
    "monthly_allowance": 2,
    "used_this_month": 1,
    "remaining": 1, 
    "next_reset": "2025-02-01"
  },
  "posts_analytics": {
    "monthly_allowance": 5,
    "used_this_month": 3,
    "remaining": 2, 
    "next_reset": "2025-02-01"
  }
}
```

## Error Handling

### Insufficient Credits (402 Payment Required)
```json
{
  "detail": "Insufficient credits. Required: 25, Available: 10. Need 15 more credits.",
  "headers": {
    "X-Credits-Required": "25",
    "X-Credits-Available": "10", 
    "X-Credits-Needed": "15"
  }
}
```

### Wallet Locked (402 Payment Required)  
```json
{
  "detail": "Your credit wallet is locked. Please renew your subscription to continue."
}
```

### No Wallet Found (402 Payment Required)
```json
{
  "detail": "Credit wallet not found. Please contact support."
}
```

## Credit Gate System Flow

1. **Before Access**: System checks if user has enough credits or free allowances
2. **Success Response**: Credits are deducted ONLY after successful data retrieval
3. **Error Handling**: If the request fails, no credits are charged
4. **Free Allowances**: Users get generous monthly free uses that reset automatically
5. **All-Inclusive Access**: Profile Analysis gives you everything - AI insights, analytics, unlock, and posts view

## Frontend Implementation Strategy

### 1. **User Experience Flow**
1. **Check Permission**: Before showing premium features, check `/can-perform/{action_type}`
2. **Show Simple Pricing**: Display clear costs - Discovery (1), Profile Analysis (25), Posts Analytics (10)
3. **Highlight Value**: Profile Analysis includes everything - AI insights, detailed analytics, unlock, and posts
4. **Encourage Discovery**: Discovery is very cheap (1 credit) with 50 free uses monthly
5. **Handle Insufficient Credits**: Redirect to top-up page or show upgrade options
6. **Track Success**: After successful premium feature use, credits are automatically deducted
7. **Update Balance**: Refresh credit balance in UI after any credit-consuming action

### 2. **Key UI/UX Recommendations**
- **Emphasize Profile Analysis value** - "Get AI insights, detailed analytics, influencer unlock, and posts viewing - all included!"
- **Promote Discovery** - "Browse 50 profiles free every month" 
- **Clear pricing display** - Simple 3-tier pricing without confusion
- **Progress indicators** - Show free allowance usage and remaining balance
- **Value messaging** - Highlight what's included vs. competitor separate charges

## Technical Implementation Notes

- **Simplified pricing model**: Only 3 action types to manage
- **All-inclusive Profile Analysis**: One payment gives access to AI insights, detailed analytics, influencer unlock, and posts viewing
- **Discovery encouragement**: Very low cost (1 credit) with generous free allowances (50/month)
- **Authentication required**: All endpoints require user authentication
- **Credit deduction timing**: Credits charged automatically AFTER successful feature usage
- **Monthly resets**: Free allowances reset on the 1st of each month
- **High-performance**: System designed for concurrent operations
- **Transaction safety**: All credit operations are atomic and transaction-safe
- **Complete audit**: Comprehensive trails maintained for every credit operation

## Competitive Advantages

1. **All-inclusive Profile Analysis** - competitors charge separately for each feature
2. **Generous Discovery allowances** - encourages platform adoption and exploration  
3. **No hidden costs** - everything included in Profile Analysis package
4. **Campaign-focused Posts Analytics** - designed specifically for campaign management
5. **Flexible pricing tiers** - works for individuals to enterprises
6. **Transparent pricing** - simple 3-action model vs. complex competitor pricing

## Future Payment Integration (Stripe Ready)

- **Credit purchase estimation** - `/top-up/estimate` endpoint ready
- **Payment processing infrastructure** - Complete backend support prepared
- **Top-up history tracking** - Transaction records ready for payment integration
- **Flexible pricing configuration** - Easy to adjust rates and packages
- **Bulk purchase discounts** - Infrastructure ready for promotional pricing

---

*This credits system provides a complete foundation for monetizing the Instagram analytics platform while maintaining excellent user experience, encouraging platform exploration, and maximizing revenue per transaction through value-packed offerings.*