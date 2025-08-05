# Analytics Following Backend - Project Memory

## Project Overview
Instagram analytics platform backend built with FastAPI, providing comprehensive Instagram profile analysis using Decodo API integration. Includes user management, campaign tracking, and detailed analytics.

## Current Database Schema Status
**✅ UPDATED**: Database schema documentation is now current and aligned

### AUTH SCHEMA (Supabase Authentication)
```
auth.users - Primary Supabase user table
auth.sessions - User session management
auth.identities - OAuth/SSO identity linking
auth.instances - Multi-tenant instance support
auth.refresh_tokens - Token refresh management
auth.audit_log_entries - Authentication audit trail
auth.mfa_factors - Multi-factor authentication setup
auth.mfa_challenges - MFA challenge tracking
auth.mfa_amr_claims - Authentication method references
auth.one_time_tokens - Password reset/verification tokens
auth.flow_state - OAuth flow state management
auth.saml_providers - SAML SSO configuration
auth.saml_relay_states - SAML relay state tracking  
auth.sso_providers - Single sign-on providers
auth.sso_domains - Domain-based SSO mapping
auth.schema_migrations - Schema version tracking
```

### PUBLIC SCHEMA (Application Data)
```
Core Instagram Analytics:
- profiles - Instagram profile data and analytics
- posts - Individual post content and metrics
- audience_demographics - Profile audience analysis
- creator_metadata - Enhanced profile analytics
- comment_sentiment - Post comment sentiment analysis
- mentions - Profile mention tracking
- related_profiles - Similar profile suggestions

User Management:
- users - Application user data and preferences
- auth_users - Bridge to Supabase auth system
- user_profiles - Extended user profile information
- user_profile_access - 30-day profile access tracking
- user_favorites - User saved/favorited profiles
- user_searches - Search activity tracking
- search_history - Additional search history

Campaign Management:
- campaigns - User campaign creation and tracking
- campaign_posts - Posts associated with campaigns
- campaign_profiles - Profiles tracked in campaigns
```

### Key Foreign Key Relationships
```
User Authentication Flow:
auth.users.id → user_profiles.user_id
users.id → campaigns.user_id
users.id → user_favorites.user_id
users.id → user_searches.user_id

Instagram Data Relationships:
profiles.id → posts.profile_id
profiles.id → audience_demographics.profile_id
profiles.id → creator_metadata.profile_id
profiles.id → mentions.profile_id
profiles.id → related_profiles.profile_id
profiles.id → user_favorites.profile_id
profiles.id → user_profile_access.profile_id
profiles.id → search_history.profile_id

Campaign Relationships:
campaigns.id → campaign_posts.campaign_id
campaigns.id → campaign_profiles.campaign_id
posts.id → campaign_posts.post_id
profiles.id → campaign_profiles.profile_id
posts.id → comment_sentiment.post_id
```

## Technology Stack

### Backend
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL with Supabase integration
- **ORM**: SQLAlchemy (async)
- **Authentication**: Supabase Auth + custom middleware
- **External API**: Decodo Instagram API
- **Caching**: Redis-compatible caching layer

### Frontend
- **Core Framework**:
  - Next.js 15.4.4 (React framework with Turbopack)
  - React 19.1.0 (Latest React version)
  - TypeScript 5 (Type safety)

- **UI Components**:
  - shadcn/ui (Custom installation - "new-york" style)
  - Radix UI (Underlying headless components)
  - Lucide React (Icon library)
  - class-variance-authority (Component variants)

- **Styling**:
  - Tailwind CSS v4 (Utility-first CSS)
  - CSS Variables (For theming)
  - next-themes (Dark/light mode)

- **State & Data**:
  - TanStack Query v5 (Server state management)
  - Zod (Schema validation)

- **Charts & Visualization**:
  - Recharts (Primary charting)
  - Chart.js + react-chartjs-2
  - ApexCharts + react-apexcharts

