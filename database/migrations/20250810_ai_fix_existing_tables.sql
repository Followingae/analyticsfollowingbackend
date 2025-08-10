-- AI Analysis Job Tracking - Fix Existing Tables
-- Fixes any missing columns in existing tables
-- Date: 2025-08-10

-- First, let's check what columns exist in the tables
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'ai_analysis_jobs'
ORDER BY ordinal_position;

SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'ai_analysis_job_logs'
ORDER BY ordinal_position;

-- Add missing columns to ai_analysis_job_logs if they don't exist
DO $$
BEGIN
    -- Check if created_at column exists in ai_analysis_job_logs
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE ai_analysis_job_logs ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    
    -- Check if log_level column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'log_level'
    ) THEN
        ALTER TABLE ai_analysis_job_logs ADD COLUMN log_level VARCHAR(20) NOT NULL DEFAULT 'info';
    END IF;
    
    -- Check if message column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'message'
    ) THEN
        ALTER TABLE ai_analysis_job_logs ADD COLUMN message TEXT NOT NULL DEFAULT '';
    END IF;
    
    -- Check if log_metadata column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'log_metadata'
    ) THEN
        ALTER TABLE ai_analysis_job_logs ADD COLUMN log_metadata JSONB DEFAULT '{}';
    END IF;
END
$$;

-- Add missing columns to ai_analysis_jobs if they don't exist
DO $$
BEGIN
    -- Check and add missing columns one by one
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'posts_processed'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN posts_processed INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'posts_successful'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN posts_successful INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'posts_failed'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN posts_failed INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'total_posts'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN total_posts INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'profile_analysis_completed'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN profile_analysis_completed BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'data_consistency_validated'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN data_consistency_validated BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'processing_duration_seconds'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN processing_duration_seconds FLOAT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'posts_per_second'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN posts_per_second FLOAT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'last_heartbeat'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN last_heartbeat TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'heartbeat_count'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN heartbeat_count INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'error_message'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN error_message TEXT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'error_count'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN error_count INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'max_retries'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN max_retries INTEGER DEFAULT 3;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'started_at'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN started_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'completed_at'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE ai_analysis_jobs ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END
$$;

-- Now create indexes safely (only if columns exist)
DO $$
BEGIN
    -- Only create indexes if the columns exist
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'job_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_jobs_job_id'
    ) THEN
        CREATE INDEX idx_ai_analysis_jobs_job_id ON ai_analysis_jobs(job_id);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'profile_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_jobs_profile_id'
    ) THEN
        CREATE INDEX idx_ai_analysis_jobs_profile_id ON ai_analysis_jobs(profile_id);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'user_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_jobs_user_id'
    ) THEN
        CREATE INDEX idx_ai_analysis_jobs_user_id ON ai_analysis_jobs(user_id);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'status'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_jobs_status'
    ) THEN
        CREATE INDEX idx_ai_analysis_jobs_status ON ai_analysis_jobs(status);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_jobs' 
        AND column_name = 'created_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_jobs_created_at'
    ) THEN
        CREATE INDEX idx_ai_analysis_jobs_created_at ON ai_analysis_jobs(created_at);
    END IF;
    
    -- Indexes for ai_analysis_job_logs (only if columns exist)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'job_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_job_logs_job_id'
    ) THEN
        CREATE INDEX idx_ai_analysis_job_logs_job_id ON ai_analysis_job_logs(job_id);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'created_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_job_logs_created_at'
    ) THEN
        CREATE INDEX idx_ai_analysis_job_logs_created_at ON ai_analysis_job_logs(created_at);
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'ai_analysis_job_logs' 
        AND column_name = 'log_level'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_ai_analysis_job_logs_level'
    ) THEN
        CREATE INDEX idx_ai_analysis_job_logs_level ON ai_analysis_job_logs(log_level);
    END IF;
END
$$;

-- Verification: Show final table structures
SELECT 'ai_analysis_jobs columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'ai_analysis_jobs'
ORDER BY ordinal_position;

SELECT 'ai_analysis_job_logs columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'ai_analysis_job_logs'
ORDER BY ordinal_position;

SELECT 'Tables fixed and ready!' as result;