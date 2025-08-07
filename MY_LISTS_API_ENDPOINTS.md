# My Lists API Endpoints Documentation

## Overview
Complete API endpoints for the My Lists module allowing users to create, manage, and organize their unlocked Instagram profiles into custom lists.

## Base URL
All endpoints assume base URL: `/api/v1`

## Authentication
All endpoints require authentication via Supabase JWT token in Authorization header:
```
Authorization: Bearer <jwt_token>
```

---

## 📋 Lists Management

### GET /lists
Get all lists for the authenticated user

**Query Parameters:**
- `include_items` (boolean, optional): Include list items in response (default: false)
- `sort` (string, optional): Sort order - "created_at", "updated_at", "name", "items_count" (default: "created_at")
- `order` (string, optional): "asc" or "desc" (default: "desc")
- `page` (integer, optional): Page number for pagination (default: 1)
- `limit` (integer, optional): Items per page (default: 20, max: 100)

**Response:**
```json
{
  "success": true,
  "data": {
    "lists": [
      {
        "id": "uuid",
        "name": "Fitness Influencers",
        "description": "Top fitness creators to follow",
        "color": "#3B82F6",
        "icon": "dumbbell",
        "is_public": false,
        "is_favorite": true,
        "sort_order": 0,
        "items_count": 12,
        "created_at": "2025-08-07T10:00:00Z",
        "updated_at": "2025-08-07T10:00:00Z",
        "last_updated": "2025-08-07T10:00:00Z",
        "items": [] // Only if include_items=true
      }
    ],
    "pagination": {
      "current_page": 1,
      "total_pages": 2,
      "total_items": 25,
      "items_per_page": 20
    }
  }
}
```

### GET /lists/{list_id}
Get a specific list with all its items

**Path Parameters:**
- `list_id` (uuid): List identifier

