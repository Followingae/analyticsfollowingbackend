# Billing Registration Fix: Orphaned Teams & Missing Wallets

**Date:** 2026-02-22
**Severity:** Critical
**Files Modified:** `app/api/billing_routes.py`
**Database Changes:** Manual fixes via Supabase MCP

---

## Problem

New users registering via the Stripe payment flow ended up with:
- **No team_member record** → 401 errors on `GET /api/v1/teams/overview`
- **No credit_wallet** → 404 errors on `GET /api/v1/credits/wallet/summary`
- **Orphaned teams** → Teams created with 0 members (6 out of 9 teams were orphaned)

### Affected User (Initial Report)
- **Email:** `umair@gmail.com`
- **Supabase ID:** `28279595-60a4-4c6c-b480-0538da0b36b5`
- **Symptoms:** Two 401 errors on team overview, 404 on wallet summary

---

## Root Cause Analysis

### Root Cause 1: Missing Rollback on Exceptions (Original Bug)

In `billing_routes.py`, three registration paths create teams, team_members, and wallets:
1. **Webhook** (`POST /webhook/complete-registration`)
2. **Verify-session** (`GET /verify-session/{session_id}`)
3. **Free-tier** (`POST /free-tier-registration`)

The `get_db()` dependency in `connection.py` (line 349-350) **auto-commits** the SQLAlchemy session when an endpoint returns successfully. When team/wallet creation threw an exception:
- The exception was caught (no 500 error)
- But `db.rollback()` was **never called**
- The `get_db` auto-commit persisted the **partial data** (team without member/wallet)
- Result: orphaned teams

### Root Cause 2: "User Exists" Paths Skip Team/Wallet Creation (Deeper Bug)

The registration flow has a race condition:
1. Frontend calls `POST /api/v1/auth/register` → creates user in Supabase auth + `users` table
2. Frontend redirects to Stripe for payment
3. After payment, Stripe webhook fires → finds user **already exists** → only updates `subscription_tier` → **no team/wallet created**
4. Frontend polls `GET /verify-session/{session_id}` → finds user **already exists** → just logs in → **no team/wallet created**

Both "user exists" paths assumed the user was fully provisioned, but `/auth/register` only creates the auth + user record — not the team or wallet.

### Root Cause 3: Incorrect CreditWallet Column Names (Verify-Session Path)

The verify-session path used wrong column names:
- `billing_cycle_start` → should be `current_billing_cycle_start`
- `billing_cycle_end` → column doesn't exist
- `stripe_customer_id`, `stripe_subscription_id` → columns don't exist
- `last_credit_reset`, `next_credit_reset` → columns don't exist

### Root Cause 4: Wrong `user_id` for Team Members (All Paths)

The team auth middleware (`team_auth_middleware.py` line 182) looks up team_members by **Supabase auth ID**:
```python
TeamMember.user_id == supabase_user_id
```

But billing_routes was setting `team_member.user_id = created_user.id` (app user ID), causing the middleware to never find the team member.

---

## Fixes Applied

### Fix 1: Shared `_ensure_team_and_wallet()` Helper Function

Added a new idempotent helper function at the top of `billing_routes.py` that:
- Checks if `team_member` exists for the user (by Supabase ID) — creates team + member if missing
- Checks if `credit_wallet` exists for the user (by Supabase ID) — creates wallet if missing
- Safe to call multiple times (no duplicates)

```python
async def _ensure_team_and_wallet(db: AsyncSession, user, plan: str):
    """
    Ensure a user has a team_member record and credit_wallet.
    Creates them if missing. Idempotent — safe to call multiple times.
    """
    # Check team_member exists → create team + member if not
    # Check credit_wallet exists → create wallet if not
```

### Fix 2: Webhook "User Exists" Path Now Provisions Team/Wallet

**Before:**
```python
if existing_user:
    # Just update subscription tier
    await db.execute(update(User)...)
    await db.commit()
```

**After:**
```python
if existing_user:
    await db.execute(update(User)...)
    await _ensure_team_and_wallet(db, existing_user, plan)
    await db.commit()
```

### Fix 3: Verify-Session "User Exists" Path Now Provisions Team/Wallet

**Before:**
```python
if user and user.status == 'active':
    # Just try to login and return tokens
```

**After:**
```python
if user and user.status == 'active':
    await _ensure_team_and_wallet(db, user, plan)
    await db.commit()
    # Then login and return tokens
```

### Fix 4: All "New User" Paths Use Shared Helper

Replaced ~50 lines of duplicated team/wallet creation code in each of the 3 paths with:
```python
await _ensure_team_and_wallet(db, created_user, plan)
```

### Fix 5: Rollback in All Exception Handlers

Added `await db.rollback()` in all except blocks to prevent partial commits:
```python
except Exception as e:
    logger.error(f"Failed to create user: {e}")
    try:
        await db.rollback()
    except Exception as rb_err:
        logger.warning(f"Rollback error: {rb_err}")
```

### Fix 6: Correct CreditWallet Column Names

Fixed verify-session path to use actual model columns:
- `current_billing_cycle_start` (was `billing_cycle_start`)
- `next_reset_date` (was various non-existent columns)

### Fix 7: Correct `user_id` — Use Supabase ID

All paths now compute:
```python
member_user_id = UUID(str(user.supabase_user_id)) if user.supabase_user_id else user.id
```
This matches what `team_auth_middleware.py` queries by.

