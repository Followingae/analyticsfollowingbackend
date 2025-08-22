# Analytics Following Backend - Complete API Documentation

## Overview
Complete API endpoint documentation for the Analytics Following Backend system.

**Base URL**: `http://localhost:8000` (development) / `https://your-domain.com` (production)

## Authentication
Most endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---


## Brand Proposals Routes
*Source: brand_proposals_routes.py*


### `/api/proposals`

**GET** `/api/proposals`
- Function: `get_brand_proposals`

**GET** `/api/proposals`
- Function: `get_brand_proposals`


### `/api/proposals/{proposal_id}`

**GET** `/api/proposals/{proposal_id}`
- Function: `get_brand_proposal`

**GET** `/api/proposals/{proposal_id}`
- Function: `get_brand_proposal`


## Campaigns Routes
*Source: campaigns_routes.py*


### `/api/campaigns`

**GET** `/api/campaigns`
- Function: `get_campaigns`

**POST** `/api/campaigns`
- Function: `create_campaign`

**GET** `/api/campaigns`
- Function: `get_campaigns`

**POST** `/api/campaigns`
- Function: `create_campaign`


### `/api/campaigns/analytics`

**GET** `/api/campaigns/analytics`
- Function: `get_global_campaigns_analytics`

**GET** `/api/campaigns/analytics`
- Function: `get_global_campaigns_analytics`


### `/api/campaigns/dashboard`

**GET** `/api/campaigns/dashboard`
- Function: `get_campaigns_dashboard`

**GET** `/api/campaigns/dashboard`
- Function: `get_campaigns_dashboard`


### `/api/campaigns/templates`

**GET** `/api/campaigns/templates`
- Function: `get_campaign_templates`

**GET** `/api/campaigns/templates`
- Function: `get_campaign_templates`


### `/api/campaigns/templates/{template_id}/create`

**POST** `/api/campaigns/templates/{template_id}/create`
- Function: `create_campaign_from_template`

**POST** `/api/campaigns/templates/{template_id}/create`
- Function: `create_campaign_from_template`


### `/api/campaigns/{campaign_id}`

**GET** `/api/campaigns/{campaign_id}`
- Function: `get_campaign`

**GET** `/api/campaigns/{campaign_id}`
- Function: `get_campaign`


### `/api/campaigns/{campaign_id}/analytics`

**GET** `/api/campaigns/{campaign_id}/analytics`
- Function: `get_campaign_analytics`

**GET** `/api/campaigns/{campaign_id}/analytics`
- Function: `get_campaign_analytics`


## Cleaned Auth Routes
*Source: cleaned_auth_routes.py*


### `/api/v1/admin/users`

**GET** `/api/v1/admin/users`
- Function: `list_users_admin`

**GET** `/api/v1/admin/users`
- Function: `list_users_admin`


### `/api/v1/dashboard`

**GET** `/api/v1/dashboard`
- Function: `get_user_dashboard`
- Response Model: `UserDashboardStats`

**GET** `/api/v1/dashboard`
- Function: `get_user_dashboard`
- Response Model: `UserDashboardStats`


### `/api/v1/debug/session`

**GET** `/api/v1/debug/session`
- Function: `debug_session_info`

**GET** `/api/v1/debug/session`
- Function: `debug_session_info`


### `/api/v1/health`

**GET** `/api/v1/health`
- Function: `auth_health_check`

**GET** `/api/v1/health`
- Function: `auth_health_check`


### `/api/v1/login`

**POST** `/api/v1/login`
- Function: `login_user`
- Response Model: `LoginResponse`

**POST** `/api/v1/login`
- Function: `login_user`
- Response Model: `LoginResponse`


### `/api/v1/logout`

**POST** `/api/v1/logout`
- Function: `logout_user`

**POST** `/api/v1/logout`
- Function: `logout_user`


### `/api/v1/me`

**GET** `/api/v1/me`
- Function: `get_current_user_profile`
- Response Model: `UserResponse`

**GET** `/api/v1/me`
- Function: `get_current_user_profile`
- Response Model: `UserResponse`


### `/api/v1/refresh`

**POST** `/api/v1/refresh`
- Function: `refresh_access_token`
- Response Model: `LoginResponse`

