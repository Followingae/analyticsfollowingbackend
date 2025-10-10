# 🚀 Complete Migration: Permanent Unlocks → 30-Day Renewable Access

## **MIGRATION OVERVIEW**

This migration fixes the fundamental business model flaw where users were getting **permanent unlocks** instead of **30-day renewable access**.

### **Before Migration (BROKEN)**
- ❌ `unlocked_influencers` table = permanent access (wrong!)
- ❌ API only showed permanent unlocks
- ❌ Users never needed to pay again after first unlock

### **After Migration (CORRECT)**
- ✅ `user_profile_access` table = 30-day renewable access
- ✅ API shows 30-day access with expiry dates
- ✅ Users must renew access every 30 days (proper business model)

---

## **EXECUTION PLAN**

### **PHASE 1: IMMEDIATE API FIX** ✅ **COMPLETED**
**File**: `app/database/comprehensive_service.py`
- Fixed `get_user_unlocked_profiles()` to use `user_profile_access` table
- Now shows proper 30-day access with expiry dates
- **Result**: client@analyticsfollowing.com will now see all 9 profiles with remaining days

### **PHASE 2: SUPABASE SQL MIGRATIONS**
Execute these SQL scripts in Supabase in order:

#### **Step 1: Migrate Existing Data**
```bash
# File: migration_01_migrate_permanent_to_30day.sql
```
- Converts all permanent unlocks to 30-day access
- Preserves existing user access but adds expiry dates
- **SAFE**: No data loss, backwards compatible

#### **Step 2: Update Credit System**
```bash
# File: migration_02_update_credit_system.sql
```
- Updates pricing rules for 30-day access
- Creates new database function for credit spending
- **SAFE**: Improves credit handling

#### **Step 3: Add Helper Functions**
```bash
# File: migration_03_update_middleware.sql
```
- Creates functions to check 30-day access
- **SAFE**: Adds new functionality without breaking existing

#### **Step 4: Remove Old Table**
```bash
# File: migration_04_cleanup_unlocked_influencers.sql
```
- ⚠️ **FINAL STEP**: Only after testing everything works
- Removes `unlocked_influencers` table
- Creates backup before deletion

---

## **CODE CHANGES MADE**

### **1. API Layer** ✅ **COMPLETED**
**File**: `app/database/comprehensive_service.py`
- `get_user_unlocked_profiles()` now uses `user_profile_access`
- Shows proper expiry dates and remaining days
- Filters out expired access automatically

### **2. Credit Gate Middleware** ✅ **COMPLETED**
**Files**: `app/middleware/atomic_credit_gate.py`
- Check functions now use 30-day access system
- Credit spending creates 30-day access instead of permanent unlocks
- Removes permanent unlock creation

---

## **TESTING CHECKLIST**

### **After Phase 1 (API Fix)**
- [ ] client@analyticsfollowing.com can see all 9 profiles
- [ ] Each profile shows correct expiry date and remaining days
- [ ] barakatme appears in unlocked profiles list

### **After SQL Migrations**
- [ ] All existing unlocks converted to 30-day access
- [ ] New credit spending creates 30-day access
- [ ] Expired access automatically removed from lists
- [ ] Credit system works with new 30-day model

### **After Full Migration**
- [ ] No references to `unlocked_influencers` in active code
- [ ] All access properly expires after 30 days
- [ ] Users must renew access to continue viewing profiles

---

## **BUSINESS MODEL IMPACT**

### **Revenue Impact** 📈 **POSITIVE**
- **Before**: Users paid once, got permanent access (revenue loss)
- **After**: Users pay every 30 days for continued access (recurring revenue)

### **User Experience** 📱 **IMPROVED**
- Clear expiry dates and remaining days
- Proper renewable access model
- Consistent pricing and access rules

---

## **ROLLBACK PLAN**

If issues occur:
1. **Phase 1 Rollback**: Revert `comprehensive_service.py` changes
2. **SQL Rollback**: Use backup tables created in migration scripts
3. **Full Rollback**: Restore from pre-migration database backup

---

## **EXECUTION ORDER**

1. ✅ **COMPLETED**: Phase 1 API fix (already applied)
2. 🔄 **NEXT**: Apply SQL migrations in order (1→2→3→4)
3. 🧪 **TEST**: Verify each step works before proceeding
4. 🚀 **DEPLOY**: Full system using 30-day renewable access model

**Total estimated time**: 30 minutes to apply all SQL scripts
**Risk level**: LOW (comprehensive backups and rollback plans)
**Business impact**: HIGH POSITIVE (fixes broken revenue model)