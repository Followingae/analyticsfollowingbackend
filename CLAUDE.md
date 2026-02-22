# Analytics Following Backend

Instagram analytics platform backend built with FastAPI. Provides Instagram profile analysis with AI-powered content intelligence, credit-based monetization, and B2B SaaS team features.

**Supabase Project ID**: check `.env` for `SUPABASE_URL`

---

## Tech Stack

### Backend
- **Framework**: FastAPI (Python), async/await throughout
- **Database**: PostgreSQL via Supabase, SQLAlchemy (async) + asyncpg
- **Auth**: Supabase Auth + Row Level Security (RLS)
- **Caching**: Redis (profile 24h, posts 12h, AI 7d, credits 5m)
- **Background Jobs**: Celery with Redis broker
- **External API**: Decodo Instagram API (formerly Apify)
- **CDN**: Cloudflare R2 (`thumbnails-prod` bucket)

### AI/ML Models
- **Sentiment**: `cardiffnlp/twitter-roberta-base-sentiment-latest` (~90% accuracy)
- **Language**: `papluca/xlm-roberta-base-language-detection` (20+ languages)
- **Classification**: `facebook/bart-large-mnli` + keyword matching (85% accuracy, 20+ categories)
- **Management**: Singleton pattern, global model caching, Celery background processing (3-5s/post)

### Frontend (separate repo)
- Next.js 15 + React 19 + TypeScript 5
- shadcn/ui + Radix UI + Tailwind CSS v4
- TanStack Query v5 + Zod validation
- Recharts + Chart.js + ApexCharts

---

## Database Schema

**Active Tables: 19 | Total Tables: 52 | Functions: 30+ | API Endpoints: 128**

### Active Tables by Domain

| Domain | Tables |
|--------|--------|
| Instagram Analytics | `profiles`, `posts`, `related_profiles` |
| User Management | `users`, `auth_users`, `user_profile_access`, `user_roles` |
| Credits & Monetization | `credit_packages`, `credit_wallets`, `credit_pricing_rules` |
| Team Management | `teams`, `team_members`, `monthly_usage_tracking`, `team_profile_access` |
| CDN & Media | `cdn_image_assets`, `cdn_image_jobs`, `cdn_processing_stats` |
| System | `system_configurations`, `list_templates` |

Empty but potentially needed: `user_lists`, `user_profiles`. 31 unused tables available for cleanup.

### Core Table Structures

```sql
-- profiles (Main Instagram analytics)
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR NOT NULL UNIQUE,
    full_name VARCHAR, biography TEXT,
    followers_count BIGINT, following_count BIGINT, posts_count BIGINT,
    -- AI fields
    ai_primary_content_type VARCHAR(50),
    ai_content_distribution JSONB,    -- {"Fashion": 0.4, "Travel": 0.3}
    ai_avg_sentiment_score FLOAT,
    ai_language_distribution JSONB,   -- {"en": 0.8, "ar": 0.2}
    ai_content_quality_score FLOAT,   -- 0-1
    ai_profile_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now()
);

-- posts (Individual post analytics)
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    instagram_post_id VARCHAR UNIQUE,
    caption TEXT, likes_count BIGINT, comments_count BIGINT,
    -- AI fields
    ai_content_category VARCHAR(50), ai_category_confidence FLOAT,
    ai_sentiment VARCHAR(20), ai_sentiment_score FLOAT, ai_sentiment_confidence FLOAT,
    ai_language_code VARCHAR(10), ai_language_confidence FLOAT,
    ai_analysis_raw JSONB, ai_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

-- credit_wallets
CREATE TABLE credit_wallets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    current_balance INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0, total_spent INTEGER NOT NULL DEFAULT 0,
    billing_cycle_start DATE, billing_cycle_end DATE,
    package_id UUID REFERENCES credit_packages(id),
    created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now()
);

-- users (Application user data)
CREATE TABLE users (
    id UUID PRIMARY KEY, supabase_user_id TEXT,
    email TEXT NOT NULL, full_name TEXT,
    role TEXT NOT NULL, status TEXT NOT NULL,
    credits INTEGER NOT NULL, credits_used_this_month INTEGER NOT NULL,
    subscription_tier TEXT, preferences JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(), updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### Key Foreign Key Relationships

```
auth.users.id -> credit_wallets.user_id, user_profiles.user_id
profiles.id   -> posts.profile_id, related_profiles.profile_id,
                 user_profile_access.profile_id, audience_demographics.profile_id
