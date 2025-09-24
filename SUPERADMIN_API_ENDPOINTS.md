# 🛡️ Superadmin API Endpoints - Complete Reference

**Last Updated**: January 2025
**Authentication**: Requires `superadmin`, `super_admin`, or `admin` role
**Base URLs**: `/api/superadmin/*`

## ✅ **IMPLEMENTATION STATUS**
- ✅ **FULLY IMPLEMENTED**: Dashboard, Analytics, User Management, Credits, Billing, Security, System Health, Proposal Access Grants
- 🟡 **PARTIALLY IMPLEMENTED**: Advanced proposals management (content creation features)
- ❌ **NOT IMPLEMENTED**: Advanced features marked in sections below

---

## 📊 Dashboard & Overview Endpoints ✅ **IMPLEMENTED**

### **GET /api/superadmin/dashboard** ✅
**Comprehensive dashboard overview with real-time metrics**
- **Response Model**: `DashboardOverviewResponse`
- **Returns**:
  - System health metrics (CPU, Memory, Disk usage)
  - User statistics (total, new registrations, active users)
  - Revenue analytics (total revenue, monthly growth)
  - Credit system overview (total distributed, spent)
  - Recent activities and alerts
  - Performance metrics
- **Use Case**: Main superadmin dashboard data

### **GET /api/superadmin/analytics**
**Comprehensive business analytics and insights**
- **Response Model**: `AnalyticsResponse`
- **Returns**:
  - User growth trends
  - Revenue analytics by time period
  - Credit consumption patterns
  - Popular influencer categories
  - System usage metrics
  - Conversion funnels
- **Use Case**: Business intelligence dashboard

### **GET /api/superadmin/analytics/realtime**
**Real-time analytics and live metrics**
- **Response Model**: `RealTimeAnalyticsResponse`
- **Returns**:
  - Active users count
  - Live system performance
  - Current API requests per second
  - Real-time credit transactions
  - Active searches and unlocks
- **Use Case**: Live monitoring dashboard

---

## 👥 User Management Endpoints

### **GET /api/superadmin/users**
**Comprehensive user management with filtering**
- **Query Parameters**:
  - `limit` (1-100): Results per page
  - `offset` (≥0): Pagination offset
  - `role_filter`: Filter by user role
  - `status_filter`: Filter by user status
  - `search`: Search by name or email
- **Response Model**: `UserManagementResponse`
- **Returns**:
  - Paginated user list with full details
  - Team memberships and roles
  - Credit wallet information
  - Recent activity summary
  - Account status and flags

### **POST /api/superadmin/users/create**
**Create new user accounts with full configuration**
- **Request Body**: `UserCreateRequest`
- **Complete Field Control**:
  - **Identity**: `email` (required), `full_name`, `first_name`, `last_name`
  - **Contact**: `phone_number`, `company`, `job_title`, `bio`
  - **Authentication**: `password` (auto-generated), `email_verified` (default: true), `phone_verified`
  - **Access Control**: `role` (required), `status` (active/inactive/suspended)
  - **Subscription**: `subscription_tier` (required), `subscription_expires_at`
  - **Credits**: `initial_credits` (required), `credits_used_this_month` (default: 0)
  - **Security**: `two_factor_enabled`, `profile_visibility`, `data_analytics_enabled`
  - **Preferences**: `timezone`, `language`, `notification_preferences` (JSON)
  - **Organization**: `team_id` (optional), `stripe_customer_id`
  - **System**: `avatar_config` (JSON), `preferences` (JSON)
- **Auto-Generated**: User ID, creation timestamps, hashed password, Supabase integration
- **Returns**: Complete user profile with system-generated fields
- **Use Case**: Enterprise user onboarding with full account configuration
- **Validation**: Email uniqueness, role permissions, credit limits, subscription validation

### **PUT /api/superadmin/users/{user_id}/edit**
**Edit existing user accounts**
- **Request Body**: User update data
- **Updatable Fields**:
  - Role, status, subscription tier
  - Credits, team assignments
  - Profile information