- **Interactive Features**:
  - DND Kit (Drag & drop)
  - TanStack Table v8 (Data tables)
  - React Day Picker (Date selection)
  - Sonner (Toast notifications)
  - CMDK (Command palette)
  - Vaul (Drawer component)

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
├── unified_models.py - SQLAlchemy models (schema-aligned)
├── comprehensive_service.py - Unified data operations
├── robust_storage.py - Data persistence layer
└── Database connection management
```

### Authentication
- Supabase-based authentication system
- Custom middleware for request validation
- User profile access management (30-day windows)

## Database Architecture Notes

### Authentication Strategy:
- **Dual Authentication System**: Supabase auth (auth schema) + application users (public.users)
- **User Flow**: auth.users → public.user_profiles → public.users for extended data
- **Access Control**: 30-day profile access via user_profile_access table

### Data Integrity:
- **All primary keys**: UUID with auto-generation
- **Timestamps**: Consistent timezone-aware timestamps throughout
- **JSONB Storage**: Flexible data storage for Instagram API responses
- **Foreign Key Constraints**: Enforced referential integrity across all relationships

### Performance Considerations:
- **Indexed Relationships**: All foreign keys properly indexed
- **JSONB Indexing**: Consider GIN indexes on frequently queried JSONB columns
- **Partitioning**: Consider partitioning large tables (posts, user_searches) by date

## Development Guidelines

### Schema Management:
1. **Schema is current and documented** - refer to this file for accurate structure
2. **Migration Strategy**: Use Supabase migrations for schema changes
3. **Testing**: Verify foreign key relationships when adding new tables
4. **Compatibility**: Maintain Supabase auth integration

### When Adding New Features:
- Follow existing UUID primary key patterns
- Use proper foreign key constraints
- Include created_at/updated_at timestamps where appropriate
- Consider JSONB for flexible data storage

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
- Comprehensive data storage to profiles/posts tables
- 30-day access tracking via user_profile_access table

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
- Database schema is current and production-ready
- Environment variable management
- Logging and monitoring setup
- Error reporting integration
- Supabase auth configuration

## Performance Optimizations
- Connection pooling (asyncpg)
- Profile data caching
- Efficient database queries
- Retry mechanisms for external APIs

## Security Measures
- **Supabase Auth Integration** - Complete OAuth and JWT-based authentication
- **Comprehensive Row Level Security (RLS)** - Database-level access control implemented
  - **ALL tables now secured** with RLS enabled (addresses Supabase security advisor warnings)
  - **True Multi-Tenant Isolation**: Each user can only access their own data
  - **Controlled Instagram Data Access**: Users can only view profiles they have searched/accessed
  - **User-Specific Data Protection**: All user tables (campaigns, favorites, searches) fully secured
  - **Service Role Backend Control**: API retains full access for data operations
  - **Access Tracking**: Instagram data access controlled via `user_profile_access` table
  - Migration: `/database/migrations/comprehensive_rls_security.sql`
- **API Rate Limiting** - Request throttling and abuse prevention
- **Input Validation** - Comprehensive request validation and sanitization
- **Secure Credential Management** - Environment-based secrets management

### RLS Security Architecture
```
User Authentication Flow:
auth.users → RLS policies → user data isolation

Instagram Data Access:
user searches profile → user_profile_access record → RLS allows access to that profile's data

Multi-Tenant Isolation:
- User A can only see User A's campaigns, favorites, searches
- User A can only see Instagram data for profiles User A has searched
- Backend API (service_role) has full access for operations
- No cross-user data leakage possible
```

## Monitoring & Logging
- Comprehensive logging throughout application
- Error tracking and alerting
- Performance monitoring
- API usage analytics

---

## CURRENT STATUS
**✅ Schema Updated**: Database schema documentation is now current and comprehensive. All tables, relationships, and foreign keys are documented and aligned for development.