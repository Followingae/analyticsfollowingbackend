# USD Column Renaming Analysis

## Tables Requiring Column Renames

### 1. credit_top_up_orders
- `price_usd_cents` → `price_cents`
- Keep `currency` column (will reference team_currency_settings)

### 2. influencer_pricing
- `story_price_usd_cents` → `story_price_cents`
- `post_price_usd_cents` → `post_price_cents`
- `reel_price_usd_cents` → `reel_price_cents`
- `ugc_video_price_usd_cents` → `ugc_video_price_cents`
- `story_series_price_usd_cents` → `story_series_price_cents`
- `carousel_post_price_usd_cents` → `carousel_post_price_cents`
- `igtv_price_usd_cents` → `igtv_price_cents`

### 3. influencer_applications
- `proposed_package_price_usd_cents` → `proposed_package_price_cents`
- `proposed_post_price_usd_cents` → `proposed_post_price_cents`
- `proposed_reel_price_usd_cents` → `proposed_reel_price_cents`
- `proposed_story_price_usd_cents` → `proposed_story_price_cents`

### 4. proposal_influencers
- `post_price_usd_cents` → `post_price_cents`
- `reel_price_usd_cents` → `reel_price_cents`
- `story_price_usd_cents` → `story_price_cents`

### 5. proposal_collaborations
- `payment_amount_usd` → `payment_amount_cents` (convert from dollars to cents for consistency)

### 6. profiles
- `cost_price_usd` → `cost_price_cents` (convert from dollars to cents)
- `sell_price_usd` → `sell_price_cents` (convert from dollars to cents)

### 7. user_list_items
- `estimated_cost` → Keep as is (already generic)

## Migration Strategy

### Phase 1: Add New Columns (Backward Compatible)
- Add new generic columns alongside existing USD columns
- Populate new columns with existing data
- Update application code to use new columns

### Phase 2: Remove Old Columns (Breaking Change)
- Drop old USD-specific columns
- Update database constraints and indexes

## Conversion Rules
- All `_usd` fields (dollar amounts) → convert to cents and rename to `_cents`
- All `_usd_cents` fields → rename to `_cents`
- Maintain data integrity during conversion