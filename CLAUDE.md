# Analytics Following Backend

Instagram analytics & influencer management platform. FastAPI + Supabase + Redis + AI/ML.

## Tech Stack

- **Runtime**: FastAPI (async), SQLAlchemy (async), asyncpg
- **Database**: PostgreSQL via Supabase — project ref: `vkbuxemkprorqxmzzkuu`, region: `ap-south-1`
- **Cache**: Redis (profiles 24h, posts 12h, AI 7d)
- **Background**: Celery + Redis broker
- **AI**: HuggingFace transformers (sentiment, language, classification) — singleton pattern
- **CDN**: Cloudflare R2 (thumbnails)
- **External API**: Decodo/Apify (Instagram data)
- **Auth**: Supabase Auth + JWT, resilient auth service with caching
- **Payments**: Stripe (infrastructure ready, not live)

## Project Structure

```
app/
  api/              # Route handlers (FastAPI routers)
    admin/          # Superadmin routes (proposals, user mgmt, influencer DB)
  services/         # Business logic
    ai/             # AI model services (sentiment, language, classification)
  core/             # Config, settings, constants
  database/         # DB connection, session management, models (unified_models.py)
  middleware/       # Auth, credit gates, rate limiting, team auth, brand access
  workers/          # Background workers (AI, CDN, post analytics)
scripts/            # CLI tools
migrations/         # SQL migration scripts
```

## Key Database Tables

| Group | Tables |
|-------|--------|
| Instagram | `profiles`, `posts`, `related_profiles` |
| Users | `users`, `auth_users`, `user_profile_access`, `user_roles` |
| Credits | `credit_packages`, `credit_wallets`, `credit_pricing_rules` |
| Teams | `teams`, `team_members`, `monthly_usage_tracking`, `team_profile_access` |
| Proposals | `campaign_proposals`, `proposal_influencers` |
| Influencer CRM | `influencer_database` (master DB with cost/sell pricing per deliverable) |
| CDN | `cdn_image_assets`, `cdn_image_jobs`, `cdn_processing_stats` |
| System | `system_configurations`, `list_templates` |

All tables have RLS policies. Models defined in `app/database/unified_models.py`.

## Core Data Pipeline

```
Instagram username → Decodo/Apify API → profiles + posts
  → CDN (thumbnails → R2) → AI analysis (sentiment, language, category)
  → Profile-level aggregation
```

New creator: ~160s full pipeline. Unlocked creator: <1s DB fast path.

## Proposal System

Admin creates proposals for brands with curated influencer lists.

**Flow**: `draft → sent → in_review → approved/rejected/more_requested`

**Key files**:
- `app/api/campaign_proposal_routes.py` — brand-facing endpoints
- `app/api/admin/admin_proposal_routes.py` — admin CRUD
- `app/services/campaign_proposals_service.py` — business logic
- `app/database/unified_models.py` — `CampaignProposal`, `ProposalInfluencer`

**Per-influencer data**:
- Price snapshots frozen at creation (`sell_price_snapshot`, `cost_price_snapshot`)
- Custom overrides via `custom_sell_pricing`
- Brand selection: `selected_by_user`, `selected_deliverables` (JSONB array)
- 7 deliverable types: post, story, reel, carousel, video, bundle, monthly

**Pricing**: Stored as USD cents in `influencer_database` (`sell_post_usd_cents`, `cost_reel_usd_cents`, etc.). Sell pricing priority: `custom_sell_pricing > sell_price_snapshot > {}`.

## Credit System

| Action | Cost |
|--------|------|
| Profile unlock | 25 credits (30-day access) |
| Post analytics | 5 credits |
| Discovery page | 1 credit |
| Campaign analysis | 10 credits |
| Bulk export | 50 credits |

Decorator: `@requires_credits("action_type")`

## Subscription Plans

| Plan | Price | Team Size | Monthly Profiles |
|------|-------|-----------|-----------------|
| Free | $0 | 1 | 5 |
| Standard | $199 | 2 | 500 |
| Premium | $499 | 5 | 2,000 |

## Creator Analytics

"Creator Analytics" refers to the `/creator-analytics/[username]` page. It serves **two audiences**:
- **Brand users**: See analytics for unlocked creators (25 credits). No cost pricing, no internal notes.
- **Superadmin**: Sees the same analytics page PLUS a collapsible `SuperadminIMDPanel` showing cost/sell pricing, margins, tier, status, tags, internal notes, and an edit button — if the creator exists in the master database. Superadmins bypass the unlock gate entirely (no credits spent).

Key files:
- Backend: `main.py` (search endpoint), `app/services/creator_search_response_builder.py` (response builders)
- Frontend: `src/components/analytics/ComprehensiveCreatorAnalytics.tsx`, `creator-tabs/` (4 tabs), `SuperadminIMDPanel.tsx`

## Key API Routes

- `/api/v1/auth/` — Authentication, dashboard, unlocked profiles
- `/api/v1/credits/` — Credit wallet, pricing
- `/api/v1/search/creator/{username}` — Creator analytics (5 sections)
- `/api/v1/discovery/` — Profile browsing
- `/api/v1/campaigns/proposals` — Brand proposal views
- `/api/v1/campaigns/proposals/{id}/influencers` — Selection + deliverables
- `/api/v1/teams/` — Team management
- `/api/v1/admin/` — Superadmin operations
- `/health` — Health check

## User Accounts

- **Brand**: `client@analyticsfollowing.com` (Premium, 5K credits)
- **Brand**: `gabe@logitech.com` (Standard)
- **Admin**: `zain@following.ae` (Admin, 100K credits)

## Conventions

- Async/await throughout, type hints on all functions
- Circuit breakers on external dependencies
- RLS on every table; DB functions use `SECURITY DEFINER` with `SET search_path`
- Cache operations >100ms
- Auth: resilient auth service caches JWT validations and user sessions
- Never expose cost pricing to brands — only sell pricing (gated by `visible_fields`)