### Fix 8: Correct `login_user()` Method Call

Verify-session path called `supabase_auth_service.login()` (doesn't exist) and accessed response as dict. Fixed to:
```python
auth_response = await supabase_auth_service.login_user(login_request)
auth_response.access_token  # attribute access, not dict
```

---

## Database Fixes (Manual via Supabase MCP)

### Umair's Account (`umair@gmail.com`)
```sql
-- Inserted team_member (Supabase ID → Umair's Team, role=owner)
INSERT INTO team_members (id, team_id, user_id, role, status)
VALUES (..., 'a9a3917c-...', '28279595-...', 'owner', 'active');

-- Created credit_wallet (2000 credits, standard tier)
INSERT INTO credit_wallets (user_id, current_balance, ...)
VALUES ('28279595-...', 2000, ...);

-- Created monthly_usage_tracking
INSERT INTO monthly_usage_tracking (...) VALUES (...);
```

### Test User (`testreguser2026@gmail.com`)
```sql
-- Created team, team_member, and credit_wallet
-- Supabase ID: ca3e457a-32dd-4a59-9da0-d3ed81be7ed0
INSERT INTO teams (...) VALUES (..., 'test ali''s Team', 'standard', ...);
INSERT INTO team_members (...) VALUES (..., 'ca3e457a-...', 'owner', 'active');
INSERT INTO credit_wallets (user_id, current_balance, ...) VALUES ('ca3e457a-...', 2000, ...);
```

### Orphaned Teams Cleanup
```sql
-- Deleted 5 orphaned teams (0 members):
-- 2x Steven's Team, 2x Santa's Team, 1x John Doe's Team
DELETE FROM teams WHERE id IN (...);
```

### Final State
All 5 remaining teams have exactly 1 member and 1 wallet each:
| Team | Tier | Members | Wallets |
|------|------|---------|---------|
| test ali's Team | standard | 1 | 1 |
| Umair's Team | standard | 1 | 1 |
| John Doe's Team | standard | 1 | 1 |
| Santa's Team | standard | 1 | 1 |
| Santa's Team | standard | 1 | 1 |

---

## Frontend Issue Discovered

### `ENDPOINTS.billing.verifySession is not a function`

During browser testing, the welcome page (`/welcome?session_id=...`) was stuck on "Verifying payment" with console errors:
```
TypeError: ENDPOINTS.billing.verifySession is not a function
```

**Cause:** Stale webpack cache. The `api.ts` config file correctly defines `verifySession` as a function, but the browser was serving a cached bundle where it wasn't.

**Fix:** Hard refresh (`Ctrl+Shift+R`) resolved it. The welcome page then showed "Welcome to Following!" with all 3 green checkmarks (Payment verified, Account created, Subscription activated).

**Note:** This was a frontend caching issue, not a code bug. The `api.ts` file at line 198 correctly defines:
```typescript
verifySession: (sessionId: string) => `/api/v1/billing/verify-session/${sessionId}`,
```

---

## Architecture Notes

### Dual ID System
- **App User ID** (`users.id`): Internal app identifier (e.g., `01da768a-...`)
- **Supabase Auth ID** (`users.supabase_user_id` / `auth.users.id`): Supabase authentication identifier (e.g., `ca3e457a-...`)
- **Team auth middleware** queries `team_members.user_id` by **Supabase ID**
- **FK constraints** on `team_members.user_id` and `credit_wallets.user_id` reference `users.id` in the SQLAlchemy model, but are **not enforced** in the actual database — existing data all uses Supabase IDs

### Registration Flow (After Fix)
```
1. Frontend: POST /auth/register → creates Supabase auth + users table entry
2. Frontend: POST /billing/pre-registration-checkout → creates Stripe session
3. User: Pays on Stripe checkout
4. Stripe: Fires webhook → POST /billing/webhook/complete-registration
   → Finds user exists → updates subscription_tier
   → Calls _ensure_team_and_wallet() → creates team + wallet if missing ✅
5. Frontend: Redirects to /welcome?session_id=...
6. Frontend: Polls GET /billing/verify-session/{session_id}
   → Finds user exists → calls _ensure_team_and_wallet() → ensures team + wallet ✅
   → Logs in user → returns access_token
7. Frontend: Stores tokens → redirects to /dashboard
```

### Key Design Decision: Idempotent Provisioning
The `_ensure_team_and_wallet()` helper is designed to be **idempotent** — it checks before creating. This means:
- Multiple paths can call it safely (webhook + verify-session may both run)
- No duplicate teams or wallets are created
- If the webhook provisions successfully, verify-session just confirms they exist
- If the webhook fails, verify-session picks up and creates them

---

## Testing

### Test Performed
1. Created new user `testreguser2026@gmail.com` via browser
2. Selected Standard plan ($199/month)
3. Completed Stripe checkout with test card (4242 4242 4242 4242)
4. Welcome page showed success after hard refresh
5. Manually verified and fixed database records

### To Verify After Backend Restart
1. Restart backend (kill PID 26808, restart uvicorn)
2. Register a new test user through the full flow
3. Check database: `team_members` and `credit_wallets` should exist
4. Login as new user: `GET /api/v1/teams/overview` should return 200
5. Check: `GET /api/v1/credits/wallet/summary` should return 200