**POST** `/api/v1/refresh`
- Function: `refresh_access_token`
- Response Model: `LoginResponse`


### `/api/v1/register`

**POST** `/api/v1/register`
- Function: `register_user`

**POST** `/api/v1/register`
- Function: `register_user`


### `/api/v1/search-history`

**GET** `/api/v1/search-history`
- Function: `get_search_history`
- Response Model: `UserSearchHistoryResponse`

**GET** `/api/v1/search-history`
- Function: `get_search_history`
- Response Model: `UserSearchHistoryResponse`


### `/api/v1/token-test`

**GET** `/api/v1/token-test`
- Function: `test_token_validation`

**GET** `/api/v1/token-test`
- Function: `test_token_validation`


### `/api/v1/unlocked-profiles`

**GET** `/api/v1/unlocked-profiles`
- Function: `get_unlocked_profiles`

**GET** `/api/v1/unlocked-profiles`
- Function: `get_unlocked_profiles`


## Cleaned Routes
*Source: cleaned_routes.py*


### `/api/v1/ai/analysis/status`

**GET** `/api/v1/ai/analysis/status`
- Function: `get_current_ai_analysis_status`

**GET** `/api/v1/ai/analysis/status`
- Function: `get_current_ai_analysis_status`


### `/api/v1/ai/fix/profile/{username}`

**POST** `/api/v1/ai/fix/profile/{username}`
- Function: `fix_profile_ai_analysis`

**POST** `/api/v1/ai/fix/profile/{username}`
- Function: `fix_profile_ai_analysis`


### `/api/v1/ai/status/profile/{username}`

**GET** `/api/v1/ai/status/profile/{username}`
- Function: `get_profile_ai_analysis_status`

**GET** `/api/v1/ai/status/profile/{username}`
- Function: `get_profile_ai_analysis_status`


### `/api/v1/ai/system/health`

**GET** `/api/v1/ai/system/health`
- Function: `get_ai_system_health`

**GET** `/api/v1/ai/system/health`
- Function: `get_ai_system_health`


### `/api/v1/ai/task/{task_id}/status`

**GET** `/api/v1/ai/task/{task_id}/status`
- Function: `get_ai_task_status`

**GET** `/api/v1/ai/task/{task_id}/status`
- Function: `get_ai_task_status`


### `/api/v1/ai/verify/{username}`

**GET** `/api/v1/ai/verify/{username}`
- Function: `verify_ai_analysis_completeness`

**GET** `/api/v1/ai/verify/{username}`
- Function: `verify_ai_analysis_completeness`


### `/api/v1/config`

**GET** `/api/v1/config`
- Function: `api_configuration`

**GET** `/api/v1/config`
- Function: `api_configuration`


### `/api/v1/health`

**GET** `/api/v1/health`
- Function: `health_check`

**GET** `/api/v1/health`
- Function: `health_check`


### `/api/v1/instagram/profile/{username}`

**GET** `/api/v1/instagram/profile/{username}`
- Function: `analyze_instagram_profile`

**GET** `/api/v1/instagram/profile/{username}`
- Function: `analyze_instagram_profile`


### `/api/v1/instagram/profile/{username}/analytics`

**GET** `/api/v1/instagram/profile/{username}/analytics`
- Function: `get_detailed_analytics`

**GET** `/api/v1/instagram/profile/{username}/analytics`
- Function: `get_detailed_analytics`


### `/api/v1/instagram/profile/{username}/complete-refresh`

**POST** `/api/v1/instagram/profile/{username}/complete-refresh`
- Function: `complete_profile_refresh`

**POST** `/api/v1/instagram/profile/{username}/complete-refresh`
- Function: `complete_profile_refresh`


### `/api/v1/instagram/profile/{username}/legacy-force-refresh`

**POST** `/api/v1/instagram/profile/{username}/legacy-force-refresh`
- Function: `legacy_force_refresh_profile_data`

**POST** `/api/v1/instagram/profile/{username}/legacy-force-refresh`
- Function: `legacy_force_refresh_profile_data`


### `/api/v1/instagram/profile/{username}/minimal`

