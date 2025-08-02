# 🎯 Frontend Endpoint Usage Guide

## ✅ **FIXED: No More Duplicate Decodo Calls!**

The backend now has **TWO SEPARATE ENDPOINTS** to eliminate duplicate API calls:

---

## 🔍 **Endpoint 1: Profile Search/Preview**

**URL**: `GET /api/v1/instagram/profile/{username}`  
**Purpose**: Initial profile search and preview  
**Behavior**: 
- ✅ Checks database first
- ✅ If not found: Fetches from Decodo + Stores in database
- ✅ If found: Returns cached data instantly
- ✅ Grants 30-day user access

**Frontend Usage**: 
```javascript
// Use for search and preview cards
const response = await fetch(`/api/v1/instagram/profile/${username}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();

// Show preview card with:
// - data.profile.username
// - data.profile.followers_count  
// - data.profile.profile_pic_url
```

---

## 📊 **Endpoint 2: Detailed Analytics** 

**URL**: `GET /api/v1/instagram/profile/{username}/analytics`  
**Purpose**: "View Analysis" detailed page  
**Behavior**:
- ✅ **ONLY reads from database** 
- ✅ **NEVER calls Decodo**
- ✅ Instant response (~0.5 seconds)
- ❌ Returns 404 if profile not unlocked yet

**Frontend Usage**:
```javascript
// Use for "View Analysis" button clicks
const response = await fetch(`/api/v1/instagram/profile/${username}/analytics`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

if (response.status === 404) {
  // Profile not unlocked yet - redirect to search
  window.location.href = `/search?q=${username}`;
} else {
  const data = await response.json();
  // Show detailed analytics page
}
```

---

## 🔄 **Correct Frontend Flow**

### **Step 1: User Searches Profile**
```javascript
// Frontend calls: GET /api/v1/instagram/profile/shaq
// Backend: Checks DB → Not found → Calls Decodo → Stores → Returns data
// Response time: ~15-30 seconds
// Frontend: Shows preview card with "Unlocked" status
```

### **Step 2: User Clicks "View Analysis"** 
```javascript
// Frontend calls: GET /api/v1/instagram/profile/shaq/analytics  
// Backend: Reads from DB only → Returns cached data
// Response time: ~0.5 seconds  
// Frontend: Shows detailed analytics page
```

### **Step 3: User Searches Same Profile Again**
```javascript
// Frontend calls: GET /api/v1/instagram/profile/shaq
// Backend: Checks DB → Found → Returns cached data
// Response time: ~0.5 seconds
// Frontend: Shows preview card instantly
```

---

## 🚫 **What's ELIMINATED**

❌ **No more duplicate Decodo calls**  
❌ **No more rate limiting issues**  
❌ **No more 60+ second waits for detailed analytics**  
❌ **No more "Analysis Failed" messages**  

---

## 📋 **Frontend Update Checklist**

### **Update Search/Preview Components:**
- [ ] Use `/api/v1/instagram/profile/{username}` for initial search
- [ ] Handle 15-30 second response time with loading indicator
- [ ] Show "Unlocked" status when profile is cached

### **Update "View Analysis" Button:**
- [ ] Use `/api/v1/instagram/profile/{username}/analytics` for detailed view
- [ ] Expect instant response (~0.5 seconds)
- [ ] Handle 404 error by redirecting to search

### **Error Handling:**
```javascript
// For analytics endpoint 404 errors:
if (response.status === 404) {
  showMessage("Please search for this profile first to unlock analytics");
  // Redirect to search or auto-trigger search
}
```

### **Loading States:**
```javascript
// Search/Preview: Long loading (15-30s)
setLoading(true);
setMessage("Analyzing profile... This may take up to 30 seconds");

// Analytics: Short loading (0.5s)  
setLoading(true);
setMessage("Loading analytics...");
```

---

## 🎯 **Key Benefits**

✅ **Single Decodo Call**: Each profile is only fetched once  
✅ **Instant Analytics**: "View Analysis" loads in ~0.5 seconds  
✅ **30-Day Caching**: Users can access unlocked profiles for 30 days  
✅ **No Rate Limiting**: Eliminates duplicate API call issues  
✅ **Better UX**: Clear separation between search and analytics  

---

## 🔧 **Testing**

**Test Profile Search:**
```bash
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8000/api/v1/instagram/profile/shaq"
```

**Test Analytics (after search):**
```bash
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8000/api/v1/instagram/profile/shaq/analytics"  
```

**Test Analytics (before search):**
```bash
# Should return 404 with helpful error message
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8000/api/v1/instagram/profile/newprofile/analytics"
```

---

## 🚀 **Ready to Deploy!**

The backend is now properly configured with:
- ✅ Database caching working
- ✅ Two separate endpoints  
- ✅ No duplicate Decodo calls
- ✅ Proper error handling
- ✅ 30-day user access system

Frontend just needs to use the correct endpoints! 🎉