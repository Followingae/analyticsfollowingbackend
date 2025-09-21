# Concurrent Creator Analytics & Bulk Search Implementation Requirements

## Current Limitations

1. **Single Active Search**: User must wait for current search to complete before starting another
2. **No Batch Processing**: Cannot search multiple creators simultaneously per user

## Business Requirements

As the senior CTO for a large silicon valley tech company, we need to implement the possibility for users to have multiple creator search analytics being processed at the same time.

There is no worry about it taking time, as they complete they can be served as per our individual approach, but the user should not have to wait until one creator analytics search to fully be completed to start another.

Comprehensively study all our creator analytics flows and how we can handle this in a robust way similar to how Modash would be doing this.

## Feature Requirements

### 1. Concurrent Individual Searches
- Users can start multiple creator searches without waiting for previous ones to complete
- Each search should be processed independently
- Results delivered as individual searches complete

### 2. Bulk Search Feature
- **Maximum Limit**: Up to 15 creators per bulk search
- **Input Method**: Multiple usernames separated by comma
- **Processing**: Run creator analytics for all creators in one search request

## Technical Implementation Guidelines

### Apify Multiple Input Guidelines

#### Passing an input to the Actor

The fastest way to get results from an Actor is to pass input directly to the `call` function. Input can be passed to `call` function and the reference of running Actor (or wait for finish) is available in `runData` variable.

This example starts an Actor that scrapes 20 posts from the Instagram website based on the hashtag.

```javascript
import { ApifyClient } from 'apify-client';

// Client initialization with the API token
const client = new ApifyClient({ token: 'MY_APIFY_TOKEN' });

const actorClient = client.actor('apify/instagram-hashtag-scraper');

const input = { hashtags: ['rainbow'], resultsLimit: 20 };

// Run the Actor and wait for it to finish up to 60 seconds.
// Input is not persisted for next runs.
const runData = await actorClient.call(input, { waitSecs: 60 });

console.log('Run data:');
console.log(runData);
```