- **Returns**: Updated user details

### **POST /api/superadmin/users/{user_id}/permissions**
**Granular permission management for individual users**
- **Request Body**: `{"permissions": {"profiles_view": true, "profiles_export": false, "proposals_access": true, "admin_access": false}, "override_role": true}`
- **Returns**: Updated user permissions and effective access level
- **Use Case**: Custom permission sets beyond standard roles

### **POST /api/superadmin/users/{user_id}/features/proposals/grant**
**Grant proposal access to specific users or teams**
- **Request Body**:
  ```json
  {
    "access_level": "full|read_only|custom",
    "expires_at": "2025-12-31T23:59:59Z",
    "reason": "Enterprise client upgrade",
    "custom_permissions": {
      "create_proposals": true,
      "edit_proposals": true,
      "delete_proposals": false,
      "view_all_proposals": true,
      "manage_collaborators": true,
      "export_proposals": true
    },
    "usage_limits": {
      "max_proposals_per_month": 50,
      "max_collaborators_per_proposal": 10
    },
    "notification_settings": {
      "notify_user": true,
      "send_welcome_email": true,
      "admin_notifications": true
    }
  }
  ```
- **Complete Control Process**:
  1. **Access Grant**: Creates entry in `proposal_access_grants` table
  2. **Permission Matrix**: Sets granular proposal permissions
  3. **Usage Tracking**: Establishes monthly limits and monitoring
  4. **Audit Trail**: Logs grant action with admin details and reason
  5. **User Notification**: Optional email notification to user
  6. **Team Propagation**: If user is team member, inherits team access level
- **Returns**:
  - Grant confirmation with unique access ID
  - Effective permissions matrix
  - Usage limits and current consumption
  - Expiration details and renewal options
- **Use Case**: Enable proposals for agency clients and enterprise users
- **Validation**: User existence, conflicting permissions, expiration date validity

### **POST /api/superadmin/users/{user_id}/features/proposals/revoke**
**Revoke proposal access from users or teams**
- **Request Body**: `{"reason": "Subscription downgrade", "immediate": true}`
- **Returns**: Access revocation confirmation
- **Use Case**: Remove proposal access when subscription changes

### **GET /api/superadmin/users/{user_id}/permissions**
**Get effective permissions for a user**
- **Returns**:
  - Role-based permissions
  - Custom permission overrides
  - Team-inherited permissions
  - Effective permission matrix
- **Use Case**: Permission auditing and troubleshooting

### **POST /api/superadmin/users/{user_id}/security/mfa**
**Multi-factor authentication control**
- **Request Body**: `{"action": "enforce|disable|reset", "method": "sms|email|authenticator"}`
- **Returns**: MFA status update and recovery codes if applicable
- **Use Case**: Security policy enforcement

### **POST /api/superadmin/users/{user_id}/security/sessions**
**Session management and forced logout**
- **Request Body**: `{"action": "terminate_all|terminate_device", "device_id": "optional"}`
- **Returns**: Session termination confirmation
- **Use Case**: Security incidents and account compromise response

### **POST /api/superadmin/users/{user_id}/security/password-reset**
**Administrative password reset**
- **Request Body**: `{"notify_user": true, "force_change": true, "temporary_password": "auto-generate"}`
- **Returns**: Password reset confirmation and temporary credentials
- **Use Case**: Account recovery and security policy enforcement

### **GET /api/superadmin/users/{user_id}/login-history**
**Detailed login and access history**
- **Query Parameters**: `limit`, `date_from`, `date_to`, `include_failed_attempts`
- **Returns**:
  - Login timestamps and IP addresses
  - Device and browser information
  - Failed login attempts and patterns
  - Geographic login distribution
- **Use Case**: Security monitoring and user behavior analysis

### **POST /api/superadmin/users/{user_id}/impersonate**
**Administrative user impersonation**
- **Request Body**: `{"duration_minutes": 30, "reason": "customer_support", "notify_user": false}`
- **Returns**: Impersonation token and session details
- **Use Case**: Customer support and troubleshooting
- **⚠️ Security**: All impersonation actions logged with admin details

