# 🔍 Background Worker Real-Time Monitoring System

## Overview

Complete real-time monitoring system for all background workers in your analytics platform. Track discovery operations, analytics processing, and system health with live updates and comprehensive metrics.

---

## 🎯 **Available Workers & Their Functions**

### **1. Discovery Worker**
- **Purpose**: Discovers new Instagram profiles and triggers analytics
- **Activities**: Profile discovery, initial data collection, queue management
- **Monitoring**: Queue size, processing rate, discovery success rate

### **2. Similar Profiles Processor**
- **Purpose**: Processes similar profiles found during analytics operations
- **Activities**: Background profile analysis, related profiles discovery
- **Monitoring**: Event processing, success/failure rates, queue status

### **3. Unified Background Processor**
- **Purpose**: Coordinates Apify → CDN → AI workflow
- **Activities**: Image processing, AI analysis orchestration, data pipeline
- **Monitoring**: Processing stages, completion rates, pipeline health

---

## 🚀 **Real-Time Monitoring Endpoints**

### **Base URL**
```
http://localhost:8000/api/v1/workers
```

### **Authentication**
All endpoints require **admin authentication**:
```typescript
headers: {
  'Authorization': `Bearer ${adminToken}`,
  'Content-Type': 'application/json'
}
```

---

## 📊 **Core Monitoring Endpoints**

### **1. Worker Overview - Real-Time Dashboard**
```
GET /api/v1/workers/overview
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-01-15T12:00:00Z",
  "system_overview": {
    "total_workers": 3,
    "active_workers": 2,
    "inactive_workers": 1,
    "overall_health": "healthy",
    "system_load": 45.2,
    "total_tasks_processed": 1247,
    "total_tasks_in_queue": 23,
    "avg_system_response_time": 2.3
  },
  "workers": [
    {
      "worker_name": "Discovery Worker",
      "status": "running",
      "uptime_seconds": 3600,
      "tasks_processed": 450,
      "tasks_successful": 425,
      "tasks_failed": 25,
      "current_queue_size": 12,
      "max_queue_size": 1000,
      "avg_processing_time": 2.1,
      "last_activity": "2025-01-15T11:59:30Z",
      "error_rate": 5.6,
      "memory_usage_mb": 156.7
    }
    // ... other workers
  ],
  "recent_activity": [
    {
      "timestamp": "2025-01-15T11:58:00Z",
      "worker": "Discovery Worker",
      "action": "Processed profile @example_user",
      "status": "success",
      "duration_ms": 2500
    }
  ],
  "performance_metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 156.7,
    "disk_usage": 67.8,
    "discovery_enabled": true,
    "max_concurrent_profiles": 3,
    "daily_rate_limit": 1000
  }
}
```

### **2. Live Worker Stream - Server-Sent Events**
```
GET /api/v1/workers/live-stream
```

**Usage (JavaScript):**
```javascript
const eventSource = new EventSource('/api/v1/workers/live-stream', {
  headers: { 'Authorization': `Bearer ${token}` }
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  updateDashboard(data.data);
};
```

**Stream Data Format:**
```
data: {
  "timestamp": "2025-01-15T12:00:00Z",
  "data": {
    "system_overview": { ... },
    "workers": [ ... ]
  }
}
```

### **3. Queue Status Monitoring**
```
GET /api/v1/workers/queue/status
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-01-15T12:00:00Z",
  "total_queued_tasks": 45,
  "queues": {
    "discovery_worker": {
      "size": 12,
      "max_size": 1000,
      "processing": true,
      "oldest_task_age_seconds": 30,
      "estimated_completion_time": 360
    },
    "similar_profiles_processor": {
      "size": 8,
      "max_size": 1000,
      "processing": false,
      "oldest_task_age_seconds": 120,
      "estimated_completion_time": 240
    },
    "unified_processor": {
      "size": 25,
      "max_size": 500,
      "processing": true,
      "oldest_task_age_seconds": 45,
      "estimated_completion_time": 750
    }
  },
  "system_health": {
    "status": "healthy",
    "queue_utilization": 4.5,
    "estimated_processing_time": 1350
  }
}
```

