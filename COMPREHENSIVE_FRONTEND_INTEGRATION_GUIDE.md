# 🚀 Complete Frontend Integration Guide - January 2025
**Analytics Following Backend - SHADCN ONLY Implementation**

---

## 🎯 Critical Issues Fixed

### ❌ Frontend Issues Identified:
1. **Not respecting 2-step serving architecture** - Showing "AI Analysis in progress" for database-served profiles
2. **Images not displaying** - Profile pictures and post thumbnails completely broken
3. **Using outdated API methods** - Not following current API response structure

### ✅ This Guide Fixes:
- ✅ **Proper 2-step serving handling** - Immediate display of database data
- ✅ **Complete CDN image integration** - Working profile pictures and post thumbnails
- ✅ **Updated API structure** - Uses only current endpoints
- ✅ **SHADCN-only components** - No other UI libraries

---

## 🏗️ API Response Structure (MUST FOLLOW)

### 1. Profile Search/Analysis Response
```typescript
// POST /api/v1/simple/creator/search/{username}
interface ProfileSearchResponse {
  success: boolean
  profile: {
    username: string
    full_name: string | null
    biography: string | null
    followers_count: number
    following_count: number
    posts_count: number
    is_verified: boolean
    profile_pic_url: string | null
    ai_analysis?: {
      primary_content_type: string | null
      avg_sentiment_score: number | null
    }
  }
  message: string
  cached: boolean  // ⚠️ CRITICAL: Shows if from database (true) or new (false)
}
```

### 2. Profile Get Response  
```typescript
// GET /api/v1/simple/creator/{username}
interface ProfileGetResponse {
  success: boolean
  profile: {
    username: string
    full_name: string | null
    biography: string | null
    followers_count: number
    following_count: number
    posts_count: number
    is_verified: boolean
    profile_pic_url: string | null
  }
  message: string
}
```

### 3. CDN Media Response
```typescript
// GET /api/v1/creators/ig/{profile_identifier}/media
// Can use either username OR UUID as profile_identifier
interface CDNMediaResponse {
  profile_id: string // UUID
  profile_identifier: string // Username or UUID that was used in request
  avatar: {
    "256": string  // CDN URL or placeholder
    "512": string  // CDN URL or placeholder
    available: boolean
    placeholder: boolean
  }
  posts: Array<{
    mediaId: string
    thumb: {
      "256": string  // CDN URL or placeholder
      "512": string  // CDN URL or placeholder
    }
    available: boolean
    placeholder: boolean
    processing_status: string
  }>
  processing_status: {
    queued: boolean
    total_assets: number
    completed_assets: number
    completion_percentage: number
  }
  cdn_info: {
    base_url: string
    cache_ttl: string
    formats_available: string[]
    sizes_available: number[]
  }
}
```

### 4. Profile Status Response (Optional - for compatibility)
```typescript
// GET /api/v1/simple/creator/{username}/status
interface ProfileStatusResponse {
  success: boolean
  status: "complete" | "not_found" | "unknown"
  username: string
  profile_ready: boolean
  analysis_complete: boolean
  message: string
  data_source: "database" | "none"
  error?: string
}
```

### 5. System Stats Response
```typescript
// GET /api/v1/simple/creator/system/stats  
interface SystemStatsResponse {
  success: boolean
  stats: {
    profiles: {
      total: number
      with_ai_analysis: number
      ai_completion_rate: string
    }
    posts: {
      total: number
      with_ai_analysis: number
      ai_completion_rate: string
    }
    system: {
      status: string
      ai_system: string
    }
  }
  message: string
}
```

---

## 🔥 React Query Hooks (TanStack Query v5)