**Query Parameters:**
- `include_profiles` (boolean, optional): Include full profile data (default: true)
- `sort_items` (string, optional): Sort items by "position", "added_at", "name" (default: "position")

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Fitness Influencers",
    "description": "Top fitness creators to follow",
    "color": "#3B82F6",
    "icon": "dumbbell",
    "is_public": false,
    "is_favorite": true,
    "sort_order": 0,
    "items_count": 12,
    "created_at": "2025-08-07T10:00:00Z",
    "updated_at": "2025-08-07T10:00:00Z",
    "last_updated": "2025-08-07T10:00:00Z",
    "items": [
      {
        "id": "uuid",
        "position": 0,
        "notes": "Great workout content",
        "tags": ["fitness", "motivation"],
        "is_pinned": true,
        "color_label": "#F59E0B",
        "added_at": "2025-08-07T10:00:00Z",
        "updated_at": "2025-08-07T10:00:00Z",
        "profile": {
          "id": "uuid",
          "username": "fitness_guru",
          "full_name": "Fitness Guru",
          "followers_count": 150000,
          "is_verified": true,
          "profile_pic_url": "https://...",
          "engagement_rate": 4.2
        }
      }
    ]
  }
}
```

### POST /lists
Create a new list

**Request Body:**
```json
{
  "name": "Tech Creators",
  "description": "Innovation and tech influencers",
  "color": "#10B981",
  "icon": "code",
  "is_favorite": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Tech Creators",
    "description": "Innovation and tech influencers",
    "color": "#10B981",
    "icon": "code",
    "is_public": false,
    "is_favorite": false,
    "sort_order": 0,
    "items_count": 0,
    "created_at": "2025-08-07T10:00:00Z",
    "updated_at": "2025-08-07T10:00:00Z",
    "last_updated": null
  }
}
```

### PUT /lists/{list_id}
Update an existing list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Request Body:**
```json
{
  "name": "Updated Tech Creators",
  "description": "Best tech influencers and innovators",
  "color": "#8B5CF6",
  "icon": "laptop",
  "is_favorite": true
}
```

**Response:** Same as GET /lists/{list_id}

### DELETE /lists/{list_id}
Delete a list and all its items

**Path Parameters:**
- `list_id` (uuid): List identifier

**Response:**
```json
{
  "success": true,
  "message": "List deleted successfully"
}
```

---

## 📝 List Items Management

### POST /lists/{list_id}/items
Add a profile to a list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Request Body:**
```json
{
  "profile_id": "uuid",
  "position": 0,
  "notes": "Excellent content creator",
  "tags": ["tech", "innovation"],
  "is_pinned": false,
  "color_label": "#F59E0B"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "position": 0,
    "notes": "Excellent content creator",
    "tags": ["tech", "innovation"],
    "is_pinned": false,
    "color_label": "#F59E0B",
    "added_at": "2025-08-07T10:00:00Z",
    "updated_at": "2025-08-07T10:00:00Z",
    "profile": {
      "id": "uuid",
      "username": "tech_innovator",
      "full_name": "Tech Innovator",
      "followers_count": 75000,
      "is_verified": false,
      "profile_pic_url": "https://...",
      "engagement_rate": 3.8
    }
  }
}
```

### PUT /lists/{list_id}/items/{item_id}
Update a list item

**Path Parameters:**
- `list_id` (uuid): List identifier
- `item_id` (uuid): List item identifier

**Request Body:**
```json
{
  "position": 2,
  "notes": "Updated notes about this creator",
  "tags": ["tech", "ai", "innovation"],
  "is_pinned": true,
  "color_label": "#EF4444"
}
```

**Response:** Same as POST response

### DELETE /lists/{list_id}/items/{item_id}
Remove a profile from a list

**Path Parameters:**
- `list_id` (uuid): List identifier
- `item_id` (uuid): List item identifier

**Response:**
```json
{
  "success": true,
  "message": "Profile removed from list successfully"
}
```

### POST /lists/{list_id}/items/bulk
Add multiple profiles to a list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Request Body:**
```json
{
  "profile_ids": ["uuid1", "uuid2", "uuid3"],
  "notes": "Bulk added profiles",
  "tags": ["bulk", "import"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "added_count": 3,
    "skipped_count": 0,
    "items": [
      // Array of created items
    ]
  }
}
```

---

## 🔄 List Operations

### PUT /lists/{list_id}/reorder
Reorder items in a list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Request Body:**
```json
{
  "item_positions": [
    {"item_id": "uuid1", "position": 0},
    {"item_id": "uuid2", "position": 1},
    {"item_id": "uuid3", "position": 2}
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "List reordered successfully",
  "data": {
    "updated_count": 3
  }
}
```

### POST /lists/{list_id}/duplicate
Duplicate a list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Request Body:**
```json
{
  "name": "Copy of Fitness Influencers",
  "include_items": true
}
```

**Response:** Same as POST /lists response

### POST /lists/bulk-operations
Perform bulk operations on lists

**Request Body:**
```json
{
  "operation": "delete", // "delete", "archive", "favorite"
  "list_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "processed_count": 3,
    "failed_count": 0
  }
}
```

---

## 📊 Analytics & Insights

### GET /lists/{list_id}/analytics
Get analytics for profiles in a list

**Path Parameters:**
- `list_id` (uuid): List identifier

**Query Parameters:**
- `period` (string, optional): "7d", "30d", "90d" (default: "30d")
- `metrics` (string, optional): Comma-separated list of metrics to include

**Response:**
```json
{
  "success": true,
  "data": {
    "list_summary": {
      "total_profiles": 12,
      "total_followers": 1250000,
      "average_engagement_rate": 4.2,
      "verified_count": 8
    },
    "engagement_trends": {
      "labels": ["2025-07-01", "2025-07-02", "..."],
      "datasets": [
        {
          "label": "Average Engagement Rate",
          "data": [4.1, 4.3, 4.2, "..."]
        }
      ]
    },
    "top_performers": [
      {
        "profile": {
          "username": "top_creator",
          "engagement_rate": 6.8
        }
      }
    ],
    "categories": {
      "fitness": 5,
      "nutrition": 3,
      "lifestyle": 4
    }
  }
}
```

### GET /lists/summary
Get summary statistics for all user lists

**Response:**
```json
{
  "success": true,
  "data": {
    "total_lists": 8,
    "total_profiles": 156,
    "average_list_size": 19.5,
    "most_popular_categories": ["fitness", "tech", "lifestyle"],
    "recent_activity": [
      {
        "type": "list_created",
        "list_name": "New Tech List",
        "timestamp": "2025-08-07T10:00:00Z"
      }
    ]
  }
}
```

---

## 🔍 Search & Discovery

### GET /profiles/available-for-lists
Get user's unlocked profiles that can be added to lists

**Query Parameters:**
- `search` (string, optional): Search by username or full name
- `not_in_list` (uuid, optional): Exclude profiles already in this list
- `category` (string, optional): Filter by category
- `min_followers` (integer, optional): Minimum followers count
- `verified_only` (boolean, optional): Only verified profiles
- `page` (integer, optional): Page number (default: 1)
- `limit` (integer, optional): Items per page (default: 20)

**Response:**
```json
{
  "success": true,
  "data": {
    "profiles": [
      {
        "id": "uuid",
        "username": "available_creator",
        "full_name": "Available Creator",
        "followers_count": 45000,
        "is_verified": true,
        "profile_pic_url": "https://...",
        "engagement_rate": 3.5,
        "access_expires_at": "2025-09-06T10:00:00Z",
        "in_lists_count": 2
      }
    ],
    "pagination": {
      "current_page": 1,
      "total_pages": 5,
      "total_items": 89,
      "items_per_page": 20
    }
  }
}
```

---

## ❌ Error Responses

All endpoints may return these error formats:

### 400 Bad Request
```json
{
  "success": false,
  "error": "validation_error",
  "message": "Invalid request data",
  "details": {
    "name": ["Name is required"]
  }
}
```

### 401 Unauthorized
```json
{
  "success": false,
  "error": "unauthorized",
  "message": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "success": false,
  "error": "forbidden",
  "message": "You don't have access to this profile"
}
```

### 404 Not Found
```json
{
  "success": false,
  "error": "not_found",
  "message": "List not found"
}
```

### 409 Conflict
```json
{
  "success": false,
  "error": "conflict",
  "message": "Profile already exists in this list"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": "internal_error",
  "message": "An unexpected error occurred"
}
```

---

## 🔧 Implementation Notes

### Frontend Integration Tips:

1. **List Colors**: Use the `color` field for UI theming and visual distinction
2. **Icons**: The `icon` field contains icon identifiers for your icon library
3. **Drag & Drop**: Use the `position` field for implementing drag-and-drop reordering
4. **Real-time Updates**: Consider WebSocket integration for real-time list updates
5. **Infinite Scroll**: Use pagination for large lists and profile searches
6. **Access Validation**: Check `user_profile_access` before allowing profiles to be added
7. **Bulk Operations**: Use bulk endpoints for better performance with multiple operations

### Database Considerations:

1. All operations respect Row Level Security (RLS) policies
2. User can only access their own lists and list items
3. Profile access is validated against `user_profile_access` table
4. Automatic cleanup when profiles or users are deleted
5. Triggers maintain `items_count` and `last_updated` automatically

### Performance Notes:

1. List queries are optimized with proper indexing
2. Use `include_items=false` for list overview pages
3. Implement caching for frequently accessed lists
4. Use pagination for large datasets
5. Consider database connection pooling for high concurrency

---

This API provides complete CRUD operations for the My Lists feature with proper authentication, validation, and error handling.