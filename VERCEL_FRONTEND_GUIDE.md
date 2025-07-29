# 🚀 Vercel Frontend Deployment Guide

## Your Live Backend API
**API Base URL:** `https://analytics-following-backend-5qfwj.ondigitalocean.app`

✅ **API Status:** Live and healthy!  
✅ **Version:** 2.0.0  
✅ **Features:** Decodo integration, retry mechanism, enhanced reliability

---

## 🎯 Frontend Architecture Overview

### **Tech Stack Recommendation**
- **Framework:** Next.js 14+ (for Vercel optimization)
- **Language:** TypeScript (for type safety)
- **Styling:** Tailwind CSS (for rapid development)
- **Charts:** Chart.js or Recharts (for analytics visualization)
- **HTTP Client:** Axios or native fetch

### **Project Structure**
```
analytics-frontend/
├── components/
│   ├── ProfileCard.tsx
│   ├── EngagementChart.tsx
│   ├── LoadingSpinner.tsx
│   └── ErrorBoundary.tsx
├── pages/
│   ├── index.tsx
│   ├── dashboard/[username].tsx
│   └── api/auth.ts
├── services/
│   ├── api.ts
│   └── types.ts
├── utils/
│   └── formatters.ts
└── vercel.json
```

---

## 🔑 Authentication Setup

Your API requires authentication. Here's how to handle it:

### **1. Environment Variables (.env.local)**
```env
NEXT_PUBLIC_API_BASE_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app
NEXT_PUBLIC_API_VERSION=v1
API_JWT_SECRET=your-jwt-secret-from-backend
SMARTPROXY_USERNAME=your-username
SMARTPROXY_PASSWORD=your-password
```

### **2. Authentication Service**
```typescript
// services/auth.ts
export class AuthService {
  private static baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  
  static async login(username: string, password: string) {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    if (!response.ok) throw new Error('Login failed');
    
    const data = await response.json();
    localStorage.setItem('auth_token', data.access_token);
    return data;
  }
  
  static getToken(): string | null {
    return localStorage.getItem('auth_token');
  }
  
  static logout() {
    localStorage.removeItem('auth_token');
  }
}
```

---

## 📡 API Service Layer

### **API Client (services/api.ts)**
```typescript
import axios from 'axios';
import { AuthService } from './auth';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeout: 30000, // 30 seconds for analytics calls
});

// Request interceptor for auth
api.interceptors.request.use((config) => {
  const token = AuthService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      AuthService.logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export class InstagramAPI {
  // Quick summary for dashboard cards (2-8 seconds)
  static async getSummary(username: string) {
    const response = await api.get(`/api/v1/analytics/summary/${username}`);
    return response.data;
  }
  
  // Full analysis for detailed view (8-25 seconds)
  static async getFullAnalysis(username: string) {
    const response = await api.get(`/api/v1/instagram/profile/${username}`);
    return response.data;
  }
  
  // Basic profile info (2-5 seconds)
  static async getBasicProfile(username: string) {
    const response = await api.get(`/api/v1/instagram/profile/${username}/basic`);
    return response.data;
  }
  
  // Health check
  static async getHealth() {
    const response = await api.get('/health');
    return response.data;
  }
}

export default api;
```

---

## 🎨 TypeScript Interfaces

### **Type Definitions (services/types.ts)**
```typescript
export interface InstagramProfile {
  username: string;
  full_name: string;
  biography: string;
  followers: number;
  following: number;
  posts_count: number;
  is_verified: boolean;
  is_private: boolean;
  profile_pic_url: string | null;
  external_url: string | null;
  engagement_rate: number;
  avg_likes: number;
  avg_comments: number;
  avg_engagement: number;
  content_quality_score: number;
  influence_score: number;
  follower_growth_rate: number | null;
}

export interface EngagementMetrics {
  like_rate: number;
  comment_rate: number;
  save_rate: number;
  share_rate: number;
  reach_rate: number;
}

export interface AudienceInsights {
  primary_age_group: string;
  gender_split: {
    female: number;
    male: number;
  };
  top_locations: string[];
  activity_times: string[];
  interests: string[];
}

export interface AnalyticsResponse {
  profile: InstagramProfile;
  engagement_metrics: EngagementMetrics;
  audience_insights: AudienceInsights;
  best_posting_times: string[];
  growth_recommendations: string[];
  analysis_timestamp: string;
  data_quality_score: number;
  scraping_method: string;
}
```

---

## 🧩 Sample React Components

### **1. Profile Dashboard Component**
```typescript
// components/ProfileDashboard.tsx
import { useState, useEffect } from 'react';
import { InstagramAPI } from '../services/api';
import { AnalyticsResponse } from '../services/types';
import LoadingSpinner from './LoadingSpinner';
import ProfileCard from './ProfileCard';
import EngagementChart from './EngagementChart';

interface Props {
  username: string;
}

export default function ProfileDashboard({ username }: Props) {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        
        // First load quick summary
        const summary = await InstagramAPI.getSummary(username);
        setData(summary);
        
        // Then load full analysis
        const fullData = await InstagramAPI.getFullAnalysis(username);
        setData(fullData);
        
      } catch (err: any) {
        setError(err.message || 'Failed to fetch analytics');
      } finally {
        setLoading(false);
      }
    }

    if (username) {
      fetchData();
    }
  }, [username]);

  if (loading) return <LoadingSpinner message="Analyzing Instagram profile..." />;
  if (error) return <div className="text-red-500">Error: {error}</div>;
  if (!data) return <div>No data available</div>;

  return (
    <div className="container mx-auto px-4 py-8">
      <ProfileCard profile={data.profile} />
      <EngagementChart metrics={data.engagement_metrics} />
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <RecommendationsCard recommendations={data.growth_recommendations} />
        <PostingTimesCard times={data.best_posting_times} />
      </div>
    </div>
  );
}
```