### 1. Creator Search Hook
```typescript
// hooks/useCreatorSearch.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

interface UseCreatorSearchOptions {
  onSuccess?: (data: ProfileSearchResponse) => void
  onError?: (error: Error) => void
}

export const useCreatorSearch = (options?: UseCreatorSearchOptions) => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (username: string): Promise<ProfileSearchResponse> => {
      const response = await api.post(`/simple/creator/search/${username}`)
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`)
      }
      
      return response.json()
    },
    onSuccess: (data, username) => {
      // Cache the profile data for GET requests
      queryClient.setQueryData(
        ['profile', username], 
        data.profile
      )
      
      // Cache CDN media separately if profile has ID
      if (data.profile && data.success) {
        queryClient.invalidateQueries({ 
          queryKey: ['cdn-media', data.profile.username] 
        })
      }
      
      options?.onSuccess?.(data)
    },
    onError: options?.onError
  })
}
```

### 2. Profile Data Hook  
```typescript
// hooks/useProfile.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const useProfile = (username: string) => {
  return useQuery({
    queryKey: ['profile', username],
    queryFn: async (): Promise<ProfileGetResponse> => {
      const response = await api.get(`/simple/creator/${username}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch profile: ${response.statusText}`)
      }
      
      return response.json()
    },
    enabled: Boolean(username),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (replaces cacheTime)
  })
}
```

### 3. CDN Media Hook
```typescript
// hooks/useCDNMedia.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const useCDNMedia = (profileIdentifier: string | undefined) => {
  return useQuery({
    queryKey: ['cdn-media', profileIdentifier],
    queryFn: async (): Promise<CDNMediaResponse> => {
      if (!profileIdentifier) throw new Error('Profile identifier required')
      
      // Can use either username or UUID
      const response = await api.get(`/creators/ig/${profileIdentifier}/media`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch CDN media: ${response.statusText}`)
      }
      
      return response.json()
    },
    enabled: Boolean(profileIdentifier),
    staleTime: 2 * 60 * 1000, // 2 minutes for images
    gcTime: 5 * 60 * 1000, // 5 minutes
    retry: 2
  })
}
```

### 4. Profile Status Hook (Legacy Compatibility)
```typescript
// hooks/useProfileStatus.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const useProfileStatus = (username: string | undefined) => {
  return useQuery({
    queryKey: ['profile-status', username],
    queryFn: async (): Promise<ProfileStatusResponse> => {
      if (!username) throw new Error('Username required')
      
      const response = await api.get(`/simple/creator/${username}/status`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch status: ${response.statusText}`)
      }
      
      return response.json()
    },
    enabled: Boolean(username),
    staleTime: 10 * 1000, // 10 seconds
    gcTime: 30 * 1000, // 30 seconds
    refetchInterval: (data) => {
      // Stop polling if profile is complete or not found
      if (data?.status === 'complete' || data?.status === 'not_found') {
        return false
      }
      return 5000 // Poll every 5 seconds for unknown status
    }
  })
}
```

### 5. System Stats Hook
```typescript
// hooks/useSystemStats.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const useSystemStats = () => {
  return useQuery({
    queryKey: ['system-stats'],
    queryFn: async (): Promise<SystemStatsResponse> => {
      const response = await api.get('/simple/creator/system/stats')
      
      if (!response.ok) {
        throw new Error(`Failed to fetch system stats: ${response.statusText}`)
      }
      
      return response.json()
    },
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000 // Auto-refresh every minute
  })
}
```

---

## 🎨 SHADCN Components (Complete Implementation)

### 1. Creator Search Component
```typescript
// components/creator-search.tsx
"use client"