users.id      -> campaigns.user_id, user_favorites.user_id, user_lists.user_id
credit_packages.id -> credit_wallets.package_id
credit_wallets.id  -> credit_transactions.wallet_id
```

---

## Profile Completeness Definition

A profile is **COMPLETE** when:
1. `followers_count > 0` and `posts_count > 0`
2. `biography` exists
3. 12+ posts stored in database
4. 12+ posts have AI analysis (`ai_content_category`, `ai_sentiment`, `ai_language_code`)
5. `ai_profile_analyzed_at IS NOT NULL`
6. 12+ posts have CDN thumbnails (`cdn_thumbnail_url IS NOT NULL`)
7. Demographics are optional (currently missing for all profiles)

Age/freshness is NOT a completeness criterion.

---

## API Endpoints

### Creator Analytics
```
GET  /api/v1/search/creator/{username}
     Single endpoint, 5 sections: OVERVIEW, AUDIENCE, ENGAGEMENT, CONTENT, POSTS
     New creator: ~160s | Unlocked creator: <1s (fast path)

GET  /api/profile/{username}           - Profile analytics (all tiers identical)
GET  /api/profile/{username}/posts     - Paginated posts with AI analysis
POST /api/export                       - Export (Standard/Premium tiers, no extra credits)
```

### Discovery System (`/api/v1/discovery/`)
```
GET  /browse              - Browse all profiles (paginated, filterable)
POST /unlock-profile      - Unlock profile (25 credits, 30-day access)
GET  /unlocked-profiles   - User's unlocked profiles with expiry
GET  /dashboard           - Discovery stats and overview
GET  /categories          - Content categories with counts
GET  /pricing             - Credit pricing info
POST /search-advanced     - Multi-criteria search
```

### Credits (`/api/v1/credits/`)
```
GET  /balance                    - Current balance
GET  /wallet/summary             - Wallet summary
GET  /dashboard                  - Credit dashboard
POST /wallet/create              - Create wallet
GET  /transactions               - Transaction history
GET  /transactions/search        - Search transactions
GET  /usage/monthly              - Monthly usage
GET  /analytics/spending         - Multi-month analytics
GET  /can-perform/{action_type}  - Check permission
GET  /pricing                    - All pricing rules
GET  /pricing/{action_type}      - Action pricing
POST /pricing/calculate          - Bulk pricing
GET  /allowances                 - Free allowance status
GET  /system/stats               - System stats
```

### Admin (`/api/v1/admin/repair/`)
```
GET  /profile-completeness/scan             - Scan incomplete profiles
POST /profile-completeness/repair           - Repair (supports dry-run)
GET  /discovery/stats                       - Discovery stats
GET  /discovery/config                      - Config validation
GET  /discovery/queue-status                - Queue status
POST /discovery/manual-trigger/{username}   - Manual trigger
GET  /health                                - System health
POST /test/validate-completeness/{username} - Test profile
```

### Cloudflare (`/api/v1/cloudflare/`)
```
GET  /dashboard                              - Infrastructure overview
GET  /health                                 - Health check
GET  /r2/buckets                             - R2 buckets
GET  /r2/buckets/{name}/usage                - Bucket usage
GET  /workers                                - Workers list
GET  /workers/{name}/analytics               - Worker analytics
GET  /zone/analytics                         - Zone metrics
GET  /cache/analytics                        - Cache metrics
GET  /cdn/performance                        - CDN metrics
GET  /ai-gateway                             - AI Gateway apps
GET  /ai-gateway/{id}/analytics              - AI Gateway analytics
GET  /page-rules                             - Page rules
POST /cache/rules                            - Create cache rules
```

### System
```
GET  /api/health              - Health check (<50ms)
GET  /api/metrics             - Performance metrics
GET  /api/streaming/metrics   - SSE live monitoring (5s updates)
```

Route prefixes: `/auth/`, `/credits/`, `/instagram/`, `/settings/`

---

## Credits & Billing System

### Subscription Plans

| Plan | Price | Team Size | Monthly Profiles | Monthly Emails | Monthly Posts | Topup Discount |
|------|-------|-----------|-----------------|----------------|---------------|----------------|
| Free | $0 | 1 | 5 | 0 | 0 | 0% |
| Standard | $199/mo | 2 | 500 | 250 | 125 | 0% |
| Premium | $499/mo | 5 | 2,000 | 800 | 300 | 20% |

### Credit Costs per Action

| Action | Credits | Free Allowance |
|--------|---------|----------------|
| Profile Analysis (`influencer_unlock`) | 25 | - |
| Post Analytics (`post_analytics`) | 5 | - |
| Discovery (`discovery_pagination`) | 10/page | 5 pages/mo |
| Email Unlock | 1 | - |
| Campaign Analysis | 10 | - |
| Bulk Export (`bulk_export`) | 50 | 1/mo |
| Advanced Search (`advanced_search`) | 15 | 10/mo |

### Topup Packages
- Starter: 1,000 credits / $50
- Professional: 2,500 credits / $125
- Enterprise: 10,000 credits / $500

Business model: Monthly allowance consumed first, then topup credits. Premium users get 20% topup discount.

### Credit Gate Integration
```python
@router.get("/instagram/profile/{username}")
@requires_credits("influencer_unlock", return_detailed_response=True)
async def analyze_instagram_profile(username: str, current_user = Depends(get_current_active_user)):
    # Automatic credit validation and spending
