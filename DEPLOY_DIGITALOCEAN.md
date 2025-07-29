# Deploy Backend to DigitalOcean

## Current Situation
- Frontend is on Vercel showing "failed to fetch"
- Backend needs to be deployed to DigitalOcean
- No working backend URLs found

## DigitalOcean Deployment Steps

### 1. Create DigitalOcean App
1. Go to [DigitalOcean Apps](https://cloud.digitalocean.com/apps)
2. Click "Create App"
3. Connect your GitHub repository
4. Select this backend repository

### 2. Configure App Settings
```yaml
name: analytics-following-backend
services:
- name: web
  source_dir: /
  github:
    repo: your-username/analyticsfollowingbackend
    branch: main
  run_command: python main.py
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  routes:
  - path: /
```

### 3. Environment Variables to Set
```
DATABASE_URL=your_postgresql_url
SUPABASE_URL=https://gzqruamgxhgsaeyiepns.supabase.co
SUPABASE_KEY=your_supabase_key
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8080
SMARTPROXY_USERNAME=S0000190509
SMARTPROXY_PASSWORD=TLcWT54ys0pxja~4gj
JWT_SECRET_KEY=analytics-following-backend-jwt-secret-key-change-in-production-2024
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

### 4. Required Files Check
- ✅ `main.py` (entry point)
- ✅ `requirements.txt` (dependencies)
- ✅ `app/` directory (application code)
- ❓ `Procfile` or run command

### 5. Create Procfile (if needed)
```
web: python main.py
```

### 6. Alternative: Use App Spec
```yaml
name: analytics-following-backend
services:
- name: web
  source_dir: /
  github:
    repo: your-username/analyticsfollowingbackend
    branch: main
  run_command: uvicorn main:app --host 0.0.0.0 --port $PORT
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8080
  routes:
  - path: /
```

## After Deployment

1. **Get the App URL** from DigitalOcean dashboard
2. **Test the backend** by visiting the URL
3. **Update frontend env vars** with the new backend URL
4. **Redeploy frontend** on Vercel

## Expected Result

After deployment, you should have:
- Working backend URL: `https://your-app-name.ondigitalocean.app`
- API accessible at: `https://your-app-name.ondigitalocean.app/api/v1`
- Health check: `https://your-app-name.ondigitalocean.app/health`