**GET** `/api/v1/instagram/profile/{username}/minimal`
- Function: `minimal_profile_test`

**GET** `/api/v1/instagram/profile/{username}/minimal`
- Function: `minimal_profile_test`


### `/api/v1/instagram/profile/{username}/posts`

**GET** `/api/v1/instagram/profile/{username}/posts`
- Function: `get_profile_posts`

**GET** `/api/v1/instagram/profile/{username}/posts`
- Function: `get_profile_posts`


### `/api/v1/search/suggestions/{partial_username}`

**GET** `/api/v1/search/suggestions/{partial_username}`
- Function: `get_username_suggestions`

**GET** `/api/v1/search/suggestions/{partial_username}`
- Function: `get_username_suggestions`


### `/api/v1/status`

**GET** `/api/v1/status`
- Function: `api_status`

**GET** `/api/v1/status`
- Function: `api_status`


### `/api/v1/user/profile/complete`

**GET** `/api/v1/user/profile/complete`
- Function: `get_complete_user_profile`

**GET** `/api/v1/user/profile/complete`
- Function: `get_complete_user_profile`


## Credit Routes
*Source: credit_routes.py*


### `/api/v1/allowances`

**GET** `/api/v1/allowances`
- Function: `get_allowance_status`

**GET** `/api/v1/allowances`
- Function: `get_allowance_status`


### `/api/v1/analytics/spending`

**GET** `/api/v1/analytics/spending`
- Function: `get_spending_analytics`

**GET** `/api/v1/analytics/spending`
- Function: `get_spending_analytics`


### `/api/v1/balance`

**GET** `/api/v1/balance`
- Function: `get_credit_balance`
- Response Model: `CreditBalance`

**GET** `/api/v1/balance`
- Function: `get_credit_balance`
- Response Model: `CreditBalance`


### `/api/v1/can-perform/{action_type}`

**GET** `/api/v1/can-perform/{action_type}`
- Function: `check_action_permission`
- Response Model: `CanPerformActionResponse`

**GET** `/api/v1/can-perform/{action_type}`
- Function: `check_action_permission`
- Response Model: `CanPerformActionResponse`


### `/api/v1/dashboard`

**GET** `/api/v1/dashboard`
- Function: `get_credit_dashboard`
- Response Model: `CreditDashboard`

**GET** `/api/v1/dashboard`
- Function: `get_credit_dashboard`
- Response Model: `CreditDashboard`


### `/api/v1/pricing`

**GET** `/api/v1/pricing`
- Function: `get_pricing_rules`
- Response Model: `List`

**GET** `/api/v1/pricing`
- Function: `get_pricing_rules`
- Response Model: `List`


### `/api/v1/pricing/calculate`

**POST** `/api/v1/pricing/calculate`
- Function: `calculate_bulk_pricing`

**POST** `/api/v1/pricing/calculate`
- Function: `calculate_bulk_pricing`


### `/api/v1/pricing/{action_type}`

**GET** `/api/v1/pricing/{action_type}`
- Function: `get_action_pricing`

**GET** `/api/v1/pricing/{action_type}`
- Function: `get_action_pricing`


### `/api/v1/system/stats`

**GET** `/api/v1/system/stats`
- Function: `get_credit_system_stats`

**GET** `/api/v1/system/stats`
- Function: `get_credit_system_stats`


### `/api/v1/top-up/estimate`

**POST** `/api/v1/top-up/estimate`
- Function: `estimate_credit_purchase`

**POST** `/api/v1/top-up/estimate`
- Function: `estimate_credit_purchase`


### `/api/v1/top-up/history`

**GET** `/api/v1/top-up/history`
- Function: `get_top_up_history`

**GET** `/api/v1/top-up/history`
- Function: `get_top_up_history`


### `/api/v1/transactions`

**GET** `/api/v1/transactions`
- Function: `get_transaction_history`
- Response Model: `List`

**GET** `/api/v1/transactions`
- Function: `get_transaction_history`
- Response Model: `List`


### `/api/v1/transactions/search`

**GET** `/api/v1/transactions/search`
- Function: `search_transactions`
- Response Model: `List`

**GET** `/api/v1/transactions/search`
- Function: `search_transactions`
- Response Model: `List`