```

### Credit Services
- `CreditWalletService` (`credit_wallet_service.py`) - wallet CRUD, balance, billing cycles
- `CreditTransactionService` (`credit_transaction_service.py`) - history, search, analytics
- `CreditPricingService` (`credit_pricing_service.py`) - pricing rules, cost calculations
- `credit_gate.py` - `@requires_credits()` decorator middleware

### Pending Billing Integrations
- Stripe payment processing (infrastructure ready)
- Admin dashboard for subscription management
- Revenue analytics

---

## Discovery & Background Processing

### Similar Profiles Auto-Discovery Flow
1. Creator Analytics finds similar profiles -> stored in `related_profiles`
2. Hook triggers background processing
3. Background processor queues for full analytics (Decodo + CDN + AI)
4. Rate limited: max 3 concurrent, 100/hour, 1,000/day
5. Quality filter: min 1K followers, skip already-complete profiles

### Active Hook Integrations
```python
# comprehensive_service.py:823 - when related profiles stored
await hook_related_profiles_stored(source_username, profile_id, related_profiles_count)

# main.py:1157 - when creator analytics pipeline completes
await hook_creator_analytics_complete(source_username, profile_id, analytics_metadata)

# post_analytics_service.py:79 - when post analysis completes
await hook_post_analytics_complete(source_username, profile_id, post_shortcode, analytics_metadata)
```

### Discovery Configuration
```python
DISCOVERY_ENABLED = True
DISCOVERY_MAX_CONCURRENT_PROFILES = 3
DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY = 1000
DISCOVERY_MIN_FOLLOWERS_COUNT = 1000
DISCOVERY_SKIP_EXISTING_PROFILES = True
DISCOVERY_RETRY_ATTEMPTS = 3
```

### Key Discovery Files
```
app/services/profile_completeness_repair_service.py
app/services/similar_profiles_discovery_service.py
app/services/background/similar_profiles_processor.py
app/services/user_discovery_service.py
app/api/admin_repair_routes.py
app/api/user_discovery_routes.py
app/core/discovery_config.py
scripts/repair_profile_completeness.py
scripts/test_similar_profiles_discovery.py
scripts/debug_discovery_integration.py
```

### CLI Tools
```bash
# Profile completeness
python scripts/repair_profile_completeness.py --scan-only|--dry-run|--repair [--limit=N --username-filter=PATTERN]

# Discovery testing
python scripts/test_similar_profiles_discovery.py --test-config|--test-discovery|--test-processor|--all

