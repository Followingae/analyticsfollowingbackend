# DigitalOcean Deployment Guide

## Production-Ready Build for DigitalOcean App Platform

### Key Fixes Applied:
1. **Fixed `databases` module dependency** - Updated to compatible version 0.7.0
2. **Fixed SQLAlchemy compatibility** - Downgraded to 1.4.50 for databases compatibility
3. **Fixed port configuration** - Now uses dynamic PORT environment variable
4. **Added production dependencies** - Including psycopg2-binary for PostgreSQL
5. **Created startup script** - Handles environment variables properly

### Deployment Options:

#### Option 1: Using DigitalOcean App Platform (Recommended)
1. Push your code to GitHub
2. Use the configuration file: `.do/app.yaml`
3. Set environment variables in DigitalOcean dashboard:
   - `SMARTPROXY_USERNAME`
   - `SMARTPROXY_PASSWORD` 
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `JWT_SECRET_KEY`

#### Option 2: Using Docker Container
1. Build: `docker build -t analytics-backend .`
2. Run: `docker run -p 8080:8080 -e PORT=8080 analytics-backend`

### Environment Variables Required:
```env
# Required for production
DEBUG=false
PORT=8080
DATABASE_URL=postgresql://user:password@host:port/database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
JWT_SECRET_KEY=your-secure-secret-key
SMARTPROXY_USERNAME=your-username
SMARTPROXY_PASSWORD=your-password

# Optional
ALLOWED_ORIGINS=https://your-frontend-domain.com
MAX_REQUESTS_PER_HOUR=500
MAX_CONCURRENT_REQUESTS=5
```

### Health Check Endpoint:
- `GET /health` - Returns service status

### Key Changes Made:
- Updated requirements.txt with compatible package versions
- Fixed Dockerfile to use dynamic PORT environment variable
- Created startup script for flexible port handling
- Added system dependencies (libpq-dev, gcc, python3-dev) in Dockerfile
- Set DEBUG=false by default for production
- Added DigitalOcean App Platform configuration

### Deployment Command:
The app will start with: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`

Your deployment should now work successfully on DigitalOcean! 🚀