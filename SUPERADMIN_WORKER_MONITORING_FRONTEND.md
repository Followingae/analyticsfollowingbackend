# 🔍 Superadmin Worker Monitoring - Frontend Integration Instructions

## Overview

Add real-time background worker monitoring to the superadmin dashboard. This provides live visibility into all background workers, queue status, and system performance with automatic updates.

---

## 🎯 **What to Build**

### **New Superadmin Section: "Worker Monitoring"**
- **Location**: Add as a new tab/section in the existing superadmin dashboard
- **Access**: Superadmin only (same authentication as other superadmin features)
- **Features**: Real-time worker status, queue monitoring, system controls

### **Key Components to Implement**
1. **Worker Overview Dashboard** - Main monitoring interface
2. **Live Stream Integration** - Real-time updates via Server-Sent Events
3. **Worker Control Panel** - Start/stop/restart workers
4. **Queue Status Monitoring** - Real-time queue visualization
5. **Performance Metrics** - System health and worker performance

---

## 🚀 **API Endpoints Available**

### **Base URL**
```
/api/v1/workers
```

### **Authentication**
All endpoints use existing superadmin authentication:
```typescript
headers: {
  'Authorization': `Bearer ${superadminToken}`,
  'Content-Type': 'application/json'
}
```

### **Core Endpoints**
```typescript
// Worker overview (main dashboard data)
GET /api/v1/workers/overview

// Live stream (Server-Sent Events for real-time updates)
GET /api/v1/workers/live-stream

// Queue status
GET /api/v1/workers/queue/status

// Individual worker details
GET /api/v1/workers/worker/{worker_name}/details
// worker_name: 'discovery', 'similar_profiles', 'unified'

// Worker control operations
POST /api/v1/workers/worker/{worker_name}/control?action={action}
// actions: 'start', 'stop', 'restart', 'pause', 'resume'

// Performance metrics over time
GET /api/v1/workers/performance/metrics?hours=24
```

---

## 🎨 **Frontend Implementation Guide**

### **1. Add Worker Monitoring to Navigation**

```typescript
// Add to superadmin navigation menu
const superadminNavItems = [
  { path: '/superadmin/dashboard', label: 'Dashboard', icon: '📊' },
  { path: '/superadmin/analytics', label: 'Analytics Completeness', icon: '🎯' },
  { path: '/superadmin/workers', label: 'Worker Monitoring', icon: '🔍' }, // NEW
  { path: '/superadmin/users', label: 'User Management', icon: '👥' },
  // ... other existing items
];
```

### **2. Create Worker Monitoring Page Component**