### **POST /api/superadmin/users/{user_id}/status**
**Change user account status (activate/deactivate/suspend)**
- **Request Body**: `{"status": "active|inactive|suspended"}`
- **Returns**: Status change confirmation
- **Use Case**: Account moderation

### **DELETE /api/superadmin/users/{user_id}**
**Permanently delete user accounts**
- **Returns**: Deletion confirmation
- **⚠️ Warning**: Permanent action, removes all user data

### **GET /api/superadmin/users/{user_id}/activities**
**Get detailed user activity history**
- **Response Model**: `UserActivityResponse`
- **Returns**:
  - Login history and sessions
  - Credit transactions and unlocks
  - Profile searches and access
  - Team activity participation
- **Use Case**: User audit and investigation

### **POST /api/superadmin/users/bulk-operations**
**Bulk user management operations**
- **Request Body**: `{"operation": "update_role|assign_team|reset_passwords", "user_ids": [], "parameters": {}}`
- **Returns**: Bulk operation results and individual status per user
- **Use Case**: Mass user management and policy enforcement

### **GET /api/superadmin/users/advanced-search**
**Advanced user search and filtering**
- **Query Parameters**: `role`, `status`, `last_login_before`, `credits_range`, `team_id`, `subscription_tier`
- **Returns**: Filtered user list with comprehensive details
- **Use Case**: User segmentation and targeted management

---

## 🔐 Role & Permission Management

### **GET /api/superadmin/roles**
**Comprehensive role management**
- **Returns**:
  - All available roles and permission levels
  - Role hierarchy and inheritance rules
  - Permission matrix by role
  - Role usage statistics
- **Use Case**: Role administration and permission auditing

### **POST /api/superadmin/roles/create**
**Create custom roles with granular permissions**
- **Request Body**: `{"role_name": "custom_analyst", "permissions": {}, "role_level": 2, "description": "..."}`
- **Returns**: Created role details and permission matrix
- **Use Case**: Custom organizational role creation

### **PUT /api/superadmin/roles/{role_id}/permissions**
**Update role permissions**
- **Request Body**: `{"permissions": {"feature_access": {...}, "data_access": {...}}, "apply_to_existing_users": true}`
- **Returns**: Updated role and affected user count
- **Use Case**: Dynamic permission management

### **GET /api/superadmin/permissions/matrix**
**Complete permission matrix across all features**
- **Returns**:
  - Feature-level permissions (profiles, proposals, exports, analytics)
  - Data access permissions (view, create, edit, delete)
  - Administrative permissions (user management, system config)
  - API endpoint access mapping
  - Special feature gates (proposals, advanced analytics, white-label)
- **Use Case**: Permission system overview and planning

### **GET /api/superadmin/features/access-grants** ✅
**Monitor and manage all feature access grants across the platform**
- **Query Parameters**: `feature_type`, `user_id`, `team_id`, `status`, `expires_soon`
- **Complete Feature Access Overview**:
  - **Proposal Access Grants**: All users with proposal feature access
  - **Team Access Hierarchy**: Team-based vs individual access grants
  - **Expiration Monitoring**: Grants expiring within specified timeframes
  - **Usage Analytics**: How granted access is being utilized
  - **Access Level Distribution**: Full vs read_only vs custom permissions
- **Returns**:
  - Paginated list of all feature grants with user/team details
  - Grant status (active, expired, revoked) and creation history
  - Access level breakdown (full, read_only, custom permissions)
  - Usage statistics and engagement metrics per grant
  - Expiration warnings and auto-renewal recommendations
  - Admin audit trail (who granted, when, why)
- **Use Case**: Platform-wide feature access oversight and compliance monitoring

### **POST /api/superadmin/features/bulk-grant**
**Bulk feature access management**
- **Request Body**: `{"feature": "proposals", "users": [], "teams": [], "access_level": "full", "expires_at": "..."}`
- **Returns**: Bulk grant operation results
- **Use Case**: Enterprise onboarding and mass feature enabling

