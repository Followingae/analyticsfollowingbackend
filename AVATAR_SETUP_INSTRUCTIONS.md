# USER AVATAR SYSTEM - SETUP INSTRUCTIONS

## BACKEND SETUP COMPLETED ✅

### What Was Implemented:

1. **Database Schema** - `database/migrations/user_avatars_schema.sql`
   - `user_avatars` table with RLS policies
   - Updated `users` table with `avatar_url` column
   - Proper indexes and constraints

2. **Avatar Service** - `app/services/avatar_service.py`
   - Upload processing with image optimization
   - Supabase Storage integration
   - Avatar priority system (custom → Instagram → initials)
   - Automatic cleanup of old avatars

3. **API Endpoints** - Added to `app/api/cleaned_routes.py`
   - `POST /api/v1/user/avatar/upload` - Upload new avatar
   - `GET /api/v1/user/avatar` - Get current avatar
   - `DELETE /api/v1/user/avatar` - Delete custom avatar
   - `GET /api/v1/user/profile/complete` - Complete profile with avatar priority

4. **Dependencies** - Updated `requirements.txt`
   - Added Pillow for image processing
   - Updated config for Supabase service key

## DEPLOYMENT STEPS:

### 1. Environment Variables (Add to .env):
```bash
# Add these to your .env file:
SUPABASE_SERVICE_KEY=your_supabase_service_key_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
```

### 2. Install New Dependencies:
```bash
pip install -r requirements.txt
```

### 3. Run Database Migration:
```bash
# Connect to your Supabase database and run:
psql -d your_database_url -f database/migrations/user_avatars_schema.sql
```

### 4. Configure Supabase Storage:
1. Go to Supabase Dashboard → Storage
2. Create bucket named `avatars`
3. Set bucket to **Public**
4. Configure bucket policies (see SUPABASE_STORAGE_SETUP.md)

### 5. Test Endpoints:
```bash
# Test health check
curl http://localhost:8000/api/v1/health

# Test avatar upload (requires authentication)
curl -X POST "http://localhost:8000/api/v1/user/avatar/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@test_image.jpg"
```

## AVATAR PRIORITY SYSTEM:

**Priority Order:**
1. **Custom uploaded avatar** (Supabase Storage) - **Highest priority**
2. **Instagram profile picture** (via CORSPROXY.IO) - **Fallback**
3. **Generated initials** - **Final fallback**

**Key Features:**
- ✅ Images automatically resized to 400x400px
- ✅ JPEG optimization with 85% quality
- ✅ Automatic cleanup of old avatars
- ✅ RLS security - users can only access their own avatars
- ✅ Perfect integration with existing authentication
- ✅ Graceful fallback to Instagram profile pictures

## API ENDPOINTS SUMMARY:

### Upload Avatar:
```javascript
POST /api/v1/user/avatar/upload
Content-Type: multipart/form-data
Authorization: Bearer JWT_TOKEN

FormData: { file: File }

Response:
{
  "success": true,
  "avatar_url": "https://your-project.supabase.co/storage/v1/object/public/avatars/user_id/avatar_xxx.jpg",
  "message": "Avatar uploaded successfully"
}
```

### Get Avatar:
```javascript
GET /api/v1/user/avatar
Authorization: Bearer JWT_TOKEN

Response:
{
  "avatar_url": "https://...",
  "has_custom_avatar": true,
  "uploaded_at": "2024-01-01T12:00:00Z",
  "file_size": 45678,
  "processed_size": "400x400"
}
```

### Delete Avatar:
```javascript
DELETE /api/v1/user/avatar
Authorization: Bearer JWT_TOKEN

Response:
{
  "success": true,
  "message": "Avatar deleted successfully",
  "reverted_to": "instagram_profile_picture"
}
```

### Complete Profile:
```javascript
GET /api/v1/user/profile/complete
Authorization: Bearer JWT_TOKEN

Response:
{
  "user": { ... },
  "avatar": {
    "current_url": "https://...",
    "has_custom_avatar": true
  },
  "instagram": {
    "profile_pic_url": "https://...",
    "profile_pic_url_hd": "https://..."
  },
  "meta": {
    "avatar_priority": "custom"
  }
}
```

## BACKEND IMPLEMENTATION IS COMPLETE ✅

The backend is now ready to handle avatar uploads with:
- Supabase Storage integration
- Image processing and optimization
- Proper security via RLS
- Avatar priority system
- Complete API endpoints

**Next: Frontend implementation required**