### `/api/v1/usage/monthly`

**GET** `/api/v1/usage/monthly`
- Function: `get_monthly_usage`
- Response Model: `MonthlyUsageSummary`

**GET** `/api/v1/usage/monthly`
- Function: `get_monthly_usage`
- Response Model: `MonthlyUsageSummary`


### `/api/v1/wallet/create`

**POST** `/api/v1/wallet/create`
- Function: `create_wallet`

**POST** `/api/v1/wallet/create`
- Function: `create_wallet`


### `/api/v1/wallet/summary`

**GET** `/api/v1/wallet/summary`
- Function: `get_wallet_summary`
- Response Model: `CreditWalletSummary`

**GET** `/api/v1/wallet/summary`
- Function: `get_wallet_summary`
- Response Model: `CreditWalletSummary`


## Discovery Routes
*Source: discovery_routes.py*


### `/api/v1/analytics/usage`

**GET** `/api/v1/analytics/usage`
- Function: `get_discovery_usage_stats`
- Response Model: `DiscoveryUsageStats`

**GET** `/api/v1/analytics/usage`
- Function: `get_discovery_usage_stats`
- Response Model: `DiscoveryUsageStats`


### `/api/v1/filters`

**POST** `/api/v1/filters`
- Function: `save_discovery_filter`
- Response Model: `DiscoveryFilterResponse`

**GET** `/api/v1/filters`
- Function: `get_discovery_filters`
- Response Model: `List`

**POST** `/api/v1/filters`
- Function: `save_discovery_filter`
- Response Model: `DiscoveryFilterResponse`

**GET** `/api/v1/filters`
- Function: `get_discovery_filters`
- Response Model: `List`


### `/api/v1/filters/categories`

**GET** `/api/v1/filters/categories`
- Function: `get_available_categories`

**GET** `/api/v1/filters/categories`
- Function: `get_available_categories`


### `/api/v1/filters/languages`

**GET** `/api/v1/filters/languages`
- Function: `get_available_languages`

**GET** `/api/v1/filters/languages`
- Function: `get_available_languages`


### `/api/v1/health`

**GET** `/api/v1/health`
- Function: `discovery_health_check`

**GET** `/api/v1/health`
- Function: `discovery_health_check`


### `/api/v1/page/{session_id}/{page_number}`

**GET** `/api/v1/page/{session_id}/{page_number}`
- Function: `get_discovery_page`
- Response Model: `DiscoverySearchResponse`

**GET** `/api/v1/page/{session_id}/{page_number}`
- Function: `get_discovery_page`
- Response Model: `DiscoverySearchResponse`


### `/api/v1/search`

**POST** `/api/v1/search`
- Function: `start_discovery_search`
- Response Model: `DiscoverySearchResponse`

**POST** `/api/v1/search`
- Function: `start_discovery_search`
- Response Model: `DiscoverySearchResponse`


### `/api/v1/unlock`

**POST** `/api/v1/unlock`
- Function: `unlock_profile`
- Response Model: `ProfileUnlockApiResponse`

**POST** `/api/v1/unlock`
- Function: `unlock_profile`
- Response Model: `ProfileUnlockApiResponse`


### `/api/v1/unlock/bulk`

**POST** `/api/v1/unlock/bulk`
- Function: `bulk_unlock_profiles`
- Response Model: `BulkProfileUnlockResponse`

**POST** `/api/v1/unlock/bulk`
- Function: `bulk_unlock_profiles`
- Response Model: `BulkProfileUnlockResponse`


### `/api/v1/unlocked`

**GET** `/api/v1/unlocked`
- Function: `get_unlocked_profiles`
- Response Model: `List`

**GET** `/api/v1/unlocked`
- Function: `get_unlocked_profiles`
- Response Model: `List`


## Engagement Routes
*Source: engagement_routes.py*


### `/api/v1/engagement/calculate/bulk`

**POST** `/api/v1/engagement/calculate/bulk`
- Function: `bulk_calculate_engagement`

**POST** `/api/v1/engagement/calculate/bulk`
- Function: `bulk_calculate_engagement`


### `/api/v1/engagement/calculate/post/{post_id}`

