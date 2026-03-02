# Analytics Following Backend

Instagram analytics platform backend. FastAPI + PostgreSQL (Supabase) + Redis + AI/ML pipeline.

## Tech Stack

- **Backend**: FastAPI (async), SQLAlchemy (async), asyncpg
- **Database**: PostgreSQL via Supabase (RLS enabled on all tables)
- **Cache**: Redis (profile 24h, posts 12h, AI results 7d)
- **Background**: Celery with Redis broker
- **AI Models**: HuggingFace transformers (sentiment, language detection, content classification)
- **CDN**: Cloudflare R2 for thumbnail storage
- **External API**: Decodo (Instagram data via Apify)
- **Auth**: Supabase Auth + JWT

## Project Structure

```
app/
  api/              # Route handlers (FastAPI routers)
  services/         # Business logic layer
    ai/             # AI model services
    background/     # Background processors (discovery, etc.)
  core/             # Config, settings, constants
  database/         # DB connection, session management
  models/           # SQLAlchemy models
  middleware/       # Auth, credit gates, rate limiting
  cache/            # Redis cache layer
  resilience/       # Circuit breakers, retry strategies
  integrations/     # Cloudflare, external API clients
  monitoring/       # Health checks, metrics
scripts/            # CLI tools (repair, discovery, debugging)
```

## Key Database Tables (19 active, Supabase project: `xyzltfollowinganalytics`)

| Group | Tables |
|-------|--------|
| Instagram | `profiles`, `posts`, `related_profiles` |
| Users | `users`, `auth_users`, `user_profile_access`, `user_roles` |
| Credits | `credit_packages`, `credit_wallets`, `credit_pricing_rules` |
| Teams | `teams`, `team_members`, `monthly_usage_tracking`, `team_profile_access` |
| CDN | `cdn_image_assets`, `cdn_image_jobs`, `cdn_processing_stats` |
| System | `system_configurations`, `list_templates` |

All tables have RLS policies and 80+ performance indexes.

## Core Data Pipeline

```
Instagram username -> Decodo/Apify API -> profiles + posts tables
  -> CDN processing (thumbnails to R2)
  -> AI analysis (sentiment, language, category per post)
  -> Profile-level AI aggregation
```

**New creator**: ~160s (full pipeline). **Unlocked creator**: <1s (DB fast path).

## Profile Completeness Criteria

A profile is "complete" when:
1. `followers_count > 0` and `posts_count > 0`
2. 12+ posts stored with AI analysis (`ai_content_category`, `ai_sentiment`, `ai_language_code`)
3. `ai_profile_analyzed_at IS NOT NULL`
4. 12+ posts have `cdn_thumbnail_url`
5. Demographics optional (not populated yet)

## Creator Analytics Response (5 sections)

Single endpoint: `GET /api/v1/search/creator/{username}`

1. **Overview**: Profile data, followers, engagement, AI content classification
2. **Audience**: Demographics, language distribution, authenticity, fraud detection
3. **Engagement**: Behavioral patterns, sentiment, post-level metrics
4. **Content**: Visual analysis, content distribution, trends, NLP
5. **Posts**: 12+ posts with individual AI analysis and CDN thumbnails

## Credit System

| Action | Cost |
|--------|------|
| Profile unlock | 25 credits (30-day access) |
| Post analytics | 5 credits |
| Discovery page | 1 credit |
| Email unlock | 1 credit |
| Campaign analysis | 10 credits |
| Bulk export | 50 credits |

Credit gate decorator: `@requires_credits("action_type")`

## Subscription Plans

| Plan | Price | Team | Monthly Profiles | Topup Discount |
|------|-------|------|-----------------|----------------|
| Free | $0 | 1 | 5 | 0% |
| Standard | $199 | 2 | 500 | 0% |
| Premium | $499 | 5 | 2,000 | 20% |

## Key API Route Prefixes

- `/auth/` - Authentication (Supabase)
- `/credits/` or `/api/v1/credits/` - Credit management
- `/instagram/` - Profile and post analytics
- `/api/v1/search/creator/` - Creator analytics
- `/api/v1/discovery/` - Profile discovery and browsing
- `/api/v1/cloudflare/` - Infrastructure monitoring
- `/api/v1/admin/repair/` - Admin profile repair tools
- `/api/health` - Health check
- `/settings/` - User settings

## AI Models

- **Sentiment**: `cardiffnlp/twitter-roberta-base-sentiment-latest`
- **Language**: `papluca/xlm-roberta-base-language-detection`
- **Classification**: `facebook/bart-large-mnli`

Models use singleton pattern with global caching. Background processing via Celery.

## Discovery System

Background processor auto-discovers similar profiles from `related_profiles` table. Hooks in:
- `main.py` - after creator analytics completes
- `comprehensive_service.py` - when related profiles are stored
- `post_analytics_service.py` - after post analysis

Config: `DISCOVERY_ENABLED`, max 3 concurrent, 1000/day rate limit, min 1K followers.

## User Accounts

- **Brand**: `client@analyticsfollowing.com` (Premium, 5K credits)
- **Admin**: `zain@following.ae` (Admin, 100K credits)

## Conventions

- All functions use type hints
- Async/await throughout
- Comprehensive error handling with logging
- Circuit breakers on all external dependencies
- Cache expensive operations (>100ms)
- RLS on every table; functions use `SECURITY DEFINER` with `SET search_path`

## Pending Work

- Stripe payment processing (infrastructure ready, not live)
- Auth leaked password protection (requires Supabase dashboard toggle)
- 31 unused tables available for cleanup