import React, { useState } from 'react'
import { Search, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { useCreatorSearch } from '@/hooks/useCreatorSearch'
import { ProfileCard } from './profile-card'

export const CreatorSearch: React.FC = () => {
  const [username, setUsername] = useState('')
  const [searchResult, setSearchResult] = useState<ProfileSearchResponse | null>(null)

  const creatorSearch = useCreatorSearch({
    onSuccess: (data) => {
      setSearchResult(data)
    },
    onError: (error) => {
      console.error('Search failed:', error)
    }
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (username.trim()) {
      creatorSearch.mutate(username.trim())
    }
  }

  const getDataSourceBadge = () => {
    if (!searchResult) return null
    
    return (
      <Badge variant={searchResult.cached ? "secondary" : "default"}>
        {searchResult.cached ? "Database" : "Fresh Data"}
      </Badge>
    )
  }

  const getStatusIcon = () => {
    if (creatorSearch.isPending) {
      return <Loader2 className="h-4 w-4 animate-spin" />
    }
    if (creatorSearch.isError) {
      return <AlertCircle className="h-4 w-4 text-destructive" />
    }
    if (creatorSearch.isSuccess) {
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    }
    return <Search className="h-4 w-4" />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Creator Search
          {getDataSourceBadge()}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            type="text"
            placeholder="Enter Instagram username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={creatorSearch.isPending}
            className="flex-1"
          />
          <Button 
            type="submit" 
            disabled={!username.trim() || creatorSearch.isPending}
          >
            {getStatusIcon()}
            {creatorSearch.isPending ? 'Searching...' : 'Search'}
          </Button>
        </form>

        {creatorSearch.isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {creatorSearch.error?.message || 'Search failed'}
            </AlertDescription>
          </Alert>
        )}

        {searchResult && (
          <div className="space-y-4">
            <Alert>
              <AlertDescription className="flex items-center justify-between">
                <span>{searchResult.message}</span>
                <Badge variant="outline">
                  {searchResult.cached ? "Served from Database" : "New Profile Fetched"}
                </Badge>
              </AlertDescription>
            </Alert>
            
            <ProfileCard profile={searchResult.profile} showAI={true} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

### 2. Profile Card Component (with CDN Images)
```typescript
// components/profile-card.tsx
"use client"

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { CheckCircle2, Users, MessageCircle, ImageIcon } from 'lucide-react'
import { useCDNMedia } from '@/hooks/useCDNMedia'
import { ProfileImageWithFallback } from './profile-image-with-fallback'

interface ProfileCardProps {
  profile: {
    username: string
    full_name: string | null
    biography: string | null
    followers_count: number
    following_count: number
    posts_count: number
    is_verified: boolean
    profile_pic_url: string | null
    ai_analysis?: {
      primary_content_type: string | null
      avg_sentiment_score: number | null
    }
  }
  showAI?: boolean
}

export const ProfileCard: React.FC<ProfileCardProps> = ({ profile, showAI = false }) => {
  // Use username directly - CDN endpoint now supports username lookup
  const cdnMedia = useCDNMedia(profile.username)

  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toString()
  }

  const getSentimentBadge = (score: number | null) => {
    if (score === null) return null
    
    if (score > 0.3) return <Badge className="bg-green-100 text-green-800">Positive</Badge>
    if (score < -0.3) return <Badge className="bg-red-100 text-red-800">Negative</Badge>
    return <Badge className="bg-gray-100 text-gray-800">Neutral</Badge>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          <ProfileImageWithFallback
            src={cdnMedia.data?.avatar?.["256"]}
            fallback={profile.profile_pic_url}
            alt={profile.username}
            className="h-12 w-12"
            isPlaceholder={cdnMedia.data?.avatar?.placeholder}
          />
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span>@{profile.username}</span>
              {profile.is_verified && (
                <CheckCircle2 className="h-4 w-4 text-blue-500" />
              )}
            </div>
            {profile.full_name && (
              <span className="text-sm text-muted-foreground">
                {profile.full_name}
              </span>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {profile.biography && (
          <p className="text-sm text-muted-foreground line-clamp-3">
            {profile.biography}
          </p>
        )}
        
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="flex flex-col items-center">
            <Users className="h-4 w-4 text-muted-foreground mb-1" />
            <span className="font-semibold">{formatNumber(profile.followers_count)}</span>
            <span className="text-xs text-muted-foreground">Followers</span>
          </div>
          <div className="flex flex-col items-center">
            <Users className="h-4 w-4 text-muted-foreground mb-1" />
            <span className="font-semibold">{formatNumber(profile.following_count)}</span>
            <span className="text-xs text-muted-foreground">Following</span>
          </div>
          <div className="flex flex-col items-center">
            <ImageIcon className="h-4 w-4 text-muted-foreground mb-1" />
            <span className="font-semibold">{formatNumber(profile.posts_count)}</span>
            <span className="text-xs text-muted-foreground">Posts</span>
          </div>
        </div>

        {showAI && profile.ai_analysis && (
          <>
            <Separator />
            <div className="space-y-2">
              <h4 className="font-medium text-sm">AI Analysis</h4>
              <div className="flex flex-wrap gap-2">
                {profile.ai_analysis.primary_content_type && (
                  <Badge variant="outline">
                    {profile.ai_analysis.primary_content_type}
                  </Badge>
                )}
                {getSentimentBadge(profile.ai_analysis.avg_sentiment_score)}
              </div>
            </div>
          </>
        )}

        {/* CDN Image Processing Status */}
        {cdnMedia.data?.processing_status && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Image Processing</span>
              <Badge variant={cdnMedia.data.processing_status.queued ? "secondary" : "default"}>
                {cdnMedia.data.processing_status.completion_percentage}% Complete
              </Badge>
            </div>
            {cdnMedia.data.processing_status.queued && (
              <div className="w-full bg-secondary rounded-full h-2">
                <div 
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${cdnMedia.data.processing_status.completion_percentage}%` }}
                />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

### 3. Profile Image with Fallback Component
```typescript
// components/profile-image-with-fallback.tsx
"use client"

import React, { useState, useEffect } from 'react'
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { User, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ProfileImageWithFallbackProps {
  src?: string | null
  fallback?: string | null
  alt: string
  className?: string
  isPlaceholder?: boolean
}

export const ProfileImageWithFallback: React.FC<ProfileImageWithFallbackProps> = ({
  src,
  fallback,
  alt,
  className,
  isPlaceholder = false
}) => {
  const [currentSrc, setCurrentSrc] = useState<string | null>(src || null)
  const [isLoading, setIsLoading] = useState(Boolean(src))
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    // Reset state when src changes
    setCurrentSrc(src || null)
    setIsLoading(Boolean(src))
    setHasError(false)
  }, [src])

  const handleError = () => {
    setIsLoading(false)
    setHasError(true)
    
    // Try fallback if available and different from current src
    if (fallback && fallback !== currentSrc) {
      setCurrentSrc(fallback)
      setIsLoading(true)
      setHasError(false)
    }
  }

  const handleLoad = () => {
    setIsLoading(false)
    setHasError(false)
  }

  return (
    <Avatar className={cn("relative", className)}>
      {currentSrc && !hasError && (
        <AvatarImage
          src={currentSrc}
          alt={alt}
          onError={handleError}
          onLoad={handleLoad}
          className={cn(
            "transition-opacity duration-200",
            isLoading ? "opacity-50" : "opacity-100"
          )}
        />
      )}
      
      <AvatarFallback className={cn(
        "bg-muted flex items-center justify-center",
        isPlaceholder && "bg-orange-50 text-orange-600"
      )}>
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <User className="h-4 w-4" />
        )}
      </AvatarFallback>
      
      {isPlaceholder && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-orange-400 rounded-full border-2 border-background" />
      )}
    </Avatar>
  )
}
```

### 4. System Dashboard Component
```typescript
// components/system-dashboard.tsx
"use client"

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Database, Brain, Activity, RefreshCw } from 'lucide-react'
import { useSystemStats } from '@/hooks/useSystemStats'
import { Button } from "@/components/ui/button"

export const SystemDashboard: React.FC = () => {
  const { data: stats, isLoading, error, refetch, isRefetching } = useSystemStats()

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="animate-pulse space-y-2">
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-4 bg-muted rounded w-1/2" />
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error || !stats?.success) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            System Statistics
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isRefetching}
            >
              <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">Failed to load system stats</p>
        </CardContent>
      </Card>
    )
  }

  const getSystemStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return <Badge className="bg-green-100 text-green-800">Healthy</Badge>
      case 'degraded':
        return <Badge className="bg-yellow-100 text-yellow-800">Degraded</Badge>
      case 'error':
        return <Badge className="bg-red-100 text-red-800">Error</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const parseCompletionRate = (rate: string): number => {
    return parseFloat(rate.replace('%', '')) || 0
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Statistics
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* System Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">System Status</span>
          </div>
          {getSystemStatusBadge(stats.stats.system.status)}
        </div>

        {/* AI System Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">AI System</span>
          </div>
          <Badge variant={stats.stats.system.ai_system === 'available' ? 'default' : 'secondary'}>
            {stats.stats.system.ai_system}
          </Badge>
        </div>

        {/* Profiles Statistics */}
        <div className="space-y-3">
          <h4 className="font-medium text-sm">Profiles</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.stats.profiles.total.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">Total Profiles</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.stats.profiles.with_ai_analysis.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">With AI Analysis</div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">AI Completion Rate</span>
              <span className="text-sm font-medium">{stats.stats.profiles.ai_completion_rate}</span>
            </div>
            <Progress value={parseCompletionRate(stats.stats.profiles.ai_completion_rate)} className="h-2" />
          </div>
        </div>

        {/* Posts Statistics */}
        <div className="space-y-3">
          <h4 className="font-medium text-sm">Posts</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.stats.posts.total.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">Total Posts</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.stats.posts.with_ai_analysis.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">With AI Analysis</div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">AI Completion Rate</span>
              <span className="text-sm font-medium">{stats.stats.posts.ai_completion_rate}</span>
            </div>
            <Progress value={parseCompletionRate(stats.stats.posts.ai_completion_rate)} className="h-2" />
          </div>
        </div>

        {/* Last Updated */}
        <div className="text-xs text-muted-foreground text-center pt-2 border-t">
          Auto-refreshes every minute • {stats.message}
        </div>
      </CardContent>
    </Card>
  )
}
```

---

## 📡 API Client Setup

### 1. API Client Configuration
```typescript
// lib/api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

class APIClient {
  private baseURL: string
  private token: string | null = null

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  setAuthToken(token: string) {
    this.token = token
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseURL}${endpoint}`
    
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    return fetch(url, {
      ...options,
      headers,
    })
  }

  async get(endpoint: string, options?: RequestInit) {
    return this.request(endpoint, { ...options, method: 'GET' })
  }

  async post(endpoint: string, data?: any, options?: RequestInit) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }
}