**POST** `/api/v1/engagement/calculate/post/{post_id}`
- Function: `calculate_post_engagement`

**POST** `/api/v1/engagement/calculate/post/{post_id}`
- Function: `calculate_post_engagement`


### `/api/v1/engagement/calculate/profile/{username}`

**POST** `/api/v1/engagement/calculate/profile/{username}`
- Function: `calculate_profile_engagement`

**POST** `/api/v1/engagement/calculate/profile/{username}`
- Function: `calculate_profile_engagement`


### `/api/v1/engagement/stats`

**GET** `/api/v1/engagement/stats`
- Function: `get_engagement_stats`

**GET** `/api/v1/engagement/stats`
- Function: `get_engagement_stats`


## Enhanced Instagram Routes
*Source: enhanced_instagram_routes.py*


### `/api/bulk/export`

**POST** `/api/bulk/export`
- Function: `bulk_export_profiles`

**POST** `/api/bulk/export`
- Function: `bulk_export_profiles`


### `/api/profile/{username}`

**GET** `/api/profile/{username}`
- Function: `get_instagram_profile_enhanced`
- Response Model: `EnhancedProfileResponse`

**GET** `/api/profile/{username}`
- Function: `get_instagram_profile_enhanced`
- Response Model: `EnhancedProfileResponse`


### `/api/profile/{username}/posts`

**GET** `/api/profile/{username}/posts`
- Function: `get_profile_posts_analytics`
- Response Model: `List`

**GET** `/api/profile/{username}/posts`
- Function: `get_profile_posts_analytics`
- Response Model: `List`


### `/api/search/advanced`

**GET** `/api/search/advanced`
- Function: `advanced_instagram_search`

**GET** `/api/search/advanced`
- Function: `advanced_instagram_search`


## Financial Management Routes
*Source: financial_management_routes.py*


### `/api/credits/adjust`

**POST** `/api/credits/adjust`
- Function: `adjust_user_credits`


### `/api/credits/bulk-adjust`

**POST** `/api/credits/bulk-adjust`
- Function: `bulk_adjust_credits`


### `/api/export/financial-report`

**GET** `/api/export/financial-report`
- Function: `export_financial_report`


### `/api/overview`

**GET** `/api/overview`
- Function: `get_financial_overview`
- Response Model: `FinancialOverviewResponse`


### `/api/revenue/metrics`

**GET** `/api/revenue/metrics`
- Function: `get_revenue_metrics`
- Response Model: `List`


### `/api/subscriptions/change`

**POST** `/api/subscriptions/change`
- Function: `change_user_subscription`


### `/api/transactions`

**GET** `/api/transactions`
- Function: `get_all_transactions`
- Response Model: `List`


### `/api/wallets`

**GET** `/api/wallets`
- Function: `get_all_credit_wallets`
- Response Model: `List`


## Health
*Source: health.py*


### `/api/health`

**GET** `/api/health`
- Function: `health_check`
- Response Model: `Dict`


### `/api/metrics`

**GET** `/api/metrics`
- Function: `system_metrics`
- Response Model: `Dict`


## Legacy Credit Routes
*Source: legacy_credit_routes.py*


### `/api/balance`

**GET** `/api/balance`
- Function: `get_credit_balance_legacy`

**GET** `/api/balance`
- Function: `get_credit_balance_legacy`


## Lists Routes
*Source: lists_routes.py*


### `/api/v1/available-profiles`

**GET** `/api/v1/available-profiles`
- Function: `get_available_profiles_for_lists`
- Response Model: `AvailableProfilesResponse`

**GET** `/api/v1/available-profiles`
- Function: `get_available_profiles_for_lists`
- Response Model: `AvailableProfilesResponse`


### `/api/v1/bulk-operations`

**POST** `/api/v1/bulk-operations`
- Function: `bulk_list_operations`
- Response Model: `BulkOperationResponse`

**POST** `/api/v1/bulk-operations`
- Function: `bulk_list_operations`
- Response Model: `BulkOperationResponse`


### `/api/v1/templates`

**GET** `/api/v1/templates`
- Function: `get_list_templates`

**GET** `/api/v1/templates`
- Function: `get_list_templates`


### `/api/v1/{list_id}`

