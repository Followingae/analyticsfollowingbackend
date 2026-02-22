# Analytics Following Backend - Deployment & Architecture Analysis

**Date**: February 22, 2026
**Scope**: Full deployment readiness audit covering AI/ML operations, backend flows, cloud providers, billing system, and codebase architecture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Codebase State](#2-current-codebase-state)
3. [AI/ML Operations Analysis](#3-aiml-operations-analysis)
4. [Backend Flows & Service Dependencies](#4-backend-flows--service-dependencies)
5. [Billing & Stripe Integration](#5-billing--stripe-integration)
6. [Cloud Deployment Options](#6-cloud-deployment-options)
7. [Architecture: Current vs Industry Standard](#7-architecture-current-vs-industry-standard)
8. [Recommended Restructuring Plan](#8-recommended-restructuring-plan)
9. [Deployment Roadmap](#9-deployment-roadmap)
10. [Action Items Checklist](#10-action-items-checklist)

---

## 1. Executive Summary

The Analytics Following Backend is a feature-rich FastAPI application with AI-powered Instagram analytics, a credit-based monetization system, and B2B SaaS capabilities. While functionally complete, the project has significant architectural and security gaps that must be addressed before production deployment.

### Key Findings at a Glance

| Area | Status | Biggest Issue |
|------|--------|---------------|
| AI/ML Operations | Functional but risky | Models run in the API event loop, blocking all other requests |
| Backend Architecture | Working but monolithic | 2,808-line main.py, 192 files in flat directories, many duplicates |
| Billing/Stripe | ~75% complete | Plaintext passwords stored in Stripe metadata (critical security) |
| Containerization | Not started | No Dockerfile, docker-compose, or Procfile exists |
| Cloud Readiness | Not ready | Windows-specific code, no deployment configuration |

### Bottom Line

The application needs three things before it can be deployed:
1. **Security fixes** in the billing system (1-2 days)
2. **AI process separation** so inference stops blocking the API (2-3 days)
3. **Containerization** with Docker for any cloud deployment (1-2 days)

After that, **Google Cloud Run** is recommended as the primary deployment target at ~$320-420/month.

---

## 2. Current Codebase State

### Project Size

| Metric | Count |
|--------|-------|
| Total Python files in `app/` | 192 |
| API route files | 43 |
| Service files | 74 |
| Worker files | 9 |
| Database module files | 14 |
| Model definition files | 11 |
| Middleware files | 11 |
| Root-level test/utility scripts | 36 |
| Lines in main.py | 2,808 |
| Registered API routers | 32+ |
| Inline endpoints in main.py | 20+ |
| Total API endpoints | 128+ |
| Active database tables | 19 |

### Current Directory Structure

```
analyticsfollowingbackend/
├── main.py                    (2,808 lines - app init, routes, workers, business logic)
├── app/
│   ├── api/                   (43 files - all route handlers in flat directory)
│   │   ├── billing_routes.py
│   │   ├── billing_routes_old.py
│   │   ├── stripe_checkout_routes.py
│   │   ├── stripe_subscription_routes.py
│   │   ├── stripe_webhook_routes.py
│   │   ├── admin_billing_routes.py
│   │   ├── ... (37 more route files)
│   │   └── admin/             (6 admin route files)
│   ├── services/              (74 files - all business logic in flat directory)
│   │   ├── production_r2_service.py
│   │   ├── real_r2_upload_service.py
│   │   ├── real_mcp_r2_service.py
│   │   ├── standard_r2_service.py
│   │   ├── working_mcp_r2_service.py
│   │   ├── r2_upload_service.py      (6 R2 service variants!)
│   │   ├── stripe_service.py
│   │   ├── stripe_billing_service.py
│   │   ├── stripe_subscription_service.py  (3 Stripe service variants!)
│   │   ├── ... (65 more service files)
│   │   └── ai/components/    (3 AI component files)
│   ├── database/              (14 files)
│   │   ├── comprehensive_service.py   (104,916 bytes - largest file)
│   │   ├── unified_models.py          (98,285 bytes)
│   │   ├── pgbouncer_absolute_fix.py
│   │   ├── pgbouncer_dialect.py
│   │   ├── pgbouncer_fix.py
│   │   ├── pgbouncer_global_fix.py
│   │   ├── pgbouncer_session.py
│   │   ├── pgbouncer_ultimate_fix.py  (6 PGBouncer fix variants!)
│   │   └── ...
│   ├── workers/               (9 files - spawned as subprocesses from main)
│   ├── models/                (11 Pydantic/SQLAlchemy model files)
│   ├── middleware/            (11 middleware files)
│   ├── core/                  (5 config files)
│   ├── monitoring/            (4 files)
│   ├── resilience/            (4 files)
│   ├── scrapers/              (5 files)
│   ├── cache/                 (2 files)
│   ├── infrastructure/        (2 files)
│   ├── integrations/          (1 file)
│   ├── utils/                 (4 files)
│   └── tasks/                 (2 files)
├── 36 loose test/utility scripts in root (create_test_user.py, fix_zeek_user.py, etc.)
└── No Dockerfile, docker-compose.yml, or Procfile
```

### Identified Duplication

| Component | Duplicated Files | Should Be |
|-----------|-----------------|-----------|
| R2/CDN Storage | 6 service variants | 1 unified storage service |
| Stripe/Billing | 3 service files + 3 webhook endpoints + 5 route files | 1 service + 1 webhook + 1 route file |
| PGBouncer | 6 fix/workaround files | 1 dialect override |
| Post Analytics | 3 service variants (`post_analytics_service.py`, `dedicated_post_analytics_service.py`, `standalone_post_analytics_service.py`) | 1 service |

---

## 3. AI/ML Operations Analysis

### All 10 AI Models Inventory

The system uses 10 AI models split into two tiers:

#### Tier 1: Heavy Transformer Models (loaded at startup, permanently cached)

| Model | HuggingFace ID | Disk | RAM | Latency/Post |
|-------|---------------|------|-----|-------------|
| Sentiment Analysis | `cardiffnlp/twitter-roberta-base-sentiment-latest` | ~500MB | ~500MB | 200-500ms |
| Language Detection | `papluca/xlm-roberta-base-language-detection` | ~1.1GB | ~1.1GB | 200-500ms |
| Content Classification | `facebook/bart-large-mnli` | ~1.6GB | ~1.6GB | 1-2s **(bottleneck)** |

#### Tier 2: Lightweight/Statistical Models (loaded on first use)

| Model | Libraries | RAM | Latency |
|-------|----------|-----|---------|
| Audience Quality | scikit-learn (IsolationForest, KMeans) | ~50MB | <500ms |
| Visual Content | torchvision ResNet50 + OpenCV | ~100MB | 2-5s/image |
| Audience Insights | geopy + pycountry + HDBSCAN + UMAP | ~50MB | <1s |
| Trend Detection | Prophet + scipy + river | ~150MB | 1-3s |
| Advanced NLP | SentenceTransformer `all-MiniLM-L6-v2` + spaCy + NLTK | ~95MB | 500ms-1s |
| Fraud Detection | IsolationForest + heuristic rules | ~50MB | <500ms |
| Behavioral Patterns | KMeans + statistical analysis | ~50MB | <500ms |

### Memory Requirements

| Scenario | RAM Needed |
|----------|-----------|
| Minimum (all models loaded) | ~4.0 GB |
| Peak (concurrent inference) | ~6.5-8.0 GB |
| With PyTorch framework overhead | +1.5 GB |
| With unnecessary TensorFlow import | +1.5 GB (wasted) |
| **Realistic production minimum** | **8-10 GB** |
| **Recommended** | **12-16 GB** |

### Model Loading Architecture (5 layers)

```
Layer 1: AIManagerSingleton
  └── Loads 3 core HuggingFace models at startup
  └── Uses threading.Lock + asyncio.Lock
  └── Calls SystemExit if any core model fails

Layer 2: AIManagerWrapper
  └── Re-exports singleton instance

Layer 3: ComprehensiveAIManager
  └── Manages all 10 models with retry configs
  └── Lazy-loads advanced models (4-10)

Layer 4: ProductionAIOrchestrator
  └── Full pipeline coordination
  └── 5-minute processing timeout
  └── 70% success threshold (7/10 models must succeed)

Layer 5: BulletproofContentIntelligence
  └── Top-level service combining everything
  └── Batch processing (batch_size=10)
```

### Critical AI Issues

#### Issue 1: AI Blocks the API Event Loop (CRITICAL)

**What's happening**: All 10 AI models are loaded directly into the FastAPI process. When a user triggers creator analytics, the AI inference runs synchronously in the async event loop. During the ~60-160 seconds of AI processing, **all other API requests are delayed or blocked**.

**Why it matters**: If 5 users trigger new creator searches simultaneously, the 6th user's health check or profile lookup will be slow or timeout.

**What the industry does**: Run AI inference in a separate process - either via Celery workers (your Celery is set up but AI doesn't actually use it) or a dedicated inference service (BentoML, Ray Serve, Triton).

#### Issue 2: No Model Memory Management

**What's happening**: Once a model is loaded, it stays in RAM forever. All 10 models are cached permanently with no unloading mechanism.

**Why it matters**: The application consumes 8-16 GB of RAM at all times, even when no AI processing is happening.

#### Issue 3: TensorFlow Imported but Unused

**What's happening**: `ai_manager_singleton.py` imports TensorFlow solely to suppress logging warnings. TensorFlow is not used for any inference.

**Why it matters**: Adds ~1.0-1.5 GB of unnecessary RAM. Removing this single import saves significant memory.

#### Issue 4: GPU Code Exists but Is Disabled

**What's happening**: The code detects GPU availability (`torch.cuda.is_available()`) but all model configs hardcode `device='cpu'`. Even on a GPU machine, all inference runs on CPU.

**Why it matters**: GPU would provide 5-10x speedup for BART-large (the bottleneck model). Simply changing the config could dramatically improve performance.

#### Issue 5: Cold Start Downloads 3.5 GB of Models

**What's happening**: HuggingFace models are downloaded at runtime on first startup. This takes 5-10 minutes.

**Why it matters**: Container restarts or scaling events will have very long cold starts unless models are pre-downloaded during the Docker build.

#### Issue 6: `face-recognition` + `dlib` Dependencies

**What's happening**: `requirements-ai.txt` includes `face-recognition` and `dlib`, which require C++ build tools (cmake, gcc). However, the actual visual content analysis code uses OpenCV's Haar cascades instead.

**Why it matters**: These are likely unused dependencies that make Docker builds harder and slower. They should be verified and removed if unused.

### Compute Recommendations

| Deployment Type | CPU | RAM | Disk | Cost (AWS) |
|----------------|-----|-----|------|-----------|
| Minimum Viable (CPU-only) | 4 vCPU | 12-16 GB | 20 GB | m6i.xlarge ~$140/mo |
| Recommended Production (CPU) | 8 vCPU | 32 GB | 50 GB | m6i.2xlarge ~$280/mo |
| GPU-Accelerated | 4 vCPU + T4 GPU | 16 GB | 50 GB | g4dn.xlarge ~$384/mo |

**Recommendation**: Start with CPU-only deployment. The current workload (~1,200 posts/hour background) is manageable on CPU. Add GPU later if throughput becomes a bottleneck.

---

## 4. Backend Flows & Service Dependencies

### Service Topology

```
FastAPI App (single process, port 8080)
  │
  ├── In-Process Components
  │   ├── 10 AI Models (permanently cached in memory)
  │   ├── Post Analytics Worker (asyncio task)
  │   ├── System Monitor (asyncio task)
  │   └── Discovery Background Processor (asyncio task)
  │
  ├── Subprocess Workers (spawned at startup by main app)
  │   ├── Celery AI Worker (--pool=solo, --concurrency=1)
  │   ├── Celery CDN Worker (--pool=solo, --concurrency=1)
  │   └── Celery Discovery Worker (--pool=solo, --concurrency=1)
  │
  ├── External Services (REQUIRED)
  │   ├── PostgreSQL via Supabase (remote, 315 pooled connections)
  │   ├── Redis (localhost:6379, DB 0 broker + DB 1 results + caching)
  │   ├── Apify/Decodo API (Instagram data scraping)
  │   ├── Cloudflare R2 (CDN image storage, thumbnails-prod bucket)
  │   ├── Stripe API (billing and subscriptions)
  │   └── Supabase Auth (JWT authentication)
  │
  └── External Services (OPTIONAL)
      └── Cloudflare API (infrastructure monitoring)
```

### Complete External Dependencies

#### A. PostgreSQL via Supabase (CRITICAL)

- **Connection**: Direct to `db.vkbuxemkprorqxmzzkuu.supabase.co` on port 5432
- **Driver**: asyncpg via SQLAlchemy async engine
- **Connection Pools**: 4 isolated pools totaling ~315 connections:
  - `user_api`: 100 connections + 50 overflow
  - `background_workers`: 80 + 20 overflow
  - `ai_workers`: 30 + 10 overflow
  - `discovery_workers`: 20 + 5 overflow
- **Concern**: 315 connections is high - Supabase Pro plans typically allow ~500. This leaves little headroom.

#### B. Redis (CRITICAL - blocks startup)

- **Usage**: Celery broker (DB 0), Celery results (DB 1), application caching, distributed locks, job queues
- **Connection Pool**: max_connections=20
- **Startup Behavior**: App calls `SystemExit` if Redis ping fails. Redis must be available before the app starts.

#### C. Celery Workers (CRITICAL - blocks startup)

- **Broker Test**: Runs during startup initialization, blocks if unavailable
- **Workers**: Spawned as subprocesses via `subprocess.Popen` from the main app
- **Worker Types**: AI analysis, CDN processing, Discovery
- **Configuration**: All use `--pool=solo --concurrency=1`

#### D. Apify/Decodo (REQUIRED for new profiles)

- **Actor**: `apify/instagram-scraper`
- **Auth**: `APIFY_API_TOKEN`
- **Data**: 12 posts, 10 related profiles, 12 reels per request
- **Retry**: Exponential backoff, 3 attempts

#### E. Cloudflare R2 (REQUIRED for CDN)

- **Client**: boto3 (S3-compatible)
- **Bucket**: `thumbnails-prod`
- **CDN URL**: `https://cdn.following.ae`
- **Operations**: Profile avatar and post thumbnail storage

#### F. Stripe (REQUIRED for billing)

- **Client**: `stripe` Python SDK (in some files) + raw HTTP `requests` (in others)
- **Mode**: Currently using test keys (`sk_test_...`)
- **Products**: Free, Standard ($199/mo), Premium ($499/mo) with monthly and annual pricing

### Creator Analytics Pipeline (The ~160s Flow)

This is the core user-facing operation. When a user searches for a new creator:

```
Step 1: User Request
  POST /api/v1/simple/creator/search/{username}

Step 2: Database Check
  ├── Profile exists + unlocked? → Return from DB (<1s) ✅
  ├── Profile exists + locked? → Return preview data
  └── Profile missing/incomplete? → Continue to full pipeline ↓

Step 3: Acquire Redis Lock (5min expiry, prevents duplicate processing)

Step 4: Apify/Decodo API Call (~30-60s)
  └── Fetches: profile data + 12 posts + 10 related profiles + 12 reels

Step 5: Store in Database
  └── Profile + posts + related profiles saved

Step 6: Unified Processing (BLOCKING - runs in API event loop)
  ├── CDN Processing (~20-30s)
  │   └── Download images → Optimize → Upload to Cloudflare R2
  │   └── Profile avatar + 12 post thumbnails
  │
  └── AI Processing (~60-90s)
      ├── Sentiment Analysis (RoBERTa) × 12 posts
      ├── Language Detection (XLM-RoBERTa) × 12 posts
      ├── Content Classification (BART-large) × 12 posts  ← slowest
      ├── Visual Content Analysis (ResNet50) × 12 posts
      ├── Advanced NLP (spaCy + SentenceTransformer) × 12 posts
      ├── Audience Quality (per profile)
      ├── Audience Insights (per profile)
      ├── Trend Detection (per profile)
      ├── Fraud Detection (per profile)
      └── Behavioral Patterns (per profile)

Step 7: Release Redis Lock

Step 8: Create UserProfileAccess (30-day unlock)

Step 9: Return Complete Profile + Posts + AI Analysis + CDN URLs
```

**Total time**: ~160 seconds for a brand new creator. This entire pipeline runs synchronously in the HTTP request handler.

### Startup Sequence (Critical Order)

```
1.  setup_logging()
2.  init_database()                  → SQLAlchemy async engine + Supabase client
3.  auth_service.initialize()        → Supabase auth + Redis cache
4.  startup_service.initialize():
    4a. AI Manager singleton         → Loads 3 HuggingFace models (30-60s)
    4b. Redis + Celery validation    → BLOCKS if unavailable
    4c. Content Intelligence init
    4d. Creator Search check
    4e. Database Services validation
    4f. Network Health Monitor start
5.  optimized_pools.initialize()     → Creates 4 DB connection pools
6.  job_queue.initialize()           → Redis priority job queue
7.  Redis connection validation      → SystemExit if unavailable
8.  start_monitoring_loop()          → Background asyncio task
9.  worker_manager.start_all_workers() → Spawns Celery subprocesses
10. post_analytics_worker.start()    → Background asyncio task
```

**Startup time**: 30-60 seconds minimum (dominated by AI model loading). On first-ever start with no model cache: 5-10 minutes (model downloads).

### Environment Variables Required (40+)

```env
# Database & Supabase (REQUIRED)
DATABASE_URL=postgresql://...
DIRECT_DATABASE_URL=postgresql://...
SUPABASE_URL=https://project.supabase.co
SUPABASE_KEY=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# Redis & Celery (REQUIRED)
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# External APIs (REQUIRED)
APIFY_API_TOKEN=...

# Stripe (REQUIRED for billing)
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_FREE_MONTHLY_PRICE_ID=price_...
STRIPE_STANDARD_MONTHLY_PRICE_ID=price_...
STRIPE_STANDARD_ANNUAL_PRICE_ID=price_...
STRIPE_PREMIUM_MONTHLY_PRICE_ID=price_...
STRIPE_PREMIUM_ANNUAL_PRICE_ID=price_...
STRIPE_STARTER_TOPUP_PRICE_ID=price_...
STRIPE_PROFESSIONAL_TOPUP_PRICE_ID=price_...
STRIPE_ENTERPRISE_TOPUP_PRICE_ID=price_...

# Cloudflare R2 CDN (REQUIRED)
CF_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=thumbnails-prod
R2_ENDPOINT=https://{account}.r2.cloudflarestorage.com
CDN_BASE_URL=https://cdn.following.ae

# Cloudflare Monitoring (OPTIONAL)
CF_MCP_API_TOKEN=...
CF_ZONE_ID=...

# Application Config (with defaults)
API_HOST=0.0.0.0
PORT=8080
DEBUG=false
JWT_SECRET_KEY=...
FRONTEND_URL=https://app.following.ae
AI_MODELS_CACHE_DIR=./ai_models
ENABLE_AI_ANALYSIS=true

# Discovery
DISCOVERY_ENABLED=true
DISCOVERY_MAX_CONCURRENT_PROFILES=3
DISCOVERY_RATE_LIMIT_PROFILES_PER_DAY=1000
```

### Deployment Concerns

1. **No Docker configuration exists** - No Dockerfile, docker-compose, or Procfile.
2. **Everything runs in one process** - API server, AI models, and worker subprocess spawning all happen in the same process.
3. **Windows-specific code** - `CREATE_NEW_PROCESS_GROUP` flag in worker auto-manager won't work on Linux.
4. **Long-running synchronous requests** - The 160s creator pipeline blocks the HTTP connection. No WebSocket or polling pattern for progress updates.
5. **Redis is a hard dependency** - Application won't start without it. No graceful degradation.
6. **315 database connections** - This is aggressive and may exceed Supabase plan limits.
7. **No health check for readiness** - The existing `/health` endpoint doesn't account for model loading state during startup.

---

## 5. Billing & Stripe Integration

### Implementation Status: ~75% Complete

#### What's Fully Working (Credit System ~95%)

The internal credit system is production-ready with enterprise-grade features:

- **7 database tables** with RLS policies: `credit_packages`, `credit_wallets`, `credit_pricing_rules`, `credit_transactions`, `credit_usage_tracking`, `credit_top_up_orders`, `unlocked_influencers`
- **Row-level locking** for double-spend prevention via `update_wallet_balance()` PL/pgSQL function
- **Atomic transactions** with balance_before/balance_after audit trail
- **Two credit gate implementations**: standard (`@requires_credits`) and bulletproof atomic (`@atomic_requires_credits`)
- **Free allowance tracking** per action type per month
- **3 credit services**: `CreditWalletService`, `CreditTransactionService`, `CreditPricingService`

#### What's Partially Working (Stripe ~65%)

| Feature | Status |
|---------|--------|
| Checkout session creation | Working (embedded + redirect modes) |
| Subscription create/upgrade/downgrade/cancel | Working |
| Customer Portal sessions | Working |
| Webhook event handling (6 event types) | Working but insecure |
| Monthly credit reset on payment | Working |
| Pre-registration payment-first flow | Working but has security issues |
| Free-tier registration | Working |
| Topup payment links | Partially working |
| Webhook signature verification | NOT IMPLEMENTED |
| Email notifications | TODO stubs only |

### Critical Security Issues (MUST FIX)

#### 1. Plaintext Password in Stripe Metadata (CRITICAL)

**File**: `billing_routes.py:217`
```python
'password': request.password,  # Note: In production, hash this or use a temporary token
```

The user's plaintext password is stored in Stripe checkout session metadata. This means:
- Anyone with Stripe dashboard access can see user passwords
- The password is stored in Stripe's systems indefinitely
- It's retrieved later via webhook/verify-session to create the account

**Why this is required to fix**: This is a PCI compliance violation and a fundamental security breach. If Stripe's dashboard is accessed by unauthorized personnel, all user passwords are exposed.

**Fix**: Use a temporary encrypted token or server-side session store. Generate a random token, store the password hash server-side keyed to that token, and pass only the token in Stripe metadata.

#### 2. Webhook Signature Verification Disabled (CRITICAL)

**File**: `billing_routes.py:285-289`
```python
elif os.getenv("DEBUG", "true").lower() == "true":
    # Development mode - parse without verification
    event = json.loads(payload)
```

The `DEBUG` environment variable defaults to `"true"`, which means webhook signature verification is **skipped by default**. Anyone can POST fake webhook events to create accounts or manipulate billing state.

**File**: `stripe_webhook_routes.py:42-43`
```python
# TODO: Implement signature verification when webhook secret is available
logger.warning("Webhook signature verification not implemented")
```

The main webhook handler at `/api/v1/stripe/webhook` has a TODO and never verifies signatures.

**Why this is required to fix**: Without signature verification, an attacker can forge webhook events to: create unauthorized accounts, grant free subscriptions, reset credit balances, or manipulate billing state.

**Fix**: Set `STRIPE_WEBHOOK_SECRET` from the Stripe dashboard, change `DEBUG` default to `"false"`, and implement `stripe.Webhook.construct_event()` in all webhook handlers.

#### 3. Hardcoded Fallback Password (HIGH)

**File**: `billing_routes.py:352,472,512`
```python
password = metadata.get('password') or 'Following0925_25'
```

If the password is missing from Stripe metadata, a hardcoded default password (`Following0925_25`) is used for account creation. This is the same password documented in CLAUDE.md for the admin account.

**Why this is required to fix**: Any user whose password metadata is lost during Stripe processing gets a known password. This password is also the admin password, creating an escalation path.

**Fix**: If the password is missing, fail the account creation gracefully and ask the user to set a password via email link. Never use a hardcoded fallback.

#### 4. Three Overlapping Webhook Endpoints (HIGH)

The system registers three separate Stripe webhook endpoints:

| Endpoint | File | Purpose |
|----------|------|---------|
| `POST /api/v1/billing/webhook/complete-registration` | `billing_routes.py` | New user registration |
| `POST /api/v1/billing/webhook` | `billing_routes_old.py` | Existing user management |
| `POST /api/v1/stripe/webhook` | `stripe_webhook_routes.py` | All subscription events |

**Why this is required to fix**: Stripe needs to be configured to call specific endpoints. Having three creates confusion about which endpoint handles which event, makes debugging difficult, and increases the surface area for security issues.

**Fix**: Consolidate into a single `/api/v1/stripe/webhook` endpoint that routes events to the appropriate handler internally.

#### 5. Raw HTTP Instead of Stripe SDK (MEDIUM)

`stripe_service.py` implements its own HTTP client using the `requests` library instead of the official `stripe` Python SDK. This misses automatic retry logic, idempotency, and API version management built into the SDK.

**Why this is required to fix**: The official SDK handles edge cases (rate limiting, retries, API versioning) that are easy to get wrong with raw HTTP.

**Fix**: Consolidate all three Stripe service files into one that uses the official `stripe` SDK exclusively.

### Stripe Configuration Needed for Production

| Item | Status |
|------|--------|
| Switch to live Stripe keys (`sk_live_...`) | Pending |
| Configure webhook endpoint in Stripe dashboard | Pending |
| Set `STRIPE_WEBHOOK_SECRET` | Pending |
| Set `DEBUG=false` in production | Pending |
| Configure Customer Portal in Stripe | Pending |
| Subscribe to required webhook events | Pending |
| Set up monitoring for failed webhooks | Pending |
| Test full registration flow end-to-end | Pending |
| Enable Stripe smart retries for failed payments | Pending |

### Recent Bug Fix (2026-02-22)

A critical bug was fixed today (in uncommitted changes to `billing_routes.py`):
- **Issue**: New users registering via Stripe ended up without `team_member` records or `credit_wallet`
- **Root cause**: Missing rollback handling, "user exists" paths skipping provisioning, wrong column names
- **Fix**: New `_ensure_team_and_wallet()` idempotent helper called from all registration paths
- **Impact**: 5 orphaned teams were manually deleted from the database

---

## 6. Cloud Deployment Options

### Workload Profile

The application requires 3 distinct container services:

| Service | CPU | RAM | Purpose |
|---------|-----|-----|---------|
| API Service | 2 vCPU | 4 GB | FastAPI with uvicorn, handles all HTTP requests |
| Background Workers | 2 vCPU | 4 GB | Celery workers for CDN processing, discovery |
| AI Workers | 4 vCPU | 8 GB | AI model inference (sentiment, language, classification) |

Plus supporting infrastructure:
- **Redis**: 2 GB (caching + Celery broker)
- **PostgreSQL**: Hosted on Supabase (external, not self-hosted)
- **Persistent storage**: AI model cache (~5-10 GB)

### Provider Comparison Matrix

#### Tier 1: Full Cloud Providers

| Feature | AWS (ECS) | Google Cloud (Cloud Run) | Azure (Container Apps) |
|---------|-----------|-------------------------|----------------------|
| **Container Support** | ECS/Fargate/EKS | Cloud Run / GKE | ACA / AKS |
| **GPU Availability** | EC2 g4dn/g5 (NOT Fargate) | L4 GPU with scale-to-zero | T4/A100 serverless |
| **Managed Redis** | ElastiCache (~$50/mo) | Memorystore (~$65/mo) | Azure Cache (~$50/mo) |
| **Auto-scaling** | ECS Service Auto Scaling | Automatic (incl. to zero) | KEDA-based |
| **Middle East Region** | UAE (me-central-1) | Doha, Qatar (me-central-1) | Dubai (UAE North) |
| **Complexity** | High | Medium | Medium-High |
| **Best For** | Enterprise / UAE compliance | Cost optimization / simplicity | .NET shops / Azure ecosystem |

#### Tier 2: Simplified Platforms

| Feature | Railway | Render | Fly.io | DigitalOcean |
|---------|---------|--------|--------|-------------|
| **GPU** | RTX Pro ($0.66/hr) | A100 ($1.35/hr) | Removed (Aug 2025) | GPU Droplets |
| **Redis** | One-click (~$10/mo) | Built-in Key Value | Upstash integration | Managed (~$30/mo) |
| **Auto-scaling** | Manual only | Pro+ plan | Machine auto-stop | Dedicated plan |
| **ME Region** | None | None | None | None |
| **Deploy** | Git push | Git push | flyctl / Git | Git push |
| **Best For** | Dev/staging | Simple production | Global edge | Familiar/simple |

### Monthly Cost Estimates (CPU-only Production)

| Platform | Compute | Redis | LB/Network | Total/month |
|----------|---------|-------|-----------|-------------|
| **Google Cloud Run** | ~$220 | ~$65 | ~$20 | **~$320** |
| **Render** | ~$260 | ~$25 | Included | **~$285** |
| **Railway** | ~$290 | ~$10 | Included | **~$300** |
| **DigitalOcean** | ~$250 | ~$30 | ~$12 | **~$302** |
| **Azure Container Apps** | ~$250 | ~$50 | ~$25 | **~$340** |
| **AWS ECS/EC2** | ~$280 | ~$50 | ~$30 | **~$380** |
| **AWS ECS/Fargate** | ~$350 | ~$50 | ~$30 | **~$450** |

### With GPU for AI Workers

| Platform | GPU Cost (8hr/day active) | Total with GPU |
|----------|--------------------------|---------------|
| **Google Cloud Run (L4)** | ~$100/mo (scales to zero!) | **~$420** |
| **Railway (RTX Pro)** | ~$158/mo | **~$458** |
| **Azure ACA (T4)** | ~$150/mo | **~$490** |
| **AWS EC2 (g4dn.xlarge)** | ~$384/mo (always on) | **~$764** |
| **AWS EC2 Spot** | ~$115/mo (70% savings) | **~$495** |

### Recommended Architecture: Google Cloud Run

```
                    Cloud DNS (following.ae)
                           │
                    Cloud Load Balancer (managed SSL)
                           │
              ┌────────────┼────────────┐
              │            │            │
    Cloud Run (API)  Cloud Run (API)    │
    2 vCPU / 4 GiB  2 vCPU / 4 GiB     │
    min 1 instance   auto-scale         │
              │            │            │
              └────────┬───┘            │
                       │                │
                Memorystore Redis       │
                  (2 GB Basic)          │
                       │                │
              ┌────────┴───┐            │
              │            │            │
    Cloud Run          Cloud Run        │
    (Workers)          (AI + L4 GPU)    │
    2 vCPU/4GiB        8 vCPU/32GiB    │
    scales to zero     scales to zero   │
              │            │            │
              └────────┬───┘            │
                       │                │
              Supabase PostgreSQL       │
              (external, managed)       │
                                        │
              Cloudflare R2 (CDN)───────┘
```

**Why Google Cloud Run is recommended**:

1. **Scale-to-zero GPU**: The only platform where AI workers with L4 GPU can scale to zero when idle. You pay $0 when no AI processing is happening, vs $384/month always-on on AWS.
2. **Closest Middle East region**: Doha (me-central-1) is ~250 miles from UAE, providing acceptable latency for the following.ae audience.
3. **Serverless simplicity**: No cluster management, automatic scaling, managed SSL.
4. **Cost-effective**: $320/mo without GPU, $420/mo with GPU.
5. **Low lock-in**: Cloud Run is based on Knative - containers are portable to any platform.
6. **Supabase compatibility**: Works seamlessly with external PostgreSQL databases.

**When to choose AWS instead**: If UAE data residency is required (AWS has `me-central-1` in the UAE), or if you need enterprise compliance certifications that only AWS provides in the region.

### Recommended Phased Deployment

| Phase | Platform | Cost/mo | Purpose |
|-------|----------|---------|---------|
| Phase 1 | Railway | ~$50-100 | Development and staging environment |
| Phase 2 | Google Cloud Run (Doha) | ~$320-420 | Production launch |
| Phase 3 | AWS ECS (UAE) | ~$450-600 | Only if UAE data residency is required |

---

## 7. Architecture: Current vs Industry Standard

### How Well-Structured FastAPI+AI Projects Look

The industry has converged on a **feature/domain-based** architecture for large FastAPI applications. This is used by Netflix Dispatch, recommended by the popular [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) guide (14k+ stars), and followed by major open-source projects like Open WebUI (70k+ stars).

### Side-by-Side Comparison

#### main.py

| Your Project | Industry Standard |
|-------------|-------------------|
| 2,808 lines | <100 lines |
| 20+ inline endpoint definitions | Zero inline endpoints |
| Business logic mixed in | App factory + router registration only |
| Worker spawning logic | Workers are separate processes/containers |
| Service initialization code | Delegated to lifespan handler |

**Why this matters**: A 2,800-line main.py is nearly impossible to navigate, test, or maintain. Every change risks breaking unrelated functionality. The industry keeps main.py as a thin "composition root" that just wires things together.

#### Directory Organization

| Your Project | Industry Standard |
|-------------|-------------------|
| File-type grouping: all routes in `api/`, all services in `services/` | Domain grouping: each feature gets its own package |
| 43 route files in one flat directory | Each domain has its own `router.py` |
| 74 service files in one flat directory | Each domain has its own `service.py` |
| Related files are spread across directories | Related files are co-located |

**Why this matters**: When you need to modify the credit system, you currently have to look in `api/credit_routes.py`, `services/credit_wallet_service.py`, `services/credit_pricing_service.py`, `services/credit_transaction_service.py`, `middleware/credit_gate.py`, `middleware/atomic_credit_gate.py`, and `models/credits.py` - files scattered across 4 different directories. In a domain-based structure, everything credit-related lives in `credits/`.

**Industry-standard structure**:

```
app/
├── main.py                      # <100 lines
├── api/router.py                # Router aggregation
│
├── auth/                        # Auth domain
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── dependencies.py
│
├── instagram/                   # Instagram analytics domain
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── scraper.py
│
├── ai/                          # AI inference domain
│   ├── manager.py
│   ├── sentiment.py
│   ├── language.py
│   ├── classifier.py
│   ├── orchestrator.py
│   └── tasks.py                 # Celery task definitions
│
├── credits/                     # Credits domain
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   ├── gate.py
│   └── models.py
│
├── billing/                     # Stripe billing domain
│   ├── router.py
│   ├── service.py               # ONE service (using SDK)
│   └── webhooks.py              # ONE webhook handler
│
├── discovery/
├── cdn/
├── teams/
├── admin/
│
├── core/                        # Shared infrastructure
│   ├── config.py                # pydantic-settings
│   ├── database.py              # Engine + get_db
│   ├── redis.py
│   ├── celery.py
│   └── security.py
│
└── common/                      # Shared utilities
    ├── pagination.py
    ├── cache.py
    └── resilience.py
```

#### AI Inference

| Your Project | Industry Standard |
|-------------|-------------------|
| Models loaded into API process | Models in separate process/service |
| Inference blocks the event loop | Inference is async via queue or gRPC |
| No batching for concurrent requests | Micro-batching for GPU efficiency |
| All models always in memory | Lazy loading or dedicated model server |

**Why this matters**: When AI inference runs in the API process, a 60-second sentiment analysis blocks the entire API from handling other requests. Industry practice is to run inference in a separate worker (Celery, Ray Serve, BentoML, or Triton) so the API stays responsive.

#### Configuration Management

| Your Project | Industry Standard |
|-------------|-------------------|
| Scattered `os.getenv()` calls | Nested `pydantic-settings` with validation |
| No type checking on env vars | Full type checking + defaults |
| Config read on every access | `@lru_cache` for single read |

**Industry-standard pattern**:
```python
# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")
    url: str
    pool_size: int = 20

class Settings(BaseSettings):
    db: DatabaseSettings = DatabaseSettings()
    redis_url: str = "redis://localhost:6379"
    debug: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

#### Worker Deployment

| Your Project | Industry Standard |
|-------------|-------------------|
| Workers spawned as subprocesses from main app | Workers are separate containers/services |
| Windows-specific subprocess flags | Platform-agnostic Docker containers |
| Can't scale workers independently | Workers scale independently from API |

**Why this matters**: When workers run as subprocesses of the API, you can't scale them independently. If you need more AI processing power, you have to scale the entire API. In production, workers should be separate Docker services that can be scaled based on queue depth.

#### Database Sessions

| Your Project | Industry Standard |
|-------------|-------------------|
| 4 separate connection pools (315 total connections) | Single pool with `get_db()` dependency |
| Multiple pool strategies | One pool, sensible defaults (pool_size=20, max_overflow=10) |
| 6 PGBouncer workaround files | 1 dialect override if needed |

### Real-World Projects to Study

| Project | Stars | Key Pattern |
|---------|-------|-------------|
| [Open WebUI](https://github.com/open-webui/open-webui) | 70k+ | FastAPI + AI, domain routers, factory pattern |
| [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) | 14k+ | Feature-based structure guide (Netflix-inspired) |
| [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | 30k+ | Official FastAPI template |
| [BentoML](https://github.com/bentoml/BentoML) | 7k+ | ML model serving framework |

---

## 8. Recommended Restructuring Plan

### Approach: Incremental Refactor (Lowest Risk)

The codebase works. The goal is to restructure without breaking functionality. This means moving files gradually, one domain at a time, while keeping the application running.

### Phase 1: Slim Down main.py (Day 1)

**Goal**: Reduce main.py from 2,808 lines to <100 lines.

**Steps**:
1. Extract all 20+ inline endpoint definitions to their appropriate domain router files
2. Move the bulletproof creator search endpoints (lines 870-1963) to `instagram/router.py`
3. Move system stats endpoints to `admin/router.py`
4. Move worker initialization to a `core/startup.py` module
5. Create `api/router.py` as a single aggregation point for all routers
6. main.py becomes: app factory + lifespan + middleware + single `include_router` call

**Result**: main.py is a clean composition root that anyone can read in 2 minutes.

### Phase 2: Consolidate Duplicates (Day 2-3)

**Goal**: Eliminate duplicate implementations that cause confusion and maintenance burden.

| Consolidation | From | To |
|--------------|------|-----|
| R2/CDN Storage | 6 service files | 1 unified `cdn/service.py` |
| Stripe Billing | 3 service files + 5 route files | 1 `billing/service.py` + 1 `billing/router.py` |
| Stripe Webhooks | 3 webhook endpoints | 1 `billing/webhooks.py` |
| PGBouncer Fixes | 6 fix files | 1 `core/pgbouncer.py` |
| Post Analytics | 3 service variants | 1 `instagram/post_analytics.py` |

**Result**: ~15-20 files eliminated, single source of truth for each concern.

### Phase 3: Domain Restructure (Week 1-2)

**Goal**: Move from file-type grouping to domain-based packages.

Start with the cleanest, most self-contained domain as a template:

1. **credits/** - Clean domain with clear boundaries (wallet, transactions, pricing, gate)
2. **billing/** - Consolidate Stripe files here
3. **auth/** - Authentication and user management
4. **instagram/** - Creator analytics, post analytics, scrapers
5. **discovery/** - Profile discovery, background processing
6. **cdn/** - CDN processing, R2 storage
7. **teams/** - Team management
8. **admin/** - Admin routes and services
9. **ai/** - AI model management, inference, orchestration

Each domain package gets:
```
domain/
├── __init__.py
├── router.py          # API endpoints
├── schemas.py         # Pydantic request/response models
├── service.py         # Business logic
├── models.py          # ORM models (if domain-specific)
├── dependencies.py    # Route dependencies
└── tasks.py           # Celery task definitions (if applicable)
```

### Phase 4: Separate AI Inference (Week 2)

**Goal**: Stop AI inference from blocking the API event loop.

**Current flow** (problematic):
```
API Request → Load Models in API Process → Run Inference (blocks 60-160s) → Return
```

**Target flow**:
```
API Request → Send to Celery AI Queue → Return "processing" status
                     │
                     ▼
              Celery AI Worker (separate process/container)
              ├── Models loaded once at worker startup
              ├── Processes inference tasks from queue
              └── Stores results in database
                     │
                     ▼
              Client polls for results (or webhook callback)
```

**Steps**:
1. Define Celery tasks for AI inference in `ai/tasks.py`
2. Move model loading to Celery worker initialization
3. API sends tasks to the AI queue instead of running inference inline
4. API returns a "processing" status with a job ID
5. Client polls a status endpoint until processing is complete
6. Alternatively, return results via SSE stream

**Result**: API responds instantly to all requests. AI processing happens asynchronously without blocking other users.

### Phase 5: Containerize (Week 2-3)

**Goal**: Create Docker configuration for consistent deployment.

**Multi-stage Dockerfile**:
```dockerfile
# Stage 1: Install dependencies
FROM python:3.11-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Download AI models (cached separately)
FROM builder AS model-downloader
RUN python -c "from transformers import pipeline; \
    pipeline('sentiment-analysis', model='cardiffnlp/twitter-roberta-base-sentiment-latest'); \
    pipeline('text-classification', model='papluca/xlm-roberta-base-language-detection'); \
    pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"

# Stage 3: Production runtime
FROM python:3.11-slim AS production
COPY --from=builder /opt/venv /opt/venv
COPY --from=model-downloader /root/.cache/huggingface /app/ai_models
COPY ./app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml**:
```yaml
services:
  api:
    build: { context: ., target: production }
    ports: ["8080:8000"]
    depends_on: [redis]
    deploy: { replicas: 2 }

  ai-worker:
    build: { context: ., target: production }
    command: celery -A app.core.celery worker -Q ai_analysis --concurrency=2
    depends_on: [redis]

  cdn-worker:
    build: { context: ., target: production }
    command: celery -A app.core.celery worker -Q cdn_processing --concurrency=4
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

**Result**: Consistent deployment across all environments. Workers scale independently from the API.

### Phase 6: Clean Up (Week 3)

1. Move all 36 root-level scripts to `scripts/` directory
2. Remove the unnecessary TensorFlow import (saves ~1.5 GB RAM)
3. Verify and remove unused `face-recognition` + `dlib` dependencies
4. Consolidate `requirements.txt` + `requirements-ai.txt` + `requirements-light.txt` into a single `pyproject.toml` with optional dependency groups
5. Add proper `.dockerignore` to exclude test scripts, docs, and development files
6. Add `alembic` or equivalent for database migration management

---

## 9. Deployment Roadmap

### Timeline Overview

```
Week 1: Security Fixes + main.py Refactor
  ├── Day 1: Fix billing security issues (passwords, webhooks, fallbacks)
  ├── Day 2: Slim main.py to <100 lines
  ├── Day 3: Consolidate duplicate services
  └── Day 4-5: Start domain restructuring

Week 2: AI Separation + Domain Restructure
  ├── Day 1-2: Move AI inference to Celery workers
  ├── Day 3-4: Continue domain restructuring
  └── Day 5: Fix Windows-specific code for Linux

Week 3: Containerization + Staging
  ├── Day 1-2: Create Dockerfile + docker-compose
  ├── Day 3: Deploy to Railway (staging)
  ├── Day 4: End-to-end testing on staging
  └── Day 5: Performance benchmarking

Week 4: Production Deployment
  ├── Day 1-2: Set up Google Cloud Run infrastructure
  ├── Day 3: Configure Stripe for production
  ├── Day 4: Deploy to production
  └── Day 5: Monitor, tune, and optimize
```

### Cost Summary

| Phase | Platform | Monthly Cost |
|-------|----------|-------------|
| Development | Local | $0 |
| Staging | Railway | ~$50-100 |
| Production (CPU) | Google Cloud Run | ~$320 |
| Production (GPU) | Google Cloud Run | ~$420 |
| Production (UAE) | AWS ECS | ~$450-600 |

---

## 10. Action Items Checklist

### Critical (Must Do Before Any Deployment)

- [ ] Remove plaintext passwords from Stripe checkout metadata
- [ ] Enable webhook signature verification (set `DEBUG=false`, set `STRIPE_WEBHOOK_SECRET`)
- [ ] Remove hardcoded fallback password `Following0925_25`
- [ ] Consolidate 3 webhook endpoints into 1
- [ ] Create Dockerfile and docker-compose.yml
- [ ] Fix Windows-specific `CREATE_NEW_PROCESS_GROUP` flag for Linux
- [ ] Commit the orphaned-teams fix (currently uncommitted in billing_routes.py)

### High Priority (Week 1-2)

- [ ] Slim main.py from 2,808 lines to <100 lines
- [ ] Move AI inference from API event loop to Celery workers
- [ ] Consolidate 6 R2 service files into 1
- [ ] Consolidate 3 Stripe service files into 1
- [ ] Consolidate 6 PGBouncer fix files into 1
- [ ] Remove unnecessary TensorFlow import (saves ~1.5 GB RAM)
- [ ] Pre-download AI models during Docker build
- [ ] Reduce database connection pool from 315 to ~50-100

### Medium Priority (Week 2-3)

- [ ] Restructure codebase to domain-based packages
- [ ] Move 36 root-level scripts to `scripts/` directory
- [ ] Verify and remove unused `face-recognition` + `dlib` dependencies
- [ ] Consolidate requirements files into `pyproject.toml`
- [ ] Add proper health check that accounts for model loading state
- [ ] Implement webhook event deduplication
- [ ] Add Stripe idempotency keys for checkout sessions
- [ ] Set up proper database migration management (Alembic)

### Operational (Week 3-4)

- [ ] Deploy staging environment on Railway
- [ ] Configure Stripe for production (live keys, webhook endpoints, Customer Portal)
- [ ] Set up Google Cloud Run infrastructure
- [ ] Configure monitoring and alerting
- [ ] End-to-end testing of all critical flows
- [ ] Performance benchmarking under load
- [ ] Set up CI/CD pipeline
- [ ] Configure custom domain (following.ae) with SSL

### Future Considerations

- [ ] Implement email notifications (currently TODO stubs)
- [ ] Add GPU support for AI inference (change device config from `cpu` to `cuda`)
- [ ] Consider Ray Serve or BentoML if real-time inference is needed
- [ ] Implement credit wallet reconciliation background job
- [ ] Add subscription expiry handling background job
- [ ] Set up annual billing flow end-to-end testing

---

*This analysis was produced by a 4-agent team analyzing the codebase in parallel: AI/ML Operations Analyzer, Backend Flow Auditor, Cloud Deployment Evaluator, and Billing System Analyzer.*