```typescript
// app/superadmin/workers/page.tsx
'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface WorkerStats {
  worker_name: string;
  status: string;
  uptime_seconds: number;
  tasks_processed: number;
  tasks_successful: number;
  tasks_failed: number;
  current_queue_size: number;
  max_queue_size: number;
  avg_processing_time: number;
  last_activity: string | null;
  error_rate: number;
  memory_usage_mb: number;
}

interface SystemOverview {
  total_workers: number;
  active_workers: number;
  inactive_workers: number;
  overall_health: string;
  system_load: number;
  total_tasks_processed: number;
  total_tasks_in_queue: number;
  avg_system_response_time: number;
}

interface WorkerMonitoringData {
  success: boolean;
  timestamp: string;
  system_overview: SystemOverview;
  workers: WorkerStats[];
  recent_activity: Array<{
    timestamp: string;
    worker: string;
    action: string;
    status: string;
    duration_ms: number;
  }>;
  performance_metrics: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    discovery_enabled: boolean;
    max_concurrent_profiles: number;
    daily_rate_limit: number;
  };
}

export default function WorkerMonitoringPage() {
  const [data, setData] = useState<WorkerMonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  // Load initial data
  useEffect(() => {
    loadWorkerData();
  }, []);

  const loadWorkerData = async () => {
    try {
      const response = await fetch('/api/v1/workers/overview', {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load worker data: ${response.status}`);
      }

      const workerData = await response.json();
      setData(workerData);
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load worker data');
    } finally {
      setLoading(false);
    }
  };

  const startLiveUpdates = () => {
    if (eventSource) {
      eventSource.close();
    }

    const es = new EventSource('/api/v1/workers/live-stream', {
      // Note: EventSource doesn't support custom headers, so you may need to use polling instead
      // or implement authentication via query params/cookies
    });

    es.onmessage = (event) => {
      try {
        const eventData = JSON.parse(event.data);
        if (eventData.data) {
          setData(eventData.data);
          setLastUpdated(new Date().toLocaleTimeString());
          setError(null);
        }
      } catch (err) {
        console.error('Failed to parse live data:', err);
      }
    };

    es.onerror = (error) => {
      console.error('Live stream error:', error);
      setIsLiveMode(false);
      setEventSource(null);
    };

    setEventSource(es);
    setIsLiveMode(true);
  };

  const stopLiveUpdates = () => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setIsLiveMode(false);
  };

  const controlWorker = async (workerName: string, action: string) => {
    try {
      const response = await fetch(`/api/v1/workers/worker/${workerName}/control?action=${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        }
      });

      const result = await response.json();

      if (result.success) {
        // Show success notification
        alert(`Worker ${workerName} ${action} successful`);
        // Refresh data
        await loadWorkerData();
      } else {
        alert(`Worker ${workerName} ${action} failed`);
      }
    } catch (err) {
      console.error('Worker control error:', err);
      alert(`Failed to ${action} worker ${workerName}`);
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running':
      case 'healthy':
        return 'default'; // Green
      case 'stopped':
      case 'unavailable':
        return 'destructive'; // Red
      case 'degraded':
        return 'secondary'; // Yellow
      default:
        return 'outline'; // Gray
    }
  };

  const getHealthColor = (health: string) => {
    switch (health.toLowerCase()) {
      case 'healthy':
        return 'text-green-600';
      case 'degraded':
        return 'text-yellow-600';
      case 'critical':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading worker monitoring...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert className="mx-4">
        <AlertDescription>
          Error loading worker data: {error}
          <Button onClick={loadWorkerData} className="ml-4" size="sm">
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return (
      <Alert className="mx-4">
        <AlertDescription>No worker data available</AlertDescription>
      </Alert>
    );
  }

  const { system_overview, workers, recent_activity, performance_metrics } = data;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">🔍 Worker Monitoring</h1>
          <p className="text-gray-600">Real-time background worker status and control</p>
        </div>

        <div className="flex items-center space-x-4">
          <div className="text-sm text-gray-500">
            Last updated: {lastUpdated}
          </div>

          {!isLiveMode ? (
            <Button onClick={startLiveUpdates} size="sm">
              📡 Start Live Updates
            </Button>
          ) : (
            <Button onClick={stopLiveUpdates} variant="outline" size="sm">
              ⏹️ Stop Live Updates
            </Button>
          )}

          <Button onClick={loadWorkerData} variant="outline" size="sm">
            🔄 Refresh
          </Button>
        </div>
      </div>

      {/* System Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Active Workers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {system_overview.active_workers}/{system_overview.total_workers}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">System Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getHealthColor(system_overview.overall_health)}`}>
              {system_overview.overall_health}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Queue Size</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {system_overview.total_tasks_in_queue}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">System Load</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {system_overview.system_load.toFixed(1)}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Individual Workers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {workers.map((worker) => (
          <Card key={worker.worker_name}>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-lg">{worker.worker_name}</CardTitle>
                <Badge variant={getStatusBadgeVariant(worker.status)}>
                  {worker.status}
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Worker Metrics */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Tasks Processed:</span>
                  <span className="font-medium">{worker.tasks_processed.toLocaleString()}</span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Success Rate:</span>
                  <span className="font-medium">
                    {worker.tasks_processed > 0
                      ? ((worker.tasks_successful / worker.tasks_processed) * 100).toFixed(1)
                      : 0
                    }%
                  </span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Queue Size:</span>
                  <span className="font-medium">
                    {worker.current_queue_size}/{worker.max_queue_size}
                  </span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Error Rate:</span>
                  <span className={`font-medium ${worker.error_rate > 10 ? 'text-red-600' : 'text-green-600'}`}>
                    {worker.error_rate.toFixed(1)}%
                  </span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Avg Processing:</span>
                  <span className="font-medium">{worker.avg_processing_time.toFixed(1)}s</span>
                </div>

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Last Activity:</span>
                  <span className="font-medium">
                    {worker.last_activity
                      ? new Date(worker.last_activity).toLocaleTimeString()
                      : 'N/A'
                    }
                  </span>
                </div>
              </div>

              {/* Worker Controls */}
              <div className="flex space-x-2 pt-4 border-t">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => controlWorker(worker.worker_name.toLowerCase().replace(/\s+/g, '_'), 'restart')}
                  className="flex-1"
                >
                  🔄 Restart
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => controlWorker(worker.worker_name.toLowerCase().replace(/\s+/g, '_'), 'pause')}
                  className="flex-1"
                >
                  ⏸️ Pause
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Activity & Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recent_activity.length > 0 ? (
                recent_activity.slice(0, 10).map((activity, index) => (
                  <div key={index} className="flex justify-between items-center text-sm">
                    <div>
                      <span className="font-medium">{activity.worker}</span>
                      <span className="text-gray-600 ml-2">{activity.action}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant={activity.status === 'success' ? 'default' : 'destructive'} className="text-xs">
                        {activity.status}
                      </Badge>
                      <span className="text-gray-500">
                        {new Date(activity.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-gray-500 text-center py-4">
                  No recent activity
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Performance Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">CPU Usage:</span>
                <span className="font-medium">{performance_metrics.cpu_usage.toFixed(1)}%</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-600">Memory Usage:</span>
                <span className="font-medium">{(performance_metrics.memory_usage / 1024).toFixed(1)} GB</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-600">Disk Usage:</span>
                <span className="font-medium">{performance_metrics.disk_usage.toFixed(1)}%</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-600">Discovery Enabled:</span>
                <Badge variant={performance_metrics.discovery_enabled ? 'default' : 'secondary'}>
                  {performance_metrics.discovery_enabled ? 'Yes' : 'No'}
                </Badge>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-600">Max Concurrent:</span>
                <span className="font-medium">{performance_metrics.max_concurrent_profiles}</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-600">Daily Limit:</span>
                <span className="font-medium">{performance_metrics.daily_rate_limit.toLocaleString()}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Helper function to get auth token (implement based on your auth system)
function getAuthToken(): string {
  // Replace with your actual token retrieval method
  return localStorage.getItem('authToken') || '';
}
```

### **3. Add Route Configuration**

```typescript
// app/superadmin/layout.tsx or routing configuration
const superadminRoutes = [
  {
    path: '/superadmin/workers',
    component: WorkerMonitoringPage,
    title: 'Worker Monitoring',
    requiresAuth: true,
    requiredRole: 'superadmin'
  }
];
```

### **4. Update Superadmin Navigation**

```typescript
// components/SuperadminNavigation.tsx
const navigationItems = [
  {
    href: '/superadmin/dashboard',
    label: 'Dashboard',
    icon: <DashboardIcon />,
  },
  {
    href: '/superadmin/analytics',
    label: 'Analytics Completeness',
    icon: <AnalyticsIcon />,
  },
  {
    href: '/superadmin/workers', // NEW
    label: 'Worker Monitoring',
    icon: <WorkerIcon />, // Use appropriate icon
  },
  // ... other existing items
];
```

---

## 🔧 **Implementation Notes**

### **Authentication Considerations**
```typescript
// Server-Sent Events (EventSource) doesn't support custom headers
// You have two options:

// Option 1: Use polling instead of SSE (recommended)
const usePolling = () => {
  useEffect(() => {
    const interval = setInterval(async () => {
      await loadWorkerData();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, []);
};

// Option 2: Implement SSE with cookie-based auth
// Configure your backend to accept auth via cookies for the SSE endpoint
```

### **Worker Name Mapping**
```typescript
// Map display names to API worker names
const workerNameMap = {
  'Discovery Worker': 'discovery',
  'Similar Profiles Processor': 'similar_profiles',
  'Unified Background Processor': 'unified'
};

const getApiWorkerName = (displayName: string) => {
  return workerNameMap[displayName] || displayName.toLowerCase().replace(/\s+/g, '_');
};
```

### **Error Handling**
```typescript
const handleApiError = (error: any) => {
  if (error.status === 401) {
    // Redirect to login
    window.location.href = '/auth/login';
  } else if (error.status === 403) {
    // Show unauthorized message
    alert('Superadmin access required');
  } else {
    // Show generic error
    console.error('API Error:', error);
    alert('An error occurred while loading worker data');
  }
};
```

---

## 🎨 **Styling & UI Framework Integration**

### **If using Tailwind CSS:**
- The component above uses Tailwind classes
- Add custom status colors if needed
- Responsive design included

### **If using different UI framework:**
```typescript
// Replace shadcn/ui components with your framework:
// Card → Your card component
// Badge → Your badge component
// Button → Your button component
// Alert → Your alert component
```

### **Custom Styles for Status Indicators:**
```css
/* Add to your global CSS */
.status-success {
  @apply bg-green-100 text-green-800 border-green-200;
}

.status-warning {
  @apply bg-yellow-100 text-yellow-800 border-yellow-200;
}

.status-error {
  @apply bg-red-100 text-red-800 border-red-200;
}

.status-unknown {
  @apply bg-gray-100 text-gray-800 border-gray-200;
}
```

---

## 📱 **Mobile Responsiveness**

```typescript
// Mobile-friendly adjustments
const MobileWorkerCard = ({ worker }: { worker: WorkerStats }) => (
  <Card className="mb-4">
    <CardHeader>
      <div className="flex justify-between items-center">
        <CardTitle className="text-base">{worker.worker_name}</CardTitle>
        <Badge variant={getStatusBadgeVariant(worker.status)}>
          {worker.status}
        </Badge>
      </div>
    </CardHeader>

    <CardContent>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>Processed: {worker.tasks_processed}</div>
        <div>Queue: {worker.current_queue_size}</div>
        <div>Success: {((worker.tasks_successful / worker.tasks_processed) * 100).toFixed(1)}%</div>
        <div>Errors: {worker.error_rate.toFixed(1)}%</div>
      </div>

      <div className="mt-3 flex space-x-2">
        <Button size="sm" className="flex-1">🔄</Button>
        <Button size="sm" className="flex-1">⏸️</Button>
      </div>
    </CardContent>
  </Card>
);
```

---

## 🚀 **Testing Instructions**

### **1. Test API Connection**
```bash
# Test the worker overview endpoint
curl -H "Authorization: Bearer YOUR_SUPERADMIN_TOKEN" \
     http://localhost:8000/api/v1/workers/overview
```

### **2. Frontend Testing Steps**
1. **Add the route** to your superadmin section
2. **Test with mock data** first (comment out API calls)
3. **Test API integration** with real backend
4. **Test real-time updates** (polling or SSE)
5. **Test worker controls** (start/stop/restart)

### **3. Mock Data for Testing**
```typescript
const mockWorkerData = {
  success: true,
  timestamp: new Date().toISOString(),
  system_overview: {
    total_workers: 3,
    active_workers: 2,
    inactive_workers: 1,
    overall_health: "healthy",
    system_load: 45.2,
    total_tasks_processed: 1247,
    total_tasks_in_queue: 23,
    avg_system_response_time: 2.3
  },
  workers: [
    {
      worker_name: "Discovery Worker",
      status: "running",
      uptime_seconds: 3600,
      tasks_processed: 450,
      tasks_successful: 425,
      tasks_failed: 25,
      current_queue_size: 12,
      max_queue_size: 1000,
      avg_processing_time: 2.1,
      last_activity: new Date().toISOString(),
      error_rate: 5.6,
      memory_usage_mb: 156.7
    }
    // ... add other workers
  ],
  recent_activity: [],
  performance_metrics: {
    cpu_usage: 45.2,
    memory_usage: 156.7,
    disk_usage: 67.8,
    discovery_enabled: true,
    max_concurrent_profiles: 3,
    daily_rate_limit: 1000
  }
};
```

---

## 🎯 **Expected Outcome**

After implementation, superadmins will have:

✅ **Real-time worker monitoring** integrated into existing superadmin dashboard
✅ **Live system health visibility** with automatic updates
✅ **Worker control capabilities** (restart/pause/resume)
✅ **Queue monitoring** to prevent backlogs
✅ **Performance metrics** for system optimization
✅ **Recent activity tracking** for debugging

The integration provides enterprise-grade monitoring capabilities within the existing superadmin interface, giving complete visibility and control over the background processing infrastructure.

---

## 📞 **Support & Questions**

If you need help with:
- **Authentication integration** - How to pass superadmin tokens
- **UI framework adaptation** - Adapting to your specific component library
- **Real-time updates** - Implementing polling vs Server-Sent Events
- **Styling customization** - Matching your existing design system

The backend is ready and all endpoints are functional - the frontend team just needs to build the interface using the component example above!