**GET** `/api/v1/{list_id}`
- Function: `get_list`
- Response Model: `SingleListResponse`

**PUT** `/api/v1/{list_id}`
- Function: `update_list`
- Response Model: `SingleListResponse`

**DELETE** `/api/v1/{list_id}`
- Function: `delete_list`

**GET** `/api/v1/{list_id}`
- Function: `get_list`
- Response Model: `SingleListResponse`

**PUT** `/api/v1/{list_id}`
- Function: `update_list`
- Response Model: `SingleListResponse`

**DELETE** `/api/v1/{list_id}`
- Function: `delete_list`


### `/api/v1/{list_id}/duplicate`

**POST** `/api/v1/{list_id}/duplicate`
- Function: `duplicate_list`
- Response Model: `SingleListResponse`

**POST** `/api/v1/{list_id}/duplicate`
- Function: `duplicate_list`
- Response Model: `SingleListResponse`


### `/api/v1/{list_id}/items`

**POST** `/api/v1/{list_id}/items`
- Function: `add_profile_to_list`
- Response Model: `dict`

**POST** `/api/v1/{list_id}/items`
- Function: `add_profile_to_list`
- Response Model: `dict`


### `/api/v1/{list_id}/items/bulk`

**POST** `/api/v1/{list_id}/items/bulk`
- Function: `bulk_add_profiles_to_list`
- Response Model: `BulkOperationResponse`

**POST** `/api/v1/{list_id}/items/bulk`
- Function: `bulk_add_profiles_to_list`
- Response Model: `BulkOperationResponse`


### `/api/v1/{list_id}/items/{item_id}`

**PUT** `/api/v1/{list_id}/items/{item_id}`
- Function: `update_list_item`
- Response Model: `dict`

**DELETE** `/api/v1/{list_id}/items/{item_id}`
- Function: `remove_profile_from_list`

**PUT** `/api/v1/{list_id}/items/{item_id}`
- Function: `update_list_item`
- Response Model: `dict`

**DELETE** `/api/v1/{list_id}/items/{item_id}`
- Function: `remove_profile_from_list`


### `/api/v1/{list_id}/reorder`

**PUT** `/api/v1/{list_id}/reorder`
- Function: `reorder_list_items`

**PUT** `/api/v1/{list_id}/reorder`
- Function: `reorder_list_items`


## Proposal Management Routes
*Source: proposal_management_routes.py*


### `/api/`

**GET** `/api/`
- Function: `get_all_proposals`
- Response Model: `List`

**POST** `/api/`
- Function: `create_proposal`
- Response Model: `ProposalDetailResponse`


### `/api/analytics`

**GET** `/api/analytics`
- Function: `get_proposal_analytics`
- Response Model: `ProposalAnalyticsResponse`


### `/api/templates/`

**GET** `/api/templates/`
- Function: `get_proposal_templates`
- Response Model: `List`

**POST** `/api/templates/`
- Function: `create_proposal_template`
- Response Model: `TemplateResponse`


### `/api/{proposal_id}`

**GET** `/api/{proposal_id}`
- Function: `get_proposal_details`
- Response Model: `ProposalDetailResponse`

**PUT** `/api/{proposal_id}`
- Function: `update_proposal`
- Response Model: `ProposalDetailResponse`


## Settings Routes
*Source: settings_routes.py*


### `/api/v1/notifications`

**GET** `/api/v1/notifications`
- Function: `get_notification_preferences`
- Response Model: `NotificationPreferencesResponse`

**PUT** `/api/v1/notifications`
- Function: `update_notification_preferences`
- Response Model: `NotificationPreferencesResponse`

**GET** `/api/v1/notifications`
- Function: `get_notification_preferences`
- Response Model: `NotificationPreferencesResponse`

**PUT** `/api/v1/notifications`
- Function: `update_notification_preferences`
- Response Model: `NotificationPreferencesResponse`


### `/api/v1/overview`

**GET** `/api/v1/overview`
- Function: `get_complete_settings_overview`
- Response Model: `UserSettingsOverview`

**GET** `/api/v1/overview`
- Function: `get_complete_settings_overview`
- Response Model: `UserSettingsOverview`