---

## 👥 Team Management & Collaboration

### **GET /api/superadmin/teams/comprehensive**
**Advanced team management overview**
- **Query Parameters**: `include_members`, `include_usage`, `include_billing`
- **Returns**:
  - Team details with member hierarchy
  - Usage statistics and limits
  - Billing and subscription information
  - Team-level permission overrides
- **Use Case**: Organizational oversight and team optimization

### **POST /api/superadmin/teams/{team_id}/members/bulk**
**Bulk team member management**
- **Request Body**: `{"operation": "add|remove|change_role", "user_ids": [], "team_role": "member|admin"}`
- **Returns**: Team membership update results
- **Use Case**: Large-scale team reorganization

### **PUT /api/superadmin/teams/{team_id}/permissions**
**Team-level permission management**
- **Request Body**: `{"permissions": {...}, "override_individual": false}`
- **Returns**: Updated team permissions and affected members
- **Use Case**: Team-based access control

---

## 💳 Credits & Billing Management

### **GET /api/superadmin/credits/overview**
**System-wide credit analytics and overview**
- **Returns**:
  - Total credits in circulation
  - Credit distribution by user tier
  - Top spending users and patterns
  - Credit package popularity
  - Fraud detection alerts

### **POST /api/superadmin/credits/users/{user_id}/adjust**
**Manually adjust user credit balances**
- **Request Body**: `CreditOperationRequest`
  ```json
  {
    "operation_type": "add|deduct|set_balance|bonus|refund",
    "amount": 1000,
    "reason": "Customer support refund",
    "reference_type": "support_ticket|billing_adjustment|promotional",
    "reference_id": "TICKET-12345",
    "billing_cycle_impact": "current|next|none",
    "notification": {
      "notify_user": true,
      "email_receipt": true,
      "custom_message": "Refund processed for billing issue"
    },
    "metadata": {
      "admin_notes": "Billing system error resolved",
      "approval_level": "manager|director",
      "external_transaction_id": "stripe_refund_12345"
    }
  }
  ```
- **Complete Process Control**:
  1. **Balance Validation**: Checks current balance and limits
  2. **Transaction Creation**: Creates audit trail in `credit_transactions`
  3. **Wallet Update**: Updates `credit_wallets` with new balance
  4. **Usage Impact**: Adjusts monthly usage if specified
  5. **Billing Integration**: Syncs with Stripe if applicable
  6. **User Notification**: Optional email with transaction details
  7. **Admin Logging**: Records admin action and justification
- **Returns**:
  - Updated credit balance (before/after)
  - Transaction ID for tracking
  - Billing cycle impact details
  - User notification status
- **Use Case**: Customer support, refunds, bonuses, billing corrections
- **Validation**: Minimum balance rules, maximum credit limits, role permissions

### **GET /api/superadmin/billing/transactions**
**Comprehensive transaction history**
- **Query Parameters**:
  - `limit`, `offset`: Pagination
  - `user_id`: Filter by specific user
  - `transaction_type`: Filter by operation type
  - `date_from`, `date_to`: Date range filtering
- **Returns**:
  - Detailed transaction history
  - Payment processing status
  - Refunds and adjustments
  - Revenue attribution

### **GET /api/superadmin/billing/revenue-analytics**
**Revenue analytics and financial reporting**
- **Returns**:
  - Monthly recurring revenue (MRR)
  - Customer lifetime value (CLV)
  - Churn rates and retention
  - Revenue by subscription tier
  - Payment method analytics

---

## 🔒 Security & Monitoring

### **GET /api/superadmin/security/alerts**
**Security alerts and threat detection**
- **Response Model**: `SecurityAlertsResponse`
- **Returns**:
  - Failed login attempts
  - Suspicious user behavior
  - API abuse detection
  - Credit fraud alerts
  - System intrusion attempts

### **GET /api/superadmin/security/suspicious-activities**
**Detailed suspicious activity monitoring**
- **Returns**:
  - Unusual access patterns
  - Multiple account creation from same IP
  - Rapid credit consumption
  - Bot-like behavior detection
  - Geographic anomalies