### **4. Individual Worker Details**
```
GET /api/v1/workers/worker/{worker_name}/details
```

**Available Workers:** `discovery`, `similar_profiles`, `unified`

**Response:**
```json
{
  "success": true,
  "worker_name": "discovery",
  "timestamp": "2025-01-15T12:00:00Z",
  "detailed_stats": "Discovery worker detailed information",
  // Worker-specific detailed metrics
}
```

### **5. Performance Metrics Over Time**
```
GET /api/v1/workers/performance/metrics?hours=24
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2025-01-15T12:00:00Z",
  "period_hours": 24,
  "start_time": "2025-01-14T12:00:00Z",
  "end_time": "2025-01-15T12:00:00Z",
  "worker_metrics": {
    // Historical worker performance data
  },
  "system_metrics": {
    // Historical system performance data
  },
  "performance_summary": {
    // Performance analysis and insights
  }
}
```

### **6. Worker Control Operations**
```
POST /api/v1/workers/worker/{worker_name}/control?action={action}
```

**Available Actions:** `start`, `stop`, `restart`, `pause`, `resume`

**Response:**
```json
{
  "success": true,
  "worker_name": "discovery",
  "action": "restart",
  "timestamp": "2025-01-15T12:00:00Z",
  "result": {
    "action_result": "Discovery worker restart operation"
  },
  "message": "Worker discovery restart operation completed"
}
```

---

## 🖥️ **Real-Time Dashboard Implementation**

### **JavaScript Dashboard Example:**
```javascript
class WorkerMonitoringDashboard {
  constructor() {
    this.apiBase = '/api/v1/workers';
    this.eventSource = null;
    this.updateInterval = null;
  }

  async startLiveMonitoring() {
    // Option 1: Server-Sent Events (Recommended)
    this.eventSource = new EventSource(`${this.apiBase}/live-stream`, {
      headers: { 'Authorization': `Bearer ${this.getToken()}` }
    });

    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.updateDashboard(data.data);
    };

    this.eventSource.onerror = (error) => {
      console.error('Live stream error:', error);
      this.fallbackToPolling();
    };
  }

  fallbackToPolling() {
    // Option 2: Polling Fallback
    this.updateInterval = setInterval(async () => {
      try {
        const response = await fetch(`${this.apiBase}/overview`, {
          headers: { 'Authorization': `Bearer ${this.getToken()}` }
        });
        const data = await response.json();
        this.updateDashboard(data);
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 5000); // Poll every 5 seconds
  }

  updateDashboard(data) {
    const { system_overview, workers } = data;

    // Update system overview
    document.getElementById('total-workers').textContent = system_overview.total_workers;
    document.getElementById('active-workers').textContent = system_overview.active_workers;
    document.getElementById('system-health').textContent = system_overview.overall_health;
    document.getElementById('queue-size').textContent = system_overview.total_tasks_in_queue;

    // Update individual worker cards
    workers.forEach(worker => this.updateWorkerCard(worker));

    // Update timestamp
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
  }

  updateWorkerCard(worker) {
    const card = document.getElementById(`worker-${worker.worker_name.replace(/\s+/g, '-').toLowerCase()}`);
    if (card) {
      card.querySelector('.worker-status').textContent = worker.status;
      card.querySelector('.tasks-processed').textContent = worker.tasks_processed;
      card.querySelector('.queue-size').textContent = worker.current_queue_size;
      card.querySelector('.error-rate').textContent = `${worker.error_rate.toFixed(1)}%`;

      // Update status indicator
      const indicator = card.querySelector('.status-indicator');
      indicator.className = `status-indicator ${this.getStatusClass(worker.status)}`;
    }
  }

  getStatusClass(status) {
    const statusMap = {
      'running': 'status-success',
      'stopped': 'status-error',
      'healthy': 'status-success',
      'degraded': 'status-warning',
      'unavailable': 'status-error'
    };
    return statusMap[status] || 'status-unknown';
  }

  async getQueueStatus() {
    try {
      const response = await fetch(`${this.apiBase}/queue/status`, {
        headers: { 'Authorization': `Bearer ${this.getToken()}` }
      });
      return await response.json();
    } catch (error) {
      console.error('Queue status error:', error);
      return null;
    }
  }

  async controlWorker(workerName, action) {
    try {
      const response = await fetch(`${this.apiBase}/worker/${workerName}/control?action=${action}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${this.getToken()}` }
      });
      const result = await response.json();

      if (result.success) {
        this.showNotification(`Worker ${workerName} ${action} successful`, 'success');
      } else {
        this.showNotification(`Worker ${workerName} ${action} failed`, 'error');
      }

      return result;
    } catch (error) {
      console.error('Worker control error:', error);
      this.showNotification(`Failed to ${action} worker ${workerName}`, 'error');
    }
  }

  showNotification(message, type) {
    // Implement your notification system
    console.log(`[${type.toUpperCase()}] ${message}`);
  }

  getToken() {
    // Get your auth token
    return localStorage.getItem('adminToken');
  }

  cleanup() {
    if (this.eventSource) {
      this.eventSource.close();
    }
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }
  }
}

// Usage
const dashboard = new WorkerMonitoringDashboard();
dashboard.startLiveMonitoring();
```