### `/api/v1/preferences`

**GET** `/api/v1/preferences`
- Function: `get_user_preferences`
- Response Model: `UserPreferencesResponse`

**PUT** `/api/v1/preferences`
- Function: `update_user_preferences`
- Response Model: `UserPreferencesResponse`

**GET** `/api/v1/preferences`
- Function: `get_user_preferences`
- Response Model: `UserPreferencesResponse`

**PUT** `/api/v1/preferences`
- Function: `update_user_preferences`
- Response Model: `UserPreferencesResponse`


### `/api/v1/profile`

**GET** `/api/v1/profile`
- Function: `get_user_profile`
- Response Model: `ProfileUpdateResponse`

**PUT** `/api/v1/profile`
- Function: `update_user_profile`
- Response Model: `ProfileUpdateResponse`

**GET** `/api/v1/profile`
- Function: `get_user_profile`
- Response Model: `ProfileUpdateResponse`

**PUT** `/api/v1/profile`
- Function: `update_user_profile`
- Response Model: `ProfileUpdateResponse`


### `/api/v1/security/2fa`

**POST** `/api/v1/security/2fa`
- Function: `toggle_two_factor_auth`
- Response Model: `TwoFactorToggleResponse`

**POST** `/api/v1/security/2fa`
- Function: `toggle_two_factor_auth`
- Response Model: `TwoFactorToggleResponse`


### `/api/v1/security/password`

**POST** `/api/v1/security/password`
- Function: `change_password`
- Response Model: `PasswordChangeResponse`

**POST** `/api/v1/security/password`
- Function: `change_password`
- Response Model: `PasswordChangeResponse`


### `/api/v1/security/privacy`

**PUT** `/api/v1/security/privacy`
- Function: `update_privacy_settings`
- Response Model: `PrivacySettingsResponse`

**PUT** `/api/v1/security/privacy`
- Function: `update_privacy_settings`
- Response Model: `PrivacySettingsResponse`


## System Monitoring Routes
*Source: system_monitoring_routes.py*


### `/api/admin-actions`

**GET** `/api/admin-actions`
- Function: `get_admin_actions_summary`
- Response Model: `AdminActionsSummaryResponse`


### `/api/analytics`

**GET** `/api/analytics`
- Function: `get_platform_analytics`
- Response Model: `PlatformAnalyticsResponse`


### `/api/health`

**GET** `/api/health`
- Function: `get_system_health`
- Response Model: `SystemHealthResponse`


### `/api/maintenance-mode`

**POST** `/api/maintenance-mode`
- Function: `toggle_maintenance_mode`


### `/api/performance`

**GET** `/api/performance`
- Function: `get_system_performance`
- Response Model: `SystemPerformanceResponse`


### `/api/user-activity`

**GET** `/api/user-activity`
- Function: `get_user_activity_stats`
- Response Model: `UserActivityStatsResponse`


## User Management Routes
*Source: user_management_routes.py*


### `/api/`

**GET** `/api/`
- Function: `get_all_users`
- Response Model: `UserListResponse`

**POST** `/api/`
- Function: `create_user`
- Response Model: `UserDetailResponse`


### `/api/bulk-update`

**POST** `/api/bulk-update`
- Function: `bulk_update_users`


### `/api/export/csv`

**GET** `/api/export/csv`
- Function: `export_users_csv`


### `/api/{user_id}`

**GET** `/api/{user_id}`
- Function: `get_user_details`
- Response Model: `UserDetailResponse`

**PUT** `/api/{user_id}`
- Function: `update_user`
- Response Model: `UserDetailResponse`

**DELETE** `/api/{user_id}`
- Function: `delete_user`


### `/api/{user_id}/activity`

**GET** `/api/{user_id}/activity`
- Function: `get_user_activity`
- Response Model: `List`


---

## Response Format

### Success Response
```json
{
  "status": "success",
  "data": { ... },
  "message": "Optional success message"
}
```

### Error Response
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Common Status Codes
- `200` - OK
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## Rate Limiting
- Maximum 500 requests per hour per user
- Maximum 5 concurrent requests

## Credits System
Many endpoints consume credits from the user's credit wallet. Credit costs are returned in response headers when applicable.

