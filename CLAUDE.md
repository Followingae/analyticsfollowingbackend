# Analytics Following Backend - Project Memory

## Project Overview
Instagram analytics platform backend built with FastAPI, providing comprehensive Instagram profile analysis using Decodo API integration. Includes user management, campaign tracking, and detailed analytics.

## Current Database Schema Status
**CRITICAL**: Database schema and code models are currently **MISALIGNED**

### Actual Database Tables (from schema resource)
```
PUBLIC SCHEMA TABLES:
- profiles (UUID primary key, comprehensive Instagram data)
- posts (UUID primary key, full post analytics)
- audience_demographics (profile demographics analysis)
- auth_users (Supabase auth integration)
- user_profiles (links auth_users to user data)
- user_profile_access (30-day access tracking)
- user_favorites (user saved profiles)
- user_searches (search history tracking)
- search_history (additional search tracking)
- campaigns (user campaign management)
- campaign_posts (posts linked to campaigns)
- campaign_profiles (profiles tracked in campaigns)
- creator_metadata (enhanced profile analytics)
- comment_sentiment (post comment analysis)
- mentions (profile mention tracking)
- related_profiles (similar profile suggestions)

AUTH SCHEMA (Supabase):
- Complete Supabase auth tables (users, sessions, identities, etc.)
```

### Model Inconsistencies Identified
1. **Missing Tables**: `users` table defined in models but doesn't exist in DB
2. **Wrong Foreign Keys**: Models reference `users.id` but DB uses `auth_users.id`
3. **Extra Fields**: Models define fields not present in actual DB
4. **Missing Models**: No models for `auth_users`, some existing tables

## Technology Stack
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL with Supabase integration
- **ORM**: SQLAlchemy (async)
- **Authentication**: Supabase Auth + custom middleware
- **External API**: Decodo Instagram API
- **Caching**: Redis-compatible caching layer

## Key Components

### API Structure
```
/api/
├── cleaned_routes.py - Production API endpoints
├── Enhanced Decodo client integration
├── Retry mechanisms for API stability
└── Comprehensive error handling
```

### Database Layer
```
/database/
├── unified_models.py - SQLAlchemy models (NEEDS SCHEMA ALIGNMENT)
├── comprehensive_service.py - Unified data operations
├── robust_storage.py - Data persistence layer
└── Database connection management
```

### Authentication
- Supabase-based authentication system
- Custom middleware for request validation
- User profile access management (30-day windows)

## Critical Schema Issues to Address

### Before Any New Development:
1. **Schema Alignment Required**: Models don't match actual database
2. **Foreign Key Fixes**: Update all user references to use `auth_users.id`
3. **Missing Table Creation**: Need to create `users` table or refactor to use `auth_users`
4. **Data Type Corrections**: Fix UUID vs String mismatches

### Current Limitations:
- **Data Storage Failing**: Code tries to insert into non-existent tables
- **Relationship Conflicts**: Foreign key mismatches causing errors
- **Incomplete User Management**: Split between Supabase and custom systems

## Development Guidelines

### Before Making Changes:
1. **Always check actual database schema first**
2. **Verify table existence and column types**
3. **Test foreign key relationships**
4. **Ensure Supabase compatibility**

### When Schema Changes Needed:
- Alert user about required database migrations
- Specify exact SQL changes needed
- Consider impact on existing data
- Plan migration strategy

### Code Quality Standards:
- Comprehensive error handling
- Async/await patterns throughout
- Proper logging and monitoring
- Type hints for all functions
- Documentation for complex operations

## API Endpoints (Current)

### Profile Operations
- `GET /profile/{username}` - Get Instagram profile with analytics
- Decodo API integration with retry mechanisms
- Comprehensive data storage (when schema fixed)
- 30-day access tracking

### User Management
- Supabase authentication integration
- User preferences and settings
- Credit/subscription management
- Profile access controls

## Environment Configuration
```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SMARTPROXY_USERNAME=...
SMARTPROXY_PASSWORD=...
```

## Dependencies
```
fastapi
sqlalchemy[asyncio]
asyncpg
supabase
tenacity (retry logic)
redis (caching)
pydantic (data validation)
```

## Testing Strategy
- Unit tests for data models
- Integration tests for API endpoints
- Database migration testing
- Decodo API mock testing

## Deployment Considerations
- Database schema must be aligned before production
- Environment variable management
- Logging and monitoring setup
- Error reporting integration

## Performance Optimizations
- Connection pooling (asyncpg)
- Profile data caching
- Efficient database queries
- Retry mechanisms for external APIs

## Security Measures
- Supabase auth integration
- API rate limiting
- Input validation and sanitization
- Secure credential management

## Monitoring & Logging
- Comprehensive logging throughout application
- Error tracking and alerting
- Performance monitoring
- API usage analytics

---

## IMMEDIATE ACTION REQUIRED
**Schema alignment must be completed before any new feature development. Current code will fail due to table/column mismatches.**