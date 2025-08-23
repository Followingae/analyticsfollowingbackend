# Final Subscription Tiers - Analytics Following Platform

## Updated Subscription Structure:

### **FREE TIER** 
- **Price**: Free
- **Team Members**: 1 (individual only)
- **Profile Analysis**: 5 profiles/month
- **Email Unlocks**: Not available
- **Post Analytics**: Not included
- **Campaigns**: Not available
- **Lists**: Not available
- **Proposals**: Locked (superadmin unlock only)
- **Export**: Not available
- **Support**: Standard support
- **Topups**: Not available

---

### **STANDARD TIER - $199/month**
- **Price**: $199 per month
- **Team Members**: Up to 2 team members (full professional industry-standard team management)
- **Profile Analysis**: 500 profiles/month
- **Email Unlocks**: 250 emails (if available from profiles)
- **Post Analytics**: 125 post analyses/month
- **Campaigns**: ✅ Create and manage campaigns
- **Lists**: ✅ Create and manage lists
- **Proposals**: 🔒 Locked (superadmin unlock only - for agency clients)
- **Export**: ✅ Export all unlocked creators, posts, and campaigns
- **Support**: ✅ Priority Support
- **Topups**: ✅ Available at standard rates

---

### **PREMIUM TIER - $499/month**
- **Price**: $499 per month  
- **Team Members**: Up to 5 team members (full professional industry-standard team management)
- **Profile Analysis**: 2,000 profiles/month
- **Email Unlocks**: 800 emails (if available from profiles)
- **Post Analytics**: 300 post analyses/month
- **Campaigns**: ✅ Create and manage campaigns
- **Lists**: ✅ Create and manage lists
- **Proposals**: 🔒 Locked (superadmin unlock only - for agency clients)
- **Export**: ✅ Export all unlocked creators, posts, and campaigns
- **Support**: ✅ Priority Support
- **Topups**: ✅ Available at 20% discount from Standard rates

---

### **ENTERPRISE TIER** (Removed - Only 3 tiers now)

---

## Key Features Added:

### 🏢 **Team Management System** (Industry Standard)
- **Professional team collaboration capabilities**
- **Role-based permissions within teams**
- **Shared access to unlocked profiles and campaigns**
- **Team member invitation and management**
- **Usage tracking per team member**

### 📧 **Email Unlock System**
- **Track email unlocks separately from profile analysis**
- **Email availability depends on profile data quality**
- **Monthly limits per subscription tier**
- **Email unlock history and tracking**

### 💰 **Topup System**
- **Standard Tier**: Standard topup rates
- **Premium Tier**: 20% discount on all topups
- **Flexible topup packages for additional profile analyses, emails, and post analytics**

### 🔒 **Proposals System**
- **Locked by default for all subscription tiers**
- **Only superadmin can unlock proposals for specific accounts**
- **Designed for agency clients who work directly with your team**

### 📤 **Universal Export**
- **All paid tiers get export capabilities**
- **Export unlocked creators, posts, and campaign data**
- **No tier-based export restrictions**
- **Bulk export removed as distinguishing feature**

---

## Credit Actions Updated:

| Action | Standard Cost | Premium Discount | Available To |
|--------|---------------|------------------|--------------|
| Profile Analysis | Included in monthly limit | Included in monthly limit | Standard, Premium |
| Email Unlock | Included in monthly limit | Included in monthly limit | Standard, Premium |
| Post Analytics | Included in monthly limit | Included in monthly limit | Standard, Premium |
| Additional Profiles (Topup) | Standard rate | 20% discount | Standard, Premium |
| Additional Emails (Topup) | Standard rate | 20% discount | Standard, Premium |
| Additional Posts (Topup) | Standard rate | 20% discount | Standard, Premium |

---

## Database Schema Changes Needed:

### New Tables Required:

1. **`team_members`** - Team member management
2. **`team_invitations`** - Team invitation system  
3. **`email_unlocks`** - Email unlock tracking
4. **`subscription_limits`** - Monthly limits tracking
5. **`topup_orders`** - Topup purchase history
6. **`proposal_unlocks`** - Superadmin proposal access grants

### Updated Tables:

1. **`users`** - Add team_id, team_role fields
2. **`credit_wallets`** - Add discount_rate field
3. **`subscription_tiers`** - Update with new limits and pricing

---

## Implementation Priority:

1. **Team Management System** - Core collaboration feature
2. **Email Unlock Tracking** - New monetization layer
3. **Updated Subscription Limits** - Monthly usage caps
4. **Topup Discount System** - Premium tier benefit
5. **Universal Export System** - Remove tier restrictions
6. **Proposal Superadmin Controls** - Agency client management

This structure creates a professional B2B SaaS platform with industry-standard team collaboration, clear value tiers, and agency-friendly proposal management.