---

## 🏢 System Administration

### **GET /api/superadmin/system/stats**
**Detailed system statistics and performance**
- **Returns**:
  - Database performance metrics
  - API response times
  - Background job queue status
  - Redis cache hit rates
  - Storage utilization

### **GET /api/superadmin/system/health**
**Comprehensive system health monitoring**
- **Returns**:
  - Service availability status
  - Database connection health
  - External API dependencies
  - Background worker status
  - Alert threshold monitoring

---

## 👑 Influencer Management

### **GET /api/superadmin/influencers/master-database**
**Complete influencer database access**
- **Response Model**: `MasterInfluencerResponse`
- **Query Parameters**:
  - `category`: Filter by content category
  - `follower_range`: Filter by follower count
  - `engagement_min`: Minimum engagement rate
  - `limit`, `offset`: Pagination
- **Returns**:
  - Complete influencer profiles
  - Performance metrics and analytics
  - Pricing information and history
  - Availability status

### **GET /api/superadmin/influencers/{influencer_id}/detailed**
**Detailed influencer profile and analytics**
- **Returns**:
  - Complete profile information
  - Historical performance data
  - Engagement trends and insights
  - Brand collaboration history
  - Revenue generation data

---

## 📋 Proposals Management

### **GET /api/superadmin/proposals/overview**
**Comprehensive proposal system overview**
- **Returns**:
  - Active proposal statistics
  - Proposal status distribution
  - Revenue pipeline analysis
  - Brand response rates
  - Success metrics

### **GET /api/superadmin/proposals/manage**
**Proposal management interface data**
- **Query Parameters**:
  - `status`: Filter by proposal status
  - `brand_id`: Filter by specific brand
  - `limit`, `offset`: Pagination
- **Returns**:
  - Paginated proposal list
  - Brand assignment details
  - Timeline and deadlines
  - Response tracking

### **PUT /api/superadmin/proposals/{proposal_id}/status**
**Update proposal status and management**
- **Request Body**: Status update data
- **Operations**: Approve, reject, modify, reassign
- **Returns**: Updated proposal details

---

---

## ⚠️ **IMPLEMENTATION STATUS NOTICE**
**The following sections contain PLANNED endpoints that are NOT YET IMPLEMENTED**. Only use endpoints marked with ✅ in production.

---

## 🔐 Authentication & Authorization

### **Role Requirements**
All endpoints require one of the following roles:
- `superadmin`
- `super_admin`
- `admin`

### **Authentication Method**
- **Header**: `Authorization: Bearer <jwt_token>`
- **Token Source**: Login via `/api/auth/login`

### **Rate Limiting**
- **Standard**: 1000 requests per minute
- **Bulk Operations**: 100 requests per minute
- **Real-time Endpoints**: 500 requests per minute

---

## 📊 Response Formats

### **Standard Response Wrapper**
```typescript
interface SuperadminApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  timestamp: string;
  user_id: string;
}
```

### **Pagination Format**
```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}
```

### **Error Response Format**
```typescript
interface ErrorResponse {
  detail: string;
  status_code: number;
  timestamp: string;
  path: string;
}
```

---

## ⚠️ Important Notes for Frontend

### **Security Considerations**
- All endpoints contain sensitive administrative data
- Implement proper role-based UI restrictions
- Log all superadmin actions for audit trails
- Use secure communication (HTTPS only)

### **Performance Optimization**
- Dashboard endpoints return large datasets
- Implement proper caching strategies
- Use pagination for large lists
- Consider real-time updates for live metrics

### **Error Handling**
- Handle 403 Forbidden (insufficient role)
- Handle 429 Rate Limited responses
- Implement retry logic for transient failures
- Display user-friendly error messages

### **Data Sensitivity**
- User personal information (PII)
- Financial transaction data
- Security alerts and logs
- System performance metrics

---

## 🚀 Integration Checklist