### **2. Profile Card Component**
```typescript
// components/ProfileCard.tsx
import { InstagramProfile } from '../services/types';
import { formatNumber } from '../utils/formatters';

interface Props {
  profile: InstagramProfile;
}

export default function ProfileCard({ profile }: Props) {
  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex items-center space-x-4">
        <img
          src={profile.profile_pic_url || '/default-avatar.png'}
          alt={profile.full_name}
          className="w-20 h-20 rounded-full"
          onError={(e) => {
            e.currentTarget.src = '/default-avatar.png';
          }}
        />
        
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold">{profile.full_name}</h1>
            {profile.is_verified && (
              <svg className="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            )}
          </div>
          <p className="text-gray-600">@{profile.username}</p>
          <p className="text-sm text-gray-500 mt-2">{profile.biography}</p>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-4 mt-6 text-center">
        <div>
          <div className="text-2xl font-bold">{formatNumber(profile.followers)}</div>
          <div className="text-gray-500">Followers</div>
        </div>
        <div>
          <div className="text-2xl font-bold">{formatNumber(profile.following)}</div>
          <div className="text-gray-500">Following</div>
        </div>
        <div>
          <div className="text-2xl font-bold">{formatNumber(profile.posts_count)}</div>
          <div className="text-gray-500">Posts</div>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mt-6">
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-blue-600">{profile.engagement_rate}%</div>
          <div className="text-blue-800">Engagement Rate</div>
        </div>
        <div className="bg-purple-50 p-4 rounded-lg">
          <div className="text-2xl font-bold text-purple-600">{profile.influence_score}/10</div>
          <div className="text-purple-800">Influence Score</div>
        </div>
      </div>
    </div>
  );
}
```

### **3. Utility Functions**
```typescript
// utils/formatters.ts
export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toString();
}

export function formatPercentage(num: number): string {
  return `${num.toFixed(2)}%`;
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString();
}
```

---

## 🚀 Vercel Deployment Configuration

### **1. vercel.json**
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "functions": {
    "pages/api/*.ts": {
      "runtime": "nodejs18.x"
    }
  },
  "rewrites": [
    {
      "source": "/api/proxy/(.*)",
      "destination": "https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/$1"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        }
      ]
    }
  ]
}
```

### **2. next.config.js**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  
  // Environment variables for client-side
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_API_VERSION: process.env.NEXT_PUBLIC_API_VERSION,
  },
  
  // Image optimization for profile pictures
  images: {
    domains: ['instagram.com', 'scontent.cdninstagram.com'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.cdninstagram.com',
      },
    ],
  },
  
  // API proxy to avoid CORS issues
  async rewrites() {
    return [
      {
        source: '/api/proxy/:path*',
        destination: 'https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/:path*',
      },
    ];
  },
}

module.exports = nextConfig;
```

### **3. package.json**
```json
{
  "name": "analytics-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0",
    "axios": "^1.6.0",
    "tailwindcss": "^3.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "chart.js": "^4.4.0",
    "react-chartjs-2": "^5.2.0"
  },
  "devDependencies": {
    "eslint": "^8.0.0",
    "eslint-config-next": "^14.0.0"
  }
}
```

---

## 🔧 Vercel Environment Variables

In your Vercel dashboard, add these environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app
NEXT_PUBLIC_API_VERSION=v1
API_JWT_SECRET=your-jwt-secret-from-backend
SMARTPROXY_USERNAME=your-username
SMARTPROXY_PASSWORD=your-password
```

---

## 📋 Deployment Steps

### **1. Create Next.js Project**
```bash
npx create-next-app@latest analytics-frontend --typescript --tailwind --eslint
cd analytics-frontend
```

### **2. Install Dependencies**
```bash
npm install axios chart.js react-chartjs-2
```

### **3. Add Components and Services**
- Copy the components and services from above
- Add the configuration files

### **4. Deploy to Vercel**
```bash
# Connect to Vercel
npx vercel

# Or deploy via GitHub
# Push to GitHub and connect in Vercel dashboard
```

### **5. Configure Environment Variables**
- Go to Vercel dashboard
- Navigate to your project settings
- Add all environment variables listed above

---

## 🧪 Testing Your Frontend

### **1. Health Check**
```javascript
// Test in browser console
fetch('/api/proxy/health')
  .then(r => r.json())
  .then(console.log);
```

### **2. Profile Analysis**
```javascript
// Test analytics endpoint (requires auth)
fetch('/api/proxy/analytics/summary/mkbhd', {
  headers: { 'Authorization': 'Bearer your-token' }
})
  .then(r => r.json())
  .then(console.log);
```

---

## 🎉 Your Frontend is Ready!

**Frontend URL:** `https://your-app.vercel.app`  
**Backend API:** `https://analytics-following-backend-5qfwj.ondigitalocean.app`

Your complete Instagram analytics platform is now live with:
- ✅ **Real-time analytics** from your DigitalOcean backend
- ✅ **Fast deployment** on Vercel's edge network
- ✅ **Professional UI** with Tailwind CSS
- ✅ **Type safety** with TypeScript
- ✅ **Optimized performance** with Next.js
- ✅ **Authentication** integrated

**🚀 Deploy and start analyzing Instagram profiles!**