# Debug
python scripts/debug_discovery_integration.py --username=USER|--test-pipeline=USER|--check-database
```

---

## Security

### Row Level Security (RLS)
All 19 active tables have comprehensive RLS policies:
- Team-based access control for team operations
- User isolation for personal data
- Profile access via `user_profile_access` table
- Credit wallet isolation per user

### Function Security
30+ database functions hardened with `SECURITY DEFINER` and `SET search_path = public, auth`.

### Remaining Manual Steps
- Enable auth leaked password protection in Supabase dashboard
- Configure auth OTP expiry to <= 1 hour

---

## Performance & Reliability

### Caching (Multi-Layer)
```
Application: AI Models (persistent), System Config (no expiry), Frequent Data (1h)
Redis:       Profiles (24h), Posts (12h), AI Results (7d), Analytics (6h),
             System Metrics (5m), Credit Balance (5m), Wallet (30m),
             Transactions (10m), Pricing Rules (1h)
```

### Database Indexes
80+ strategic indexes including:
- `idx_profiles_username_hash` (hash index for lookups)
- `idx_posts_profile_created` (profile_id, created_at DESC)
- `idx_posts_ai_analyzed` (ai_analyzed_at DESC)
- `idx_user_profile_access_user_profile` (user_id, profile_id, accessed_at DESC)

### Circuit Breakers
| Service | Failure Threshold | Cooldown |
|---------|-------------------|----------|
| Database | 3 failures | 30s |
| External API | 5 failures | 60s |
| AI Models | 4 failures | 120s |
| Cache | 3 failures | 15s |

### Retry Strategies
- Database: exponential backoff, 3 attempts, max 10s
- API: jittered backoff, 5 attempts, max 30s
- AI: extended backoff, 4 attempts, max 60s
- Cache: linear backoff, 3 attempts, max 2s

### Fallbacks
- Profile: cached data (up to 1h old) -> basic defaults
- AI: rule-based analysis -> neutral defaults
- System: graceful degradation -> queue for later

### Performance Targets
- Cached responses: <100ms
- Fresh responses: <2s
- Health check: <50ms
- AI throughput: 1,200 posts/hour background

---

## Cloudflare Integration

Custom MCP-style client (`app/integrations/cloudflare_mcp_client.py`) connected to `Partners@following.ae` account.

Key files:
- Client: `app/integrations/cloudflare_mcp_client.py`
- Routes: `app/api/cloudflare_mcp_routes.py`
- Config: `.claude/mcp_cloudflare_config.json`
- Test: `scripts/test_cloudflare_integration.py`
- Env var: `CF_MCP_API_TOKEN`

---

## Environment Configuration

```env
# Database & Supabase
DATABASE_URL=postgresql://user:pass@host/db
SUPABASE_URL=https://project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=...

# AI
AI_MODELS_CACHE_DIR=./ai_models
AI_BATCH_SIZE=16
AI_MAX_WORKERS=2
ENABLE_AI_ANALYSIS=true

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# External APIs
DECODO_API_KEY=...
SMARTPROXY_USERNAME=...
SMARTPROXY_PASSWORD=...

# Cloudflare
CF_MCP_API_TOKEN=...

# Discovery
DISCOVERY_ENABLED=true
DISCOVERY_MAX_CONCURRENT_PROFILES=3
DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY=1000
DISCOVERY_MIN_FOLLOWERS_COUNT=1000

# Monitoring
ENABLE_PERFORMANCE_MONITORING=true
MONITORING_ALERT_WEBHOOK=...
```

---

## Development Guidelines

- Type hints on all functions
- Async/await throughout
- Comprehensive error handling with logging
- Cache expensive operations (>100ms)
- All external dependencies need fallback strategies
- Background processing for long operations

---

## Key User Accounts
- **Brand User**: `client@analyticsfollowing.com` (Premium, 5K credits)
- **Admin User**: `zain@following.ae` (Admin, 100K credits)

---

## Update History
- **Jan 2025**: Creator search system completed, RLS hardening (21->1 advisories), database cleanup (removed 40+ unused tables), Cloudflare MCP integration, discovery system with background processing
- **Aug 2025**: Fixed auth mismatches, credit wallet sync, generated 128-endpoint API docs