- [ ] Implement role-based route protection
- [ ] Add comprehensive error handling
- [ ] Implement data pagination UI
- [ ] Add real-time dashboard updates
- [ ] Create audit logging for actions
- [ ] Implement secure data export features
- [ ] Add confirmation dialogs for destructive actions
- [ ] Implement search and filtering UI
- [ ] Add bulk operation capabilities
- [ ] Create responsive admin interface

---

## 🤖 AI System Management & Monitoring

### **GET /api/superadmin/ai/models/status**
**AI models performance and health monitoring**
- **Returns**:
  - Individual model performance metrics
  - Analysis success/failure rates per model
  - Processing times and bottlenecks
  - Queue depth and processing backlogs
  - Model version information and updates
- **Use Case**: Monitor AI system health and performance

### **GET /api/superadmin/ai/analysis/queue**
**AI analysis queue monitoring and management**
- **Returns**:
  - Current queue depth by model type
  - Processing times and estimated completion
  - Failed analysis jobs and retry status
  - Resource utilization metrics
  - Background worker health status
- **Use Case**: Monitor and manage AI processing pipeline

### **GET /api/superadmin/ai/analysis/stats**
**Comprehensive AI analysis statistics**
- **Query Parameters**: `date_from`, `date_to`, `model_type`
- **Returns**:
  - Total analyses performed by model type
  - Success rates and error patterns
  - Processing time trends
  - Content category distribution
  - Sentiment analysis distribution
  - Language detection statistics
- **Use Case**: AI system performance analytics

### **POST /api/superadmin/ai/analysis/retry**
**Retry failed AI analysis jobs**
- **Request Body**: `{"job_ids": [], "model_types": []}`
- **Returns**: Retry operation status and queue updates
- **Use Case**: Recover from failed AI processing

---

## 📱 Content & Media Management

### **GET /api/superadmin/content/moderation/queue**
**Content moderation queue and flagged content**
- **Returns**:
  - Flagged profiles and posts requiring review
  - Automated moderation alerts
  - Content quality scores below thresholds
  - User-reported content
  - Suspicious activity patterns
- **Use Case**: Content moderation and platform safety

### **GET /api/superadmin/content/categories/distribution**
**Content category distribution and trends**
- **Returns**:
  - Content categories by volume
  - Trending content types
  - Geographic content distribution
  - Language usage patterns
  - Content quality metrics by category
- **Use Case**: Content strategy and curation insights

### **GET /api/superadmin/cdn/performance**
**CDN and media delivery performance**
- **Returns**:
  - Image processing success rates
  - CDN response times and latency
  - Storage utilization by bucket
  - Thumbnail generation statistics
  - Media asset optimization metrics
- **Use Case**: Monitor media delivery performance

### **GET /api/superadmin/cdn/assets**
**Media asset management and statistics**
- **Query Parameters**: `asset_type`, `status`, `date_range`
- **Returns**:
  - Asset counts by type and status
  - Storage usage and costs
  - Processing failures and retries
  - Asset lifecycle management
  - Cleanup recommendations
- **Use Case**: Media asset management and optimization

---

## ⚙️ System Configuration & Feature Management

### **GET /api/superadmin/system/configurations**
**System configuration management**
- **Complete Configuration Access**:
  - **AI System**: `ai_analysis_enabled`, `ai_models_enabled`, `ai_comprehensive_analysis_version`
  - **Rate Limiting**: `api_rate_limit_per_minute`, `bulk_operation_limits`, `concurrent_requests`
  - **Credits**: `default_user_credits`, `profile_analysis_cost`, `max_credits_per_user`
  - **Caching**: `cache_ttl_profiles`, `cache_ttl_posts`, `redis_connection_pool_size`
  - **Features**: `max_profiles_per_list`, `export_formats_enabled`, `bulk_operations_enabled`
  - **Security**: `password_complexity`, `session_timeout`, `mfa_enforcement_roles`
  - **Maintenance**: `system_maintenance_window`, `backup_schedule`, `cleanup_intervals`
  - **Integration**: `stripe_webhook_endpoints`, `email_service_config`, `cdn_settings`