To run multiple inputs with the same Actor, most convenient way is to create multiple [tasks](https://docs.apify.com/platform/actors/running/tasks) with different inputs. Task input is persisted on Apify platform when task is created.

```javascript
import { ApifyClient } from 'apify-client';

// Client initialization with the API token
const client = new ApifyClient({ token: 'MY_APIFY_TOKEN' });

const animalsHashtags = ['zebra', 'lion', 'hippo'];

// Multiple input schemas for one Actor can be persisted in tasks.
// Tasks are saved in the Apify platform and can be run multiple times.
const socialsTasksPromises = animalsHashtags.map((hashtag) =>
    client.tasks().create({
        actId: 'apify/instagram-hashtag-scraper',
        name: `hashtags-${hashtag}`,
        input: { hashtags: [hashtag], resultsLimit: 20 },
        options: { memoryMbytes: 1024 },
    }),
);

// Create all tasks in parallel
const createdTasks = await Promise.all(socialsTasksPromises);

console.log('Created tasks:');
console.log(createdTasks);

// Run all tasks in parallel
await Promise.all(createdTasks.map((task) => client.task(task.id).call()));
```

#### Getting latest data from an Actor, joining datasets

Actor data are stored to [datasets](https://docs.apify.com/platform/storage/dataset). Datasets can be retrieved from Actor runs. Dataset items can be listed with pagination. Also, datasets can be merged together to make analysis further on with single file as dataset can be exported to various data format (CSV, JSON, XSLX, XML). [Integrations](https://docs.apify.com/platform/integrations) can do the trick as well.

```javascript
import { ApifyClient } from 'apify-client';

// Client initialization with the API token
const client = new ApifyClient({ token: 'MY_APIFY_TOKEN' });

const actorClient = client.actor('apify/instagram-hashtag-scraper');

const actorRuns = actorClient.runs();

// See pagination to understand how to get more datasets
const actorDatasets = await actorRuns.list({ limit: 20 });

console.log('Actor datasets:');
console.log(actorDatasets);

const mergingDataset = await client.datasets().getOrCreate('merge-dataset');

for (const datasetItem of actorDatasets.items) {
    // Dataset items can be handled here. Dataset items can be paginated
    const datasetItems = await client.dataset(datasetItem.defaultDatasetId).listItems({ limit: 1000 });

    // Items can be pushed to single dataset
    await client.dataset(mergingDataset.id).pushItems(datasetItems.items);

    // ...
}
```

#### Handling webhooks

[Webhooks](https://docs.apify.com/platform/integrations/webhooks) can be used to get notifications about Actor runs. For example, a webhook can be triggered when an Actor run finishes successfully. Webhook can receive dataset ID for further processing.

Initialization of webhook:

```javascript
import { ApifyClient } from 'apify-client';

// Client initialization with the API token
const client = new ApifyClient({ token: 'MY_APIFY_TOKEN' });

const webhooksClient = client.webhooks();

await webhooksClient.create({
    description: 'Instagram hashtag actor succeeded',
    condition: { actorId: 'reGe1ST3OBgYZSsZJ' }, // Actor ID of apify/instagram-hashtag-scraper
    // Request URL can be generated using https://webhook.site. Any REST server can be used
    requestUrl: 'https://webhook.site/CUSTOM_WEBHOOK_ID',
    eventTypes: ['ACTOR.RUN.SUCCEEDED'],
});
```

Simple webhook listener can be built on [`express`](https://expressjs.com/) library, which can helps to create a REST server for handling webhooks:

```javascript
import express from 'express';
import bodyParser from 'body-parser';
import { ApifyClient, DownloadItemsFormat } from 'apify-client';

// Initialize Apify client, express and define server port
const client = new ApifyClient({ token: 'MY_APIFY_TOKEN' });
const app = express();
const PORT = 3000;

// Tell express to use body-parser's JSON parsing
app.use(bodyParser.json());

app.post('apify-webhook', async (req, res) => {
    // Log the payload from the webhook
    console.log(req.body);

    const runDataset = await client.dataset(req.body.resource.defaultDatasetId);

    // e.g. Save dataset locally as JSON
    await runDataset.downloadItems(DownloadItemsFormat.JSON);

    // Respond to the webhook
    res.send('Webhook received');
});

// Start express on the defined port
app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));
```

## Implementation Plan Summary

Before you start coding, ultrathink and give me your plan of implementation for these 2. Ensure you check our codebase comprehensively to make this seamless with our process, and cross-verify what we need and what's there already using cloudflare mcp and supabase mcp.

## 🏗️ Enterprise-Grade Concurrent Creator Analytics Implementation Plan

Based on comprehensive analysis of current architecture, here's the strategic implementation plan for concurrent and bulk creator analytics processing:

### 📊 Current System Assessment

#### Existing Assets We Can Leverage:
✅ **Redis Infrastructure** - Already configured for caching, can extend for job queuing
✅ **Celery Workers** - Background processing foundation exists
✅ **AI Manager Singleton** - Designed for concurrent model usage
✅ **Database Schema** - Robust foundation with proper indexing
✅ **Credit System** - Atomic transaction handling already implemented
✅ **Apify Client** - Supports batch processing patterns

#### Critical Gaps to Address:
⚠️ **Job Queue Management** - No async job tracking system
⚠️ **Real-time Status Updates** - No WebSocket/SSE implementation
⚠️ **Bulk Processing Logic** - Single-item processing only
⚠️ **Concurrent Resource Management** - AI/Database pool limits

### 🎯 Implementation Strategy: 4-Phase Approach

#### Phase 1: Job Queue Infrastructure (Foundation)

##### 1.1 Enhanced Database Schema
```sql
-- New job management tables
CREATE TABLE creator_analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    team_id UUID REFERENCES teams(id),
    job_type VARCHAR(20) NOT NULL, -- 'single' or 'bulk'
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    priority INTEGER DEFAULT 0,

    -- Job configuration
    usernames TEXT[] NOT NULL, -- Array of usernames to process
    total_creators INTEGER NOT NULL,
    completed_creators INTEGER DEFAULT 0,
    failed_creators INTEGER DEFAULT 0,

    -- Credit management
    estimated_credits INTEGER NOT NULL,
    credits_charged INTEGER DEFAULT 0,
    credits_reserved BOOLEAN DEFAULT false,

    -- Progress tracking
    progress_percentage FLOAT DEFAULT 0.0,
    current_stage VARCHAR(50),
    detailed_status JSONB DEFAULT '{}',

    -- Results
    results JSONB DEFAULT '[]',
    error_details JSONB DEFAULT '{}',

    -- Timing
    created_at TIMESTAMP DEFAULT now(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion_at TIMESTAMP,

    -- Metadata
    job_metadata JSONB DEFAULT '{}',

    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_job_type CHECK (job_type IN ('single', 'bulk'))
);

-- Individual creator job tracking
CREATE TABLE creator_job_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES creator_analysis_jobs(id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,

    -- Processing stages
    apify_completed BOOLEAN DEFAULT false,
    database_populated BOOLEAN DEFAULT false,
    cdn_processed BOOLEAN DEFAULT false,
    ai_analyzed BOOLEAN DEFAULT false,

    -- Results
    profile_id UUID REFERENCES profiles(id),
    result_data JSONB,
    error_message TEXT,

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_duration INTEGER, -- seconds

    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),

    UNIQUE(job_id, username)
);

-- Job queue for worker processing
CREATE TABLE job_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES creator_analysis_jobs(id),
    queue_name VARCHAR(50) NOT NULL DEFAULT 'creator_analysis',
    priority INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP DEFAULT now(),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    worker_id VARCHAR(100),
    processed_at TIMESTAMP,

    INDEX idx_job_queue_priority_scheduled (priority DESC, scheduled_at ASC),
    INDEX idx_job_queue_status (job_id, processed_at)
);
```

##### 1.2 Advanced Job Management Service
```python
# app/services/job_management_service.py
class CreatorAnalysisJobManager:
    """
    Enterprise-grade job management for concurrent creator analytics
    Handles job queuing, status tracking, and resource allocation
    """

    async def submit_single_creator_job(self, username: str, user_id: UUID, team_id: UUID) -> UUID:
        """Submit single creator analysis job (non-blocking)"""

    async def submit_bulk_creator_job(self, usernames: List[str], user_id: UUID, team_id: UUID) -> UUID:
        """Submit bulk creator analysis job (up to 15 creators)"""

    async def get_job_status(self, job_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Get comprehensive job status with progress details"""

    async def get_user_active_jobs(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get all active jobs for a user"""

    async def cancel_job(self, job_id: UUID, user_id: UUID) -> bool:
        """Cancel a pending/processing job"""
```

#### Phase 2: Concurrent Processing Engine

##### 2.1 Enhanced Background Worker System
```python
# app/workers/concurrent_creator_processor.py
class ConcurrentCreatorProcessor:
    """
    High-performance concurrent creator analysis processor
    Handles multiple jobs simultaneously with resource management
    """

    def __init__(self):
        self.max_concurrent_jobs = 10  # Per worker instance
        self.ai_model_pool = AIModelPool(max_size=5)
        self.apify_client_pool = ApifyClientPool(max_size=3)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_jobs)

    async def process_creator_job(self, job_id: UUID):
        """Process individual creator analysis job"""
        async with self.semaphore:
            # Process with resource pooling
            pass

    async def process_bulk_job(self, job_id: UUID):
        """Process bulk creator analysis job"""
        # Split into concurrent individual jobs
        pass
```

##### 2.2 Resource Pool Management
```python
# app/infrastructure/resource_pools.py
class AIModelPool:
    """Shared AI model pool for concurrent processing"""

class ApifyClientPool:
    """Managed Apify client pool with rate limiting"""

class DatabaseConnectionPool:
    """Enhanced database connection management"""
```

#### Phase 3: Bulk Search Implementation

##### 3.1 Bulk API Endpoints
```python
# New endpoints in main.py or dedicated routes file
@app.post("/api/v1/instagram/bulk-search")
async def bulk_creator_search(
    request: BulkSearchRequest,  # usernames: List[str], max 15
    current_user=Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Submit bulk creator analysis job
    Returns job_id for tracking progress
    """

@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(
    job_id: UUID,
    current_user=Depends(get_current_active_user),
    db=Depends(get_db)
):
    """Get real-time job status and progress"""

@app.get("/api/v1/jobs/{job_id}/results")
async def get_job_results(
    job_id: UUID,
    current_user=Depends(get_current_active_user),
    db=Depends(get_db)
):
    """Get completed results (supports partial results)"""
```

##### 3.2 Enhanced Apify Integration
```python
# app/scrapers/bulk_apify_client.py
class BulkApifyClient(ApifyInstagramClient):
    """
    Enhanced Apify client supporting bulk operations
    Based on Apify's multiple input guidelines
    """

    async def get_multiple_profiles_comprehensive(self, usernames: List[str]) -> Dict[str, Any]:
        """
        Bulk profile scraping using Apify's task-based approach
        Creates multiple tasks and processes them in parallel
        """

        # Create multiple tasks for parallel processing
        tasks = []
        for username in usernames:
            task = await self._create_profile_task(username)
            tasks.append(task)

        # Process all tasks in parallel
        results = await asyncio.gather(*[
            self._execute_task(task) for task in tasks
        ], return_exceptions=True)

        return self._consolidate_results(usernames, results)
```

#### Phase 4: Real-time Updates & User Experience

##### 4.1 WebSocket Integration
```python
# app/websockets/job_updates.py
class JobStatusWebSocket:
    """Real-time job status updates via WebSocket"""

    async def connect_user(self, user_id: UUID, websocket: WebSocket):
        """Connect user to job updates"""

    async def broadcast_job_update(self, job_id: UUID, status_update: Dict):
        """Broadcast job status to connected users"""
```

##### 4.2 Enhanced Frontend Integration
```typescript
// Frontend job management interface
interface JobManager {
  submitSingleCreator(username: string): Promise<JobSubmission>
  submitBulkCreators(usernames: string[]): Promise<JobSubmission>
  subscribeToJobUpdates(jobId: string): WebSocket
  getJobResults(jobId: string): Promise<CreatorAnalytics[]>
}
```

### 🔧 Technical Implementation Details

#### Credit System Enhancement
```python
# Enhanced credit validation for bulk operations
async def validate_bulk_credits(self, user_id: UUID, usernames: List[str]) -> BulkCreditValidation:
    """
    Atomic credit validation for bulk operations
    - Calculate total cost (25 credits × new creators + 5 credits × existing creators)
    - Reserve credits before job starts
    - Charge incrementally as creators complete
    - Refund if job cancelled
    """
```

#### Apify Rate Limiting Strategy
```python
# Smart rate limiting for bulk operations
class ApifyRateLimiter:
    """
    Intelligent rate limiting for Apify API
    - Respects Apify's rate limits
    - Distributes requests optimally
    - Handles backpressure gracefully
    """
```

#### AI Processing Optimization
```python
# Optimized AI processing for concurrent jobs
async def process_ai_analysis_batch(self, profiles_data: List[Dict]) -> List[AIAnalysisResult]:
    """
    Batch AI processing with smart resource allocation
    - Groups similar analysis types
    - Maximizes GPU/CPU utilization
    - Maintains quality standards
    """
```

### 📊 Performance Targets

#### Concurrent Processing Capacity
- **Single User**: Up to 5 concurrent creator searches
- **System-wide**: 100+ concurrent jobs across all users
- **Bulk Processing**: 15 creators in ~180-240 seconds (parallel processing)
- **Resource Efficiency**: 80%+ AI model utilization

#### User Experience Metrics
- **Job Submission**: <500ms response time
- **Status Updates**: <2s real-time updates via WebSocket
- **Partial Results**: Available as individual creators complete
- **Error Recovery**: Automatic retry with exponential backoff

### 🛡️ Risk Mitigation

#### Resource Protection
- **Memory Management**: AI model pool prevents memory leaks
- **Database Connections**: Connection pooling prevents exhaustion
- **API Rate Limits**: Smart throttling prevents Apify blocking

#### Error Handling
- **Individual Job Isolation**: One failed creator doesn't affect others
- **Graceful Degradation**: System continues operating under partial failures
- **Credit Protection**: Atomic transactions prevent credit loss

### 🚀 Implementation Timeline

**Week 1-2**: Phase 1 - Job queue infrastructure
**Week 3-4**: Phase 2 - Concurrent processing engine
**Week 5-6**: Phase 3 - Bulk search implementation
**Week 7-8**: Phase 4 - Real-time updates & optimization

This architecture will transform your platform into an enterprise-grade concurrent analytics system, matching the capabilities of platforms like Modash while maintaining your existing reliability and quality standards.

---

*Document created: January 2025*
*Status: Requirements & Implementation Plan*
*Next Steps: Begin Phase 1 Implementation*