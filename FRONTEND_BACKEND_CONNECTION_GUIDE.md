# Frontend-Backend Connection Setup

## ✅ Backend Status: WORKING
**Your DigitalOcean Backend:** `https://analytics-following-backend-5qfwj.ondigitalocean.app`

- ✅ Root endpoint working
- ✅ Health check working  
- ❌ Auth endpoint timing out (database connection issue)

## Frontend Configuration (Vercel)

### 1. Add Environment Variables
Go to your Vercel project → Settings → Environment Variables and add:

```
NEXT_PUBLIC_API_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app
NEXT_PUBLIC_API_BASE_URL=https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1
```

### 2. Redeploy Frontend
After adding env vars, trigger a new deployment:
- Go to Vercel dashboard
- Click "Redeploy" or push a commit to trigger new build

## Backend Issues to Fix

### 1. Auth Endpoint Timeout (504 Error)
The auth endpoint is timing out, likely due to:
- Database connection timeout
- Supabase connection issues
- Environment variables not set properly

### 2. Required Environment Variables in DigitalOcean
Make sure these are set in your DigitalOcean app:

```
DATABASE_URL=postgresql://postgres.gzqruamgxhgsaeyiepns:Hhotmail1998%40%40@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://gzqruamgxhgsaeyiepns.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd6cXJ1YW1neGhnc2FleWllcG5zIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYwNjgyMSwiZXhwIjoyMDY5MTgyODIxfQ.9QEZPQO0wZTrNETSq23UjeorCjzr4O25mS8jAQSaG24
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8080
SMARTPROXY_USERNAME=S0000190509
SMARTPROXY_PASSWORD=TLcWT54ys0pxja~4gj
JWT_SECRET_KEY=analytics-following-backend-jwt-secret-key-change-in-production-2024
```

### 3. Add Your Frontend URL to CORS
Add this environment variable in DigitalOcean:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

## Next Steps

1. **Fix Backend Auth:**
   - Check DigitalOcean app logs for database connection errors
   - Verify all environment variables are set
   - Restart the DigitalOcean app

2. **Update Frontend:**
   - Add the backend URL to Vercel env vars
   - Redeploy frontend

3. **Test Connection:**
   - Try logging in with demo credentials:
     - Email: `zzain.ali@outlook.com`
     - Password: `BarakatDemo2024!`

## Demo Account Ready
- ✅ User created: `zzain.ali@outlook.com`
- ✅ 4 Creators with full analytics
- ✅ All mock data populated
- ⏳ Waiting for backend auth fix

Once auth is working, your Barakat demo will be fully functional!