- **Configuration Details**:
  - Current value and data type
  - Default value and valid ranges
  - Last modified timestamp and admin
  - Environment overrides (dev/staging/prod)
  - Restart requirements for changes
  - Impact assessment and dependencies
- **Returns**: Complete system configuration matrix with change history
- **Use Case**: Platform configuration oversight and compliance auditing

### **PUT /api/superadmin/system/configurations**
**Update system configurations**
- **Request Body**: `{"config_key": "value", "description": "...", "requires_restart": false}`
- **Returns**: Configuration update confirmation
- **Use Case**: Real-time system configuration management

### **GET /api/superadmin/system/feature-flags**
**Feature flag management and status**
- **Returns**:
  - Active feature flags and rollout percentages
  - User segment targeting rules
  - A/B test configurations and results
  - Feature adoption metrics
  - Rollback capabilities
- **Use Case**: Feature rollout control and testing

### **POST /api/superadmin/system/feature-flags/{flag_id}/toggle**
**Toggle feature flags for users or segments**
- **Request Body**: `{"enabled": true, "rollout_percentage": 50, "target_segments": []}`
- **Returns**: Feature flag update confirmation
- **Use Case**: Control feature rollouts and experiments

---

## 📈 Advanced Platform Analytics

### **GET /api/superadmin/platform/usage/detailed**
**Comprehensive platform usage analytics**
- **Query Parameters**: `timeframe`, `breakdown_by`, `include_segments`
- **Returns**:
  - API endpoint usage by frequency
  - User journey analytics and funnel conversion
  - Feature adoption rates and engagement
  - Geographic usage patterns
  - Device and browser analytics
  - Performance bottleneck identification
- **Use Case**: Product optimization and resource planning

### **GET /api/superadmin/platform/performance/metrics**
**Platform performance and health metrics**
- **Returns**:
  - Response time percentiles (P50, P95, P99)
  - Error rates by endpoint and error type
  - Database query performance
  - Cache hit rates and optimization opportunities
  - Resource utilization trends
  - Alert threshold monitoring
- **Use Case**: Platform optimization and SLA monitoring

### **GET /api/superadmin/platform/api/usage**
**API usage analytics and rate limiting**
- **Query Parameters**: `user_id`, `endpoint_pattern`, `time_range`
- **Returns**:
  - API calls by endpoint and user
  - Rate limit violations and patterns
  - API key usage and quotas
  - Integration health scores
  - Usage forecasting and capacity planning
- **Use Case**: API management and quota optimization

---

## 🔍 Advanced User & Business Intelligence

### **GET /api/superadmin/users/cohort-analysis**
**User cohort analysis and retention metrics**
- **Query Parameters**: `cohort_period`, `retention_periods`
- **Returns**:
  - User retention curves by signup cohort
  - Feature usage by user lifecycle stage
  - Churn prediction and risk factors
  - User lifetime value calculations
  - Activation and engagement funnels
- **Use Case**: User growth strategy and retention optimization

### **GET /api/superadmin/users/segmentation**
**Advanced user segmentation and profiling**
- **Returns**:
  - User segments by behavior and usage patterns
  - High-value user identification
  - At-risk user detection
  - Usage pattern clustering
  - Personalization opportunity scoring
- **Use Case**: User experience optimization and marketing

### **GET /api/superadmin/business/forecasting**
**Business forecasting and predictive analytics**
- **Query Parameters**: `forecast_period`, `metrics`
- **Returns**:
  - Revenue forecasting models
  - User growth projections
  - Capacity planning recommendations
  - Seasonal trend analysis
  - Business goal tracking and predictions
- **Use Case**: Strategic planning and business intelligence

---

## 🛠️ Platform Operations & Maintenance

### **GET /api/superadmin/operations/health**
**Comprehensive system health monitoring**
- **Returns**:
  - Service dependency health checks
  - Database connection pool status
  - Background job processing health
  - External API integration status
  - System resource utilization
  - Alert status and escalation paths
- **Use Case**: Operations monitoring and incident prevention

