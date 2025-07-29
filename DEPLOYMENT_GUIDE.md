# Analytics Following Backend - Deployment Guide

## 🚀 Deploy to analytics.following.ae

### Option 1: Railway (Recommended)

1. **Setup Railway Account**
   - Go to [railway.app](https://railway.app)
   - Connect your GitHub account
   - Create new project from GitHub repo

2. **Environment Variables**
   Copy these to Railway dashboard:
   ```
   DEBUG=False
   ENVIRONMENT=production
   SUPABASE_URL=https://gzqruamgxhgsaeyiepns.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd6cXJ1YW1neGhnc2FleWllcG5zIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYwNjgyMSwiZXhwIjoyMDY5MTgyODIxfQ.9QEZPQO0wZTrNETSq23UjeorCjzr4O25mS8jAQSaG24
   SMARTPROXY_USERNAME=your_username
   SMARTPROXY_PASSWORD=your_password
   JWT_SECRET_KEY=your-super-secure-jwt-secret-key
   ALLOWED_ORIGINS=https://following.ae,https://www.following.ae,https://app.following.ae
   ```

3. **Custom Domain Setup**
   - In Railway dashboard: Settings > Domains
   - Add custom domain: `analytics.following.ae`
   - Copy the CNAME target Railway provides
   - Give this to your domain registrar

4. **Deploy**
   - Railway auto-deploys on git push
   - Monitor logs in Railway dashboard

### Option 2: DigitalOcean App Platform

1. **Create App**
   - Go to DigitalOcean > Apps
   - Connect GitHub repo
   - Choose "Web Service"

2. **Configure**
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Add environment variables from above

3. **Custom Domain**
   - In DO dashboard: Settings > Domains
   - Add `analytics.following.ae`
   - Configure DNS with your registrar

## 🔧 DNS Configuration

### For Domain Registrar (Marlon):

**If using Railway:**
```
Domain: analytics.following.ae
Type: CNAME
Target: [Railway will provide this - something like xxx.railway.app]
TTL: 300 (5 minutes)
```

**If using DigitalOcean:**
```
Domain: analytics.following.ae  
Type: CNAME
Target: [DO will provide this - something like xxx.ondigitalocean.app]
TTL: 300 (5 minutes)
```

**If using direct IP:**
```
Domain: analytics.following.ae
Type: A Record
Target: [Your server IP address]
TTL: 300 (5 minutes)
```

## 🔒 SSL/HTTPS

- Railway: Automatic SSL (Let's Encrypt)
- DigitalOcean: Automatic SSL (Let's Encrypt)
- Custom server: Use Certbot or Cloudflare

## 📋 Post-Deployment Checklist

1. ✅ Domain points to hosting service
2. ✅ SSL certificate active (https://)
3. ✅ Health check: `https://analytics.following.ae/health`
4. ✅ API docs: `https://analytics.following.ae/docs`
5. ✅ Test login endpoint
6. ✅ Update frontend to use new domain
7. ✅ Test CORS from frontend domain

## 🧪 Testing Production

```bash
# Health check
curl https://analytics.following.ae/health

# Login test
curl -X POST https://analytics.following.ae/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"client@analyticsfollowing.com","password":"ClientPass2024!"}'

# Profile test (with token)
curl -X GET https://analytics.following.ae/api/v1/instagram/profile/instagram/simple \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🚨 Important Notes

1. **Security**: Never commit `.env` files to git
2. **Credentials**: Use hosting platform's environment variables
3. **HTTPS Only**: All production traffic should be HTTPS
4. **CORS**: Update frontend to use `https://analytics.following.ae`
5. **Monitoring**: Set up logging and monitoring in production

## 📞 Support

If deployment fails:
1. Check hosting platform logs
2. Verify environment variables
3. Test health endpoint
4. Check DNS propagation