### **React Component Example:**
```typescript
import React, { useState, useEffect } from 'react';

interface WorkerStats {
  worker_name: string;
  status: string;
  tasks_processed: number;
  current_queue_size: number;
  error_rate: number;
  last_activity: string;
}

interface SystemOverview {
  total_workers: number;
  active_workers: number;
  overall_health: string;
  total_tasks_in_queue: number;
}

const WorkerMonitoringDashboard: React.FC = () => {
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [workers, setWorkers] = useState<WorkerStats[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  useEffect(() => {
    const eventSource = new EventSource('/api/v1/workers/live-stream', {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.data) {
        setSystemOverview(data.data.system_overview);
        setWorkers(data.data.workers);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      // Fallback to polling
      startPolling();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const startPolling = () => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/v1/workers/overview', {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
          setSystemOverview(data.system_overview);
          setWorkers(data.workers);
          setLastUpdated(new Date().toLocaleTimeString());
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 5000);

    return () => clearInterval(interval);
  };

  const getStatusColor = (status: string) => {
    const colors = {
      'running': 'green',
      'healthy': 'green',
      'stopped': 'red',
      'degraded': 'yellow',
      'unavailable': 'gray'
    };
    return colors[status] || 'gray';
  };

  if (!systemOverview) {
    return <div className="loading">Loading worker monitoring...</div>;
  }

  return (
    <div className="worker-monitoring-dashboard">
      <div className="dashboard-header">
        <h1>🔍 Worker Monitoring Dashboard</h1>
        <div className="last-updated">Last updated: {lastUpdated}</div>
      </div>

      {/* System Overview */}
      <div className="system-overview">
        <div className="metric-card">
          <h3>Active Workers</h3>
          <div className="metric-value">{systemOverview.active_workers}/{systemOverview.total_workers}</div>
        </div>

        <div className="metric-card">
          <h3>System Health</h3>
          <div className={`metric-value health-${systemOverview.overall_health}`}>
            {systemOverview.overall_health}
          </div>
        </div>

        <div className="metric-card">
          <h3>Queue Size</h3>
          <div className="metric-value">{systemOverview.total_tasks_in_queue}</div>
        </div>
      </div>

      {/* Individual Workers */}
      <div className="workers-grid">
        {workers.map((worker) => (
          <div key={worker.worker_name} className="worker-card">
            <div className="worker-header">
              <h3>{worker.worker_name}</h3>
              <div
                className="status-indicator"
                style={{ backgroundColor: getStatusColor(worker.status) }}
              />
            </div>

            <div className="worker-metrics">
              <div className="metric">
                <span className="label">Status:</span>
                <span className="value">{worker.status}</span>
              </div>

              <div className="metric">
                <span className="label">Processed:</span>
                <span className="value">{worker.tasks_processed.toLocaleString()}</span>
              </div>

              <div className="metric">
                <span className="label">Queue:</span>
                <span className="value">{worker.current_queue_size}</span>
              </div>

              <div className="metric">
                <span className="label">Error Rate:</span>
                <span className="value">{worker.error_rate.toFixed(1)}%</span>
              </div>

              <div className="metric">
                <span className="label">Last Activity:</span>
                <span className="value">
                  {worker.last_activity
                    ? new Date(worker.last_activity).toLocaleTimeString()
                    : 'N/A'
                  }
                </span>
              </div>
            </div>

            {/* Worker Controls */}
            <div className="worker-controls">
              <button onClick={() => controlWorker(worker.worker_name, 'restart')}>
                🔄 Restart
              </button>
              <button onClick={() => controlWorker(worker.worker_name, 'pause')}>
                ⏸️ Pause
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const controlWorker = async (workerName: string, action: string) => {
  try {
    const response = await fetch(`/api/v1/workers/worker/${workerName}/control?action=${action}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });

    const result = await response.json();

    if (result.success) {
      alert(`Worker ${workerName} ${action} successful`);
    } else {
      alert(`Worker ${workerName} ${action} failed`);
    }
  } catch (error) {
    console.error('Worker control error:', error);
    alert(`Failed to ${action} worker ${workerName}`);
  }
};