### **GET /api/superadmin/operations/audit-log**
**Comprehensive platform audit logging**
- **Query Parameters**: `user_id`, `action_type`, `date_range`, `severity`
- **Returns**:
  - All administrative actions and changes
  - User behavior and access patterns
  - System configuration changes
  - Security events and anomalies
  - Data access and export logs
- **Use Case**: Security auditing and compliance

### **POST /api/superadmin/operations/maintenance**
**System maintenance and cleanup operations**
- **Request Body**: `{"operation": "cleanup_unused_assets", "dry_run": true, "schedule": "now"}`
- **Returns**: Maintenance operation status and results
- **Use Case**: Platform maintenance and optimization

### **GET /api/superadmin/operations/backup-status**
**Data backup and recovery status**
- **Returns**:
  - Backup schedule and completion status
  - Data retention policies and compliance
  - Recovery point objectives (RPO) status
  - Backup storage utilization
  - Disaster recovery readiness
- **Use Case**: Data protection and business continuity

---

## 📊 Data Export & Integration Management

### **POST /api/superadmin/data/export/comprehensive**
**Comprehensive data export for analytics and compliance**
- **Request Body**: `{"tables": [], "date_range": {}, "format": "csv|json", "include_pii": false}`
- **Returns**: Export job status and download links
- **Use Case**: Data analytics, compliance reporting, business intelligence

### **GET /api/superadmin/data/export/jobs**
**Data export job management and status**
- **Returns**:
  - Active and completed export jobs
  - Export job progress and estimated completion
  - Export file availability and expiration
  - Export audit trail and access logs
- **Use Case**: Large-scale data operations management

### **GET /api/superadmin/integrations/third-party**
**Third-party integration monitoring**
- **Returns**:
  - External API health and response times
  - Integration usage and quotas
  - Error rates and failure patterns
  - Cost tracking and optimization opportunities
  - Integration security and compliance status
- **Use Case**: Integration management and cost optimization

---

## 🚨 Security & Compliance Management

### **GET /api/superadmin/security/threats**
**Security threat detection and monitoring**
- **Returns**:
  - Suspicious login attempts and patterns
  - API abuse detection and mitigation
  - Data access anomalies
  - Potential security vulnerabilities
  - Threat intelligence integration
- **Use Case**: Proactive security monitoring and threat response

### **GET /api/superadmin/compliance/reports**
**Compliance reporting and data governance**
- **Query Parameters**: `report_type`, `date_range`, `regulation`
- **Returns**:
  - GDPR compliance status and data handling
  - Data retention policy enforcement
  - User consent and privacy controls
  - Data processing audit trails
  - Regulatory requirement tracking
- **Use Case**: Legal compliance and data governance

### **POST /api/superadmin/security/user-lock**
**Emergency user account controls**
- **Request Body**: `{"user_id": "uuid", "action": "lock|unlock|force_logout", "reason": "security_incident"}`
- **Returns**: Security action confirmation and audit log
- **Use Case**: Emergency security response and incident management

---

## ⚠️ Critical Implementation Notes

### **Enterprise Platform Control**
These endpoints provide complete visibility and control over:
- **AI Processing Pipeline**: Monitor and manage the core AI analysis system
- **Content Strategy**: Understand content trends and moderation needs
- **System Performance**: Comprehensive platform health and optimization
- **Business Intelligence**: Advanced analytics for strategic decision making
- **Operations Management**: Complete platform operational control
- **Security & Compliance**: Enterprise-grade security and regulatory compliance

### **Data Sensitivity & Access Control**
- All endpoints require `super_admin` role with additional permission checks
- Sensitive operations require multi-factor authentication confirmation
- All actions are comprehensively logged for audit compliance
- Rate limiting prevents abuse while allowing operational flexibility

### **Integration with Existing Systems**
- Seamlessly integrates with current dashboard and user management
- Extends existing credit and billing analytics
- Enhances proposal and influencer management with deeper insights
- Provides foundation for advanced business intelligence and automation

---

**End of Documentation**
*For technical support or endpoint clarification, contact the backend development team.*