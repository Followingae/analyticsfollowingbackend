# Frontend Migration Guide: Async Post Analytics

## 🚀 Overview

The backend now supports **ASYNC POST ANALYTICS** for adding posts to campaigns. This solves the critical issue where the backend would become unresponsive during post analytics, preventing users from navigating the frontend.

## ✅ Benefits of Async Mode

1. **Backend stays responsive** - Users can navigate freely while posts are processing
2. **No timeout issues** - Long-running analytics won't cause request timeouts
3. **Progress tracking** - Real-time status updates during processing
4. **Better UX** - Users can continue working instead of waiting

## 🔄 Migration Strategy

The system supports both modes during transition:
- **`async_mode=true`** (DEFAULT) - New non-blocking mode
- **`async_mode=false`** - Legacy blocking mode (deprecated)

## 📡 API Changes

### Step 1: Add Post to Campaign (Async)

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/posts?async_mode=true`

**Request:**
```json
{
  "instagram_post_url": "https://www.instagram.com/p/ABC123/"
}
```

**Immediate Response (returns in <1 second):**
```json
{
  "success": true,
  "mode": "async",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Post analytics job queued. Poll status endpoint for progress.",
  "status_url": "/api/v1/campaigns/jobs/550e8400-e29b-41d4-a716-446655440000/status",
  "result_url": "/api/v1/campaigns/jobs/550e8400-e29b-41d4-a716-446655440000/result",
  "estimated_time_seconds": 180,
  "deprecation_notice": null
}
```

### Step 2: Poll for Status

**Endpoint:** `GET /api/v1/campaigns/jobs/{job_id}/status`

**Poll every 5 seconds until status is "completed" or "failed"**

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",  // "pending" | "processing" | "completed" | "failed"
  "progress_percent": 45,
  "current_stage": "ai_analysis",  // "queued" | "apify" | "cdn_processing" | "ai_analysis" | "complete"
  "estimated_remaining_seconds": 95,
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:00:02Z",
  "completed_at": null,
  "error": null
}
```

### Step 3: Get Results (when completed)

**Endpoint:** `GET /api/v1/campaigns/jobs/{job_id}/result`

**Response (same as synchronous mode):**
```json
{
  "success": true,
  "campaign_post_id": "7761bce3-2b23-4a8a-b995-296212a1e958",
  "post_analysis": {
    "post_id": "...",
    "profile": { /* complete profile data */ },
    "post": { /* complete post data with AI analysis */ },
    "audience_demographics": [ /* complete demographics */ ]
  },
  "added_at": "2024-01-15T10:03:15Z",
  "message": "Post added to campaign successfully"
}
```

## 💻 Frontend Implementation

### React/TypeScript Example

```typescript
// 1. Add post to campaign (returns immediately)
const addPostToCampaign = async (campaignId: string, postUrl: string) => {
  const response = await fetch(
    `/api/v1/campaigns/${campaignId}/posts?async_mode=true`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instagram_post_url: postUrl })
    }
  );

  const data = await response.json();

  if (data.mode === 'async') {
    // Start polling for status
    pollJobStatus(data.job_id);

    // Show non-blocking UI
    showProgressModal({
      message: "Processing post analytics...",
      jobId: data.job_id
    });
  }

  return data;
};

// 2. Poll for job status
const pollJobStatus = async (jobId: string) => {
  const interval = setInterval(async () => {
    try {
      const response = await fetch(`/api/v1/campaigns/jobs/${jobId}/status`);
      const status = await response.json();

      // Update progress UI
      updateProgress({
        percent: status.progress_percent,
        stage: status.current_stage,
        estimatedRemaining: status.estimated_remaining_seconds
      });

      // Check if completed
      if (status.status === 'completed') {
        clearInterval(interval);
        const result = await getJobResult(jobId);
        handleSuccess(result);
      } else if (status.status === 'failed') {
        clearInterval(interval);
        handleError(status.error);
      }
    } catch (error) {
      clearInterval(interval);
      handleError(error);
    }
  }, 5000); // Poll every 5 seconds
};

// 3. Get final results
const getJobResult = async (jobId: string) => {
  const response = await fetch(`/api/v1/campaigns/jobs/${jobId}/result`);
  return await response.json();
};
```