export const api = new APIClient(API_BASE_URL)
```

### 2. React Query Provider Setup
```typescript
// providers/query-provider.tsx
"use client"

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            gcTime: 5 * 60 * 1000, // 5 minutes (replaces cacheTime)
            retry: (failureCount, error: any) => {
              // Don't retry on 4xx errors
              if (error?.status >= 400 && error?.status < 500) {
                return false
              }
              return failureCount < 3
            },
          },
          mutations: {
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

---

## 🖼️ Image Handling Strategy

### 1. Profile Images (Avatars)
```typescript
// Image Priority Order:
// 1. CDN optimized image (256px/512px WebP)
// 2. Original Instagram URL (fallback)
// 3. Placeholder image

const ProfileAvatar: React.FC<{ username: string }> = ({ 
  username
}) => {
  const cdnMedia = useCDNMedia(username)
  const [imageError, setImageError] = useState(false)

  const getImageSrc = () => {
    // Try CDN first (if not placeholder)
    if (cdnMedia.data?.avatar && !cdnMedia.data.avatar.placeholder) {
      return cdnMedia.data.avatar["256"] // or "512" for high-res
    }
    
    // Fallback to original URL
    if (originalProfilePicUrl && !imageError) {
      return originalProfilePicUrl
    }
    
    // Final fallback to placeholder
    return `${cdnMedia.data?.cdn_info?.base_url}/placeholders/avatar-256.webp`
  }

  return (
    <Avatar>
      <AvatarImage
        src={getImageSrc()}
        alt={username}
        onError={() => setImageError(true)}
      />
      <AvatarFallback>
        {cdnMedia.isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <User className="h-4 w-4" />
        )}
      </AvatarFallback>
    </Avatar>
  )
}
```

### 2. Post Thumbnails
```typescript
// Post thumbnail component with proper fallbacks
const PostThumbnail: React.FC<{ 
  postId: string
  username: string
  size?: 256 | 512
}> = ({ postId, username, size = 256 }) => {
  const cdnMedia = useCDNMedia(username)
  const [imageError, setImageError] = useState(false)

  const postData = cdnMedia.data?.posts?.find(p => p.mediaId === postId)
  
  const getImageSrc = () => {
    if (postData && !postData.placeholder) {
      return postData.thumb[size.toString()]
    }
    
    // Fallback to placeholder
    return `${cdnMedia.data?.cdn_info?.base_url}/placeholders/post-${size}.webp`
  }

  return (
    <div className="relative aspect-square rounded-lg overflow-hidden bg-muted">
      <img
        src={getImageSrc()}
        alt="Post thumbnail"
        className="w-full h-full object-cover transition-opacity duration-200"
        onError={() => setImageError(true)}
        loading="lazy"
      />
      
      {postData?.placeholder && (
        <div className="absolute inset-0 flex items-center justify-center bg-orange-50/80">
          <div className="text-orange-600 text-xs font-medium">Processing</div>
        </div>
      )}
    </div>
  )
}
```

### 3. Image Processing Status
```typescript
// Show processing status for images
const ImageProcessingStatus: React.FC<{ 
  processing: CDNMediaResponse['processing_status'] 
}> = ({ processing }) => {
  if (processing.completion_percentage === 100) {
    return null // All images processed
  }

  return (
    <Card className="bg-blue-50 border-blue-200">
      <CardContent className="pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-blue-700">
            Optimizing Images
          </span>
          <Badge className="bg-blue-100 text-blue-700">
            {processing.completion_percentage}%
          </Badge>
        </div>
        <Progress 
          value={processing.completion_percentage} 
          className="h-2"
        />
        <p className="text-xs text-blue-600 mt-2">
          {processing.completed_assets} of {processing.total_assets} images processed
        </p>
      </CardContent>
    </Card>
  )
}
```

---

## 🔄 2-Step Serving Implementation

### The Problem:
Your frontend shows "AI Analysis in progress" even for profiles served from database AND is polling a non-existent status endpoint.

### The WRONG Way (Current Frontend):
```typescript
// ❌ WRONG - This causes 404 errors and unnecessary polling
const BadCreatorComponent = ({ username }) => {
  const [searchResult, setSearchResult] = useState(null)
  
  // Wrong: Start search
  const search = useCreatorSearch()
  
  // Wrong: Always poll status endpoint (causes 404s!)
  const status = useProfileStatus(username) // ← THIS CAUSES 404 SPAM
  
  // Wrong: Show processing even for cached profiles
  if (status.data?.status !== 'complete') {
    return <div>AI Analysis in Progress...</div> // ❌ Wrong for cached!
  }
  
  return <ProfileDisplay data={searchResult} />
}
```

### The CORRECT Way (2-Step Serving):
```typescript
// ✅ CORRECT - Respects 2-step serving architecture
const CorrectCreatorComponent = ({ username }) => {
  const [searchResult, setSearchResult] = useState(null)
  
  const search = useCreatorSearch({
    onSuccess: (data) => {
      setSearchResult(data)
      
      // ✅ CRITICAL: Check the cached field!
      if (data.cached) {
        // Profile from database - show immediately, no polling needed!
        console.log('Database profile - ready immediately!')
      } else {
        // New profile - background processing queued
        console.log('New profile - background processing started')
      }
    }
  })
  
  // ✅ CORRECT: Show appropriate status based on data source
  const getStatusDisplay = () => {
    if (!searchResult) return "Loading..."
    
    if (searchResult.cached) {
      // From database - complete immediately
      return "✅ Profile Ready"
    } else {
      // New profile - processing in background
      return "🔄 Profile Fetched • Background Analysis Queued"
    }
  }
  
  return (
    <div>
      <div className="status">{getStatusDisplay()}</div>
      {searchResult && <ProfileDisplay data={searchResult.profile} />}
    </div>
  )
}
```

### The Solution:
```typescript
// Correct 2-step serving handling
const CreatorProfilePage: React.FC<{ username: string }> = ({ username }) => {
  const [initialData, setInitialData] = useState<ProfileSearchResponse | null>(null)
  const creatorSearch = useCreatorSearch({
    onSuccess: (data) => {
      setInitialData(data)
    }
  })

  // Show appropriate status based on data source
  const getAnalysisStatus = () => {
    if (!initialData) return "Loading..."
    
    if (initialData.cached) {
      // Profile from database - show complete data
      return "Profile analysis complete"
    } else {
      // Fresh profile - may trigger background processing
      return "Profile data fetched • Background analysis queued"
    }
  }

  return (
    <div className="space-y-4">
      {initialData && (
        <>
          <Alert>
            <AlertDescription>
              {getAnalysisStatus()}
            </AlertDescription>
          </Alert>
          
          <ProfileCard 
            profile={initialData.profile} 
            showAI={initialData.cached} // Only show AI data for cached profiles
          />
          
          {/* Show processing indicator ONLY for new profiles */}
          {!initialData.cached && (
            <Card className="bg-yellow-50 border-yellow-200">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-yellow-600" />
                  <span className="text-sm font-medium text-yellow-700">
                    Processing profile in background...
                  </span>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
```

---

## 📋 Implementation Checklist

### ✅ Required Dependencies
```bash
npm install @tanstack/react-query @tanstack/react-query-devtools
npm install lucide-react class-variance-authority clsx tailwind-merge
```

### ✅ File Structure
```
components/
├── ui/ (SHADCN components)
├── creator-search.tsx
├── profile-card.tsx
├── profile-image-with-fallback.tsx
├── system-dashboard.tsx
├── post-thumbnail.tsx
└── image-processing-status.tsx

hooks/
├── useCreatorSearch.ts
├── useProfile.ts
├── useCDNMedia.ts
└── useSystemStats.ts

lib/
├── api.ts
└── utils.ts (SHADCN utils)

providers/
└── query-provider.tsx
```

### ✅ Environment Variables
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### ✅ Main App Integration
```typescript
// app/layout.tsx
import { QueryProvider } from '@/providers/query-provider'

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  )
}
```

---

## 🎯 Critical Implementation Rules

### ❌ DO NOT DO:
1. **Show "AI Analysis in Progress" for cached profiles** - Use `response.cached` to determine display
2. **Use placeholder images for working CDN** - Always try CDN first, then fallback
3. **Mix UI libraries** - Only SHADCN components allowed
4. **Ignore 2-step serving** - Always show immediate data first
5. **Make multiple API calls for same data** - Use React Query caching properly
6. **Show loading spinners for cached data** - Instant display for database profiles
7. **Poll status endpoint unnecessarily** - Only poll for genuinely unknown profiles
8. **Use status polling for cached profiles** - Database profiles are immediately ready

### ✅ MUST DO:
1. **Check `cached` field** - Show appropriate messaging based on data source
2. **Use CDN media endpoint** - Get proper image URLs with fallbacks
3. **Handle loading states properly** - Show skeletons while loading, instant for cached
4. **Implement proper error boundaries** - Graceful error handling
5. **Use React Query correctly** - Proper caching and background updates
6. **Follow image priority order** - CDN → Original → Placeholder
7. **Show processing status only when needed** - For new profiles and image processing

---

## 🚀 Quick Start Integration

### Step 1: Install Dependencies
```bash
# Core dependencies
npm install @tanstack/react-query @tanstack/react-query-devtools
npm install lucide-react class-variance-authority clsx tailwind-merge

# SHADCN components (install as needed)
npx shadcn-ui@latest add button card input avatar badge alert progress separator
```

### Step 2: Set up API Client
```typescript
// lib/api.ts - Copy exact implementation from above
// This handles all authentication and error handling
```

### Step 3: Add Query Provider
```typescript
// providers/query-provider.tsx - Copy exact implementation from above
// Wrap your app with this provider
```

### Step 4: Create Hooks
```typescript
// hooks/ - Copy all hook implementations from above
// These handle all API calls and caching logic
```

### Step 5: Build Components
```typescript
// components/ - Copy all component implementations from above  
// These handle proper 2-step serving and image display
```

### Step 6: Integration Example
```typescript
// pages/creator/[username].tsx
"use client"

import { useRouter } from 'next/router'
import { CreatorSearch } from '@/components/creator-search'
import { SystemDashboard } from '@/components/system-dashboard'

export default function CreatorPage() {
  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">Creator Analytics</h1>
      
      <div className="grid lg:grid-cols-2 gap-6">
        <CreatorSearch />
        <SystemDashboard />
      </div>
    </div>
  )
}
```

---

## 🔍 Testing Your Integration

### 1. Test 2-Step Serving
```typescript
// Test with existing profile (should show cached: true)
const response = await api.post('/simple/creator/search/cristiano')
console.log('Cached:', response.cached) // Should be true for existing profiles

// Test with new profile (should show cached: false)  
const response2 = await api.post('/simple/creator/search/newuser123')
console.log('Cached:', response2.cached) // Should be false for new profiles
```

### 2. Test CDN Images
```typescript
// Test CDN media endpoint - now supports username OR UUID!
const cdnData = await api.get('/creators/ig/deals.food/media') // Username works!
// OR
const cdnData2 = await api.get('/creators/ig/d62a8790-8472-412a-ab03-5623e25e45ff/media') // UUID works!

console.log('Avatar available:', !cdnData.avatar.placeholder)
console.log('Processing %:', cdnData.processing_status.completion_percentage)
```

### 3. Verify Component Behavior
- ✅ Cached profiles should show data instantly (no loading spinner)
- ✅ New profiles should show loading, then success message
- ✅ Images should display from CDN when available
- ✅ Fallback images should work when CDN is processing
- ✅ No "AI Analysis in Progress" for database profiles

---

## 🐛 Troubleshooting

### Issue: Images not displaying
**Solution**: Check CDN endpoint response and image URL structure
```typescript
// Debug CDN response
const cdnData = await useCDNMedia(profileId)
console.log('CDN Response:', cdnData.data)
console.log('Avatar URL:', cdnData.data?.avatar?.["256"])
```

### Issue: "AI Analysis in Progress" for cached profiles
**Solution**: Check the `cached` field in API response
```typescript
// Verify cached field usage
if (profileResponse.cached) {
  // Show complete data, no processing indicators
} else {
  // Show processing indicators for new profiles only
}
```

### Issue: Multiple API calls for same data
**Solution**: Verify React Query setup and caching keys
```typescript
// Check query keys match across hooks
useQuery({ queryKey: ['profile', username] }) // Must be consistent
```

### Issue: Status endpoint 404 errors (polling spam)
**Solution**: Stop polling status endpoint for cached profiles
```typescript
// ❌ WRONG - Causes 404 spam
const status = useProfileStatus(username) // Always polls

// ✅ CORRECT - Only poll when needed
const shouldPoll = searchResult && !searchResult.cached && searchResult.status !== 'complete'
const status = useProfileStatus(shouldPoll ? username : undefined)
```

---

## 📞 Support

If you encounter issues:

1. **Check API responses** - Verify the response structure matches the interfaces
2. **Review React Query DevTools** - Check caching behavior and query states  
3. **Inspect Network tab** - Verify correct endpoints are being called
4. **Check console errors** - Look for TypeScript errors or API failures

**This guide provides everything needed for a complete, working frontend integration that respects our 2-step serving architecture and displays images correctly.**

---

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Create comprehensive SHADCN frontend integration guide", "status": "completed", "activeForm": "Creating comprehensive SHADCN frontend integration guide"}, {"content": "Document proper image handling for CDN integration", "status": "in_progress", "activeForm": "Documenting proper image handling for CDN integration"}, {"content": "Write React Query hooks for 2-step serving pattern", "status": "completed", "activeForm": "Writing React Query hooks for 2-step serving pattern"}, {"content": "Create SHADCN components that respect backend data structure", "status": "completed", "activeForm": "Creating SHADCN components that respect backend data structure"}, {"content": "Add usage examples and implementation checklist", "status": "pending", "activeForm": "Adding usage examples and implementation checklist"}]