# Currency Migration Implementation Guide

## 🎯 Overview
Complete migration strategy to implement **industry-standard currency-per-team configuration** replacing hardcoded USD across all modules. This follows the same pattern used by Stripe, Shopify, Salesforce, and other major B2B SaaS platforms.

## 📋 Migration Steps

### ✅ Step 1: Currency Configuration System
**Status: COMPLETED**
- ✅ Created `team_currency_settings` table with RLS policies
- ✅ Added trigger for auto-creating currency settings for new teams
- ✅ Updated `unified_models.py` with `TeamCurrencySettings` model
- ✅ Added relationship to `Team` model

**Files Created:**
- `migrations/20250127_add_team_currency_settings.sql`
- Updated: `app/database/unified_models.py`

### ✅ Step 2: Database Column Analysis
**Status: COMPLETED**
- ✅ Identified all USD-hardcoded columns across 7 tables
- ✅ Created migration strategy for backward-compatible rename

**Files Created:**
- `migrations/20250127_rename_usd_columns_analysis.md`

### ✅ Step 3: Column Migration Scripts
**Status: COMPLETED**
- ✅ Phase 1: Add generic columns (backward compatible)
- ✅ Phase 2: Remove USD columns (breaking change)

**Files Created:**
- `migrations/20250127_phase1_add_generic_currency_columns.sql`
- `migrations/20250127_phase2_remove_usd_columns.sql`

### ✅ Step 4: Currency Service Layer
**Status: COMPLETED**
- ✅ Created comprehensive `CurrencyService` with caching
- ✅ Team and user currency resolution
- ✅ Amount formatting and parsing utilities
- ✅ Industry-standard singleton pattern

**Files Created:**
- `app/services/currency_service.py`

### ✅ Step 5: Currency API Routes
**Status: COMPLETED**
- ✅ Superadmin currency management endpoints
- ✅ Team currency configuration
- ✅ Currency formatting utilities

**Files Created:**
- `app/api/currency_routes.py`

### 🔄 Step 6: Update Application Code
**Status: PENDING**

#### API Endpoints to Update
All endpoints returning monetary amounts need to use `currency_service`:

1. **Proposal System** (`app/api/superadmin_proposals_routes.py`)
   - Replace hardcoded `"currency": "USD"` with dynamic currency
   - Use `format_amount()` for all monetary displays

2. **Credit System** (`app/api/credit_routes.py`)
   - Replace hardcoded `"currency": "USD"`
   - Use team currency for all pricing calculations

3. **Financial Management** (`app/api/admin/financial_management_routes.py`)
   - Update all monetary responses with dynamic currency

#### Service Layer Updates
Update services to use generic column names:

1. **Proposals Service** (`app/services/refined_proposals_service.py`)
   - Update to use `post_price_cents` instead of `post_price_usd_cents`
   - Add currency formatting to all monetary outputs

2. **Credit Services**
   - Update to use `price_cents` instead of `price_usd_cents`

#### Database Query Updates
Replace all queries using USD-specific column names:
```python
# OLD (Phase 1 - use both columns during transition)
story_price_usd_cents = profile.story_price_usd_cents

# NEW (Phase 2 - use generic columns)
story_price_cents = profile.story_price_cents
```

### 🔄 Step 7: Integration Updates
**Status: PENDING**

#### Add Currency Service to Main App
```python
# In main.py, add currency routes
from app.api.currency_routes import router as currency_router
app.include_router(currency_router)
```

#### Update Response Models
Add currency info to all monetary response models:
```python
class ProposalResponse(BaseModel):
    total_budget_cents: int
    currency_info: dict  # From currency_service
    formatted_total_budget: str  # Human-readable
```

### 🧪 Step 8: Testing
**Status: PENDING**

#### Test Cases Needed
1. **Team Currency Management**
   - Create team → auto-creates USD currency settings
   - Superadmin updates team currency → all team data reflects new currency
   - User queries → returns correct team currency

2. **API Response Testing**
   - All monetary endpoints return dynamic currency
   - Currency formatting works correctly
   - Different teams see their respective currencies

3. **Migration Testing**
   - Phase 1 migration preserves all data
   - Phase 2 migration removes old columns cleanly
   - No data loss during transitions

## 🚀 Deployment Strategy

### Phase 1 Deployment (Backward Compatible)
1. ✅ Deploy currency configuration system
2. 🔄 Run Phase 1 column migration (add generic columns)
3. 🔄 Update application code to use new columns
4. 🔄 Deploy updated application code
5. 🧪 Test extensively with both old and new columns

### Phase 2 Deployment (Breaking Change)
1. 🔄 Verify all code uses generic columns
2. 🔄 Run Phase 2 migration (remove USD columns)
3. 🧪 Final testing and verification

## 🔧 Manual Steps Required

### 1. Run Database Migrations
```sql
-- Step 1: Create currency configuration
\i migrations/20250127_add_team_currency_settings.sql

-- Step 2: Add generic columns (safe to run)
\i migrations/20250127_phase1_add_generic_currency_columns.sql

-- Step 3: After code updates, remove old columns
\i migrations/20250127_phase2_remove_usd_columns.sql
```

### 2. Add Currency Routes to Main App
```python
# In main.py
from app.api.currency_routes import router as currency_router
app.include_router(currency_router)
```

### 3. Update Environment Variables
No additional environment variables needed - uses existing database and cache configuration.

## 🎯 Benefits After Migration

### 1. **Superadmin Currency Control**
- Superadmins can change any team's currency instantly
- No database migration needed for currency changes
- Single source of truth per team

### 2. **Clean Database Design**
- No USD pollution in business tables
- Consistent naming convention (`*_cents` for all monetary fields)
- Better query performance (no currency JOINs)

### 3. **Industry Standard Architecture**
- Follows Stripe/Shopify/Salesforce patterns
- Easier maintenance and scaling
- Cleaner business logic

### 4. **Enhanced User Experience**
- Teams see consistent currency throughout platform
- Proper currency formatting and symbols
- Localized monetary displays

## ⚠️ Important Notes

1. **Backward Compatibility**: Phase 1 migration maintains both old and new columns during transition
2. **Data Integrity**: All migrations preserve existing data and convert appropriately
3. **Performance**: Currency service includes comprehensive caching (1-hour TTL)
4. **Security**: RLS policies ensure teams can only access their own currency settings
5. **Testing**: Extensive testing required before Phase 2 deployment

## 🔗 Related Files

### Database
- `migrations/20250127_*.sql` - All migration scripts
- `app/database/unified_models.py` - Updated with TeamCurrencySettings

### Services
- `app/services/currency_service.py` - Core currency logic
- `app/api/currency_routes.py` - Currency management API

### Documentation
- `migrations/20250127_rename_usd_columns_analysis.md` - Column analysis
- `CURRENCY_MIGRATION_GUIDE.md` - This implementation guide

The migration strategy provides **complete USD hardcoding removal** while maintaining **zero downtime** and **full backward compatibility** during the transition period.