## 🎨 UI/UX Recommendations

### Progress Modal Component
```typescript
const PostAnalyticsProgress = ({ jobId, onComplete, onError }) => {
  const [progress, setProgress] = useState({
    percent: 0,
    stage: 'queued',
    estimatedRemaining: null
  });

  return (
    <Modal isOpen={true} closeOnEscape={false}>
      <div className="p-6">
        <h3>Processing Instagram Post</h3>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2.5 mt-4">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${progress.percent}%` }}
          />
        </div>

        {/* Status Message */}
        <div className="mt-4 text-sm text-gray-600">
          {getStageMessage(progress.stage)}
        </div>

        {/* Estimated Time */}
        {progress.estimatedRemaining && (
          <div className="mt-2 text-xs text-gray-500">
            Estimated time remaining: {formatSeconds(progress.estimatedRemaining)}
          </div>
        )}

        {/* User can continue working */}
        <div className="mt-6 p-3 bg-green-50 rounded">
          <p className="text-sm text-green-800">
            ✅ You can continue using the app while this processes
          </p>
        </div>
      </div>
    </Modal>
  );
};

const getStageMessage = (stage: string): string => {
  const messages = {
    'queued': 'Request queued, starting soon...',
    'apify': 'Fetching Instagram data...',
    'cdn_processing': 'Processing media and thumbnails...',
    'ai_analysis': 'Running AI content analysis...',
    'complete': 'Analytics complete!'
  };
  return messages[stage] || 'Processing...';
};
```

## 🔄 Backward Compatibility

During transition, the frontend can check server capabilities:

```typescript
const checkAsyncSupport = async () => {
  // Try async mode first
  const response = await fetch('/api/v1/campaigns/123/posts?async_mode=true', {
    method: 'POST',
    // ... test request
  });

  const data = await response.json();

  // Check if server returned async response
  if (data.mode === 'async') {
    // Server supports async mode
    setAsyncModeEnabled(true);
  } else {
    // Fallback to sync mode
    console.warn('Server does not support async mode yet');
    setAsyncModeEnabled(false);
  }
};
```

## ⚠️ Important Considerations

1. **Don't block the UI** - Users should be able to navigate while processing
2. **Handle connection loss** - Save job_id locally to resume status checking
3. **Show clear progress** - Users need to know something is happening
4. **Provide cancel option** - Allow users to cancel long-running jobs (future feature)

## 📊 Expected Processing Times

- **New creator (no cache):** 2-5 minutes
- **Existing creator (cached):** 30-60 seconds
- **Multiple posts:** Process individually for better UX

## 🚨 Error Handling

```typescript
const handleJobError = (error: any) => {
  // Specific error messages
  if (error.includes('Instagram post not found')) {
    showError('The Instagram post URL appears to be invalid or deleted');
  } else if (error.includes('Private profile')) {
    showError('This profile is private and cannot be analyzed');
  } else {
    showError('Failed to analyze post. Please try again.');
  }

  // Allow retry
  showRetryButton();
};
```

## 🎯 Migration Checklist

- [ ] Update POST request to include `?async_mode=true`
- [ ] Implement status polling logic
- [ ] Add progress UI component
- [ ] Handle job completion callback
- [ ] Test error scenarios
- [ ] Update loading states to be non-blocking
- [ ] Add job_id persistence for page refreshes
- [ ] Remove old timeout handlers
- [ ] Test with slow network conditions
- [ ] Verify users can navigate during processing

## 📞 Support

If you encounter any issues during migration, the backend team is available to help with the transition.