const getToken = () => {
  return localStorage.getItem('adminToken') || '';
};

export default WorkerMonitoringDashboard;
```

---

## 🧪 **Testing & Usage**

### **Quick Test Script**
```bash
# Test all endpoints
python scripts/test_worker_monitoring.py test

# Real-time monitoring for 30 seconds
python scripts/test_worker_monitoring.py monitor

# Test live stream
python scripts/test_worker_monitoring.py stream

# Run all tests
python scripts/test_worker_monitoring.py all
```

### **Manual API Testing**
```bash
# Get worker overview
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/workers/overview

# Get queue status
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/workers/queue/status

# Live stream (leave running)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Accept: text/event-stream" \
     http://localhost:8000/api/v1/workers/live-stream

# Control worker
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/v1/workers/worker/discovery/control?action=restart"
```

---

## 🎯 **Key Monitoring Metrics**

### **System Health Indicators**
- **Overall Health**: `healthy` | `degraded` | `critical`
- **Active Workers**: Number of running workers vs total
- **Queue Utilization**: Total tasks in all queues
- **System Load**: CPU and memory usage

### **Worker Performance Metrics**
- **Tasks Processed**: Total completed tasks
- **Success Rate**: (Successful tasks / Total tasks) * 100
- **Error Rate**: (Failed tasks / Total tasks) * 100
- **Average Processing Time**: Time per task
- **Queue Size**: Current pending tasks

### **Real-Time Activity Tracking**
- **Last Activity**: Timestamp of most recent worker action
- **Processing Status**: Currently processing vs idle
- **Queue Age**: How long oldest task has been waiting
- **Estimated Completion**: Time to clear current queue

---

## 🚨 **Alerts & Notifications**

### **Health Status Alerts**
- **Critical**: All workers down or system unresponsive
- **Degraded**: Some workers down or high error rates (>10%)
- **Healthy**: All systems operational

### **Performance Alerts**
- **High Queue**: >100 tasks in any single queue
- **Slow Processing**: Average processing time >60 seconds
- **High Error Rate**: >15% failure rate for any worker
- **Memory Issues**: >80% memory utilization

### **Monitoring Best Practices**
1. **Set up alerts** for critical health status changes
2. **Monitor queue sizes** to prevent backlogs
3. **Track error rates** to identify system issues
4. **Use live stream** for real-time debugging
5. **Regular performance reviews** using historical metrics

---

## 🎉 **System Ready!**

Your **Background Worker Real-Time Monitoring System** is now fully operational! You can:

✅ **Track all workers in real-time** with live updates every 5 seconds
✅ **Monitor queue status** and processing performance
✅ **Control worker lifecycle** (start/stop/restart operations)
✅ **Stream live data** to frontend dashboards
✅ **Analyze performance trends** with historical metrics
✅ **Set up alerts** for system health monitoring

The system provides enterprise-grade monitoring capabilities for your entire background processing infrastructure.