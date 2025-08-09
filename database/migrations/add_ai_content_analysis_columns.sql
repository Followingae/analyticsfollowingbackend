-- =====================================================================================
-- AI CONTENT ANALYSIS COLUMNS MIGRATION
-- Extends existing tables with AI/ML content intelligence capabilities
-- Non-breaking changes - all columns are optional and backwards compatible
-- =====================================================================================

-- EXTEND POSTS TABLE WITH AI CONTENT ANALYSIS
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_content_category VARCHAR(50);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_category_confidence FLOAT DEFAULT 0.0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_sentiment VARCHAR(20);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_sentiment_score FLOAT DEFAULT 0.0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_sentiment_confidence FLOAT DEFAULT 0.0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_language_code VARCHAR(10);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_language_confidence FLOAT DEFAULT 0.0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_analysis_raw JSONB;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_analyzed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ai_analysis_version VARCHAR(20) DEFAULT '1.0.0';

-- EXTEND PROFILES TABLE WITH AGGREGATED AI INSIGHTS
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_primary_content_type VARCHAR(50);
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_content_distribution JSONB; -- {"Fashion": 0.4, "Travel": 0.3, etc}
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_avg_sentiment_score FLOAT DEFAULT 0.0;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_language_distribution JSONB;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_content_quality_score FLOAT DEFAULT 0.0;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ai_profile_analyzed_at TIMESTAMP WITH TIME ZONE;

-- RENAME EXISTING CATEGORY COLUMN FOR CLARITY (BACKWARDS COMPATIBLE)
-- Keep the original column, just add alias for new AI-determined category
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS instagram_business_category VARCHAR(100);

-- Copy existing category data to new column if not already done
UPDATE profiles 
SET instagram_business_category = category 
WHERE instagram_business_category IS NULL AND category IS NOT NULL;

-- ADD PERFORMANCE INDEXES FOR AI QUERIES
CREATE INDEX IF NOT EXISTS idx_posts_ai_content_category ON posts(ai_content_category) WHERE ai_content_category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_posts_ai_sentiment ON posts(ai_sentiment) WHERE ai_sentiment IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_posts_ai_language ON posts(ai_language_code) WHERE ai_language_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_posts_ai_analyzed_at ON posts(ai_analyzed_at) WHERE ai_analyzed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_ai_content_type ON profiles(ai_primary_content_type) WHERE ai_primary_content_type IS NOT NULL;

-- ADD COMMENTS FOR DOCUMENTATION
COMMENT ON COLUMN posts.ai_content_category IS 'AI-determined content category (Fashion, Tech, Travel, etc.)';
COMMENT ON COLUMN posts.ai_category_confidence IS 'Confidence score for content category (0.0-1.0)';
COMMENT ON COLUMN posts.ai_sentiment IS 'Post sentiment: positive, negative, neutral';
COMMENT ON COLUMN posts.ai_sentiment_score IS 'Sentiment score (-1.0 to +1.0)';
COMMENT ON COLUMN posts.ai_sentiment_confidence IS 'Confidence in sentiment analysis (0.0-1.0)';
COMMENT ON COLUMN posts.ai_language_code IS 'Detected language ISO code (en, ar, fr, etc.)';
COMMENT ON COLUMN posts.ai_language_confidence IS 'Language detection confidence (0.0-1.0)';
COMMENT ON COLUMN posts.ai_analysis_raw IS 'Full AI analysis results in JSON format';
COMMENT ON COLUMN posts.ai_analyzed_at IS 'Timestamp when AI analysis was performed';
COMMENT ON COLUMN posts.ai_analysis_version IS 'Version of AI models used for analysis';

COMMENT ON COLUMN profiles.ai_primary_content_type IS 'Primary content category for this profile based on posts';
COMMENT ON COLUMN profiles.ai_content_distribution IS 'Distribution of content types as JSON {"Fashion": 0.4, "Travel": 0.3}';
COMMENT ON COLUMN profiles.ai_avg_sentiment_score IS 'Average sentiment score across all posts';
COMMENT ON COLUMN profiles.ai_language_distribution IS 'Language distribution as JSON {"en": 0.8, "ar": 0.2}';
COMMENT ON COLUMN profiles.ai_content_quality_score IS 'AI-assessed overall content quality (0.0-1.0)';
COMMENT ON COLUMN profiles.instagram_business_category IS 'Original Instagram business category';

-- MIGRATION COMPLETE
-- Next steps:
-- 1. Update unified_models.py with new AI columns
-- 2. Create ContentIntelligenceService
-- 3. Implement background AI analysis