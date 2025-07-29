# Analytics Following Backend

A FastAPI-based backend server that provides Instagram profile analysis using SmartProxy's Social Media Scraping API.

## Features

- 📊 **Comprehensive Instagram Profile Analysis** - Get detailed metrics, engagement rates, and insights
- 🏷️ **Hashtag Analytics** - Analyze hashtag performance and difficulty scores  
- 📈 **Growth Recommendations** - AI-powered suggestions for profile optimization
- 🔍 **Content Strategy Analysis** - Insights on best posting times and content types
- ⚡ **Fast & Reliable** - Built with FastAPI and SmartProxy for high performance

## Prerequisites

1. **SmartProxy Account**: You need a SmartProxy subscription to use this API
   - Sign up at [SmartProxy](https://smartproxy.com) or [Decodo](https://decodo.com)
   - Get your API credentials from the dashboard
   - Plans start from $0.08 per 1,000 requests (7-day free trial available)

2. **Python 3.8+**

## Quick Setup

1. **Clone and navigate to the project:**
   ```bash
   cd analyticsfollowingbackend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your SmartProxy credentials:
   ```env
   SMARTPROXY_USERNAME="your_smartproxy_username"
   SMARTPROXY_PASSWORD="your_smartproxy_password"
   ```

5. **Run the server:**
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:8000`

## API Endpoints

### 🔧 SmartProxy Endpoints (Original)

#### 📊 Comprehensive Profile Analysis
```http
GET /api/v1/instagram/profile/{username}
```

Returns detailed profile analysis using SmartProxy API.

**Example:**
```bash
curl http://localhost:8000/api/v1/instagram/profile/instagram
```

### 🏠 In-House Scraper Endpoints (New!)

#### 📊 In-House Profile Analysis  
```http
GET /api/v1/inhouse/instagram/profile/{username}
```

Returns detailed profile analysis using our in-house web scraping solution:
- Profile metrics (followers, engagement rate, etc.)
- Estimated analytics and insights
- Growth recommendations
- Content strategy suggestions

**Example:**
```bash
curl http://localhost:8000/api/v1/inhouse/instagram/profile/shaq
```

#### 👤 In-House Basic Profile
```http
GET /api/v1/inhouse/instagram/profile/{username}/basic
```

Returns basic profile information using in-house scraper.

**Example:**
```bash
curl http://localhost:8000/api/v1/inhouse/instagram/profile/shaq/basic
```

#### 🧪 Test In-House Scraper
```http
GET /api/v1/inhouse/test
```

Test the in-house scraper functionality.

**Example:**
```bash
curl http://localhost:8000/api/v1/inhouse/test
```

### 👤 Basic Profile Info
```http
GET /api/v1/instagram/profile/{username}/basic
```

Returns basic profile information without detailed analysis.

### 🏷️ Hashtag Analysis
```http
GET /api/v1/instagram/hashtag/{hashtag}
```

Analyze hashtag performance and metrics.

**Example:**
```bash
curl http://localhost:8000/api/v1/instagram/hashtag/fitness
```

### 🔍 API Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Response Example

```json
{
  "profile": {
    "username": "instagram",
    "full_name": "Instagram",
    "followers": 650000000,
    "following": 76,
    "posts_count": 7500,
    "is_verified": true,
    "engagement_rate": 2.5,
    "avg_likes": 1250000,
    "influence_score": 9.8
  },
  "recent_posts": [...],
  "hashtag_analysis": [...],
  "content_strategy": {
    "best_posting_hour": 14,
    "recommended_content_type": "photo",
    "posting_frequency_per_day": 1.2
  },
  "growth_recommendations": [
    "Great engagement rate! Continue with current strategy",
    "Consider posting more video content for better reach"
  ]
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SMARTPROXY_USERNAME` | Your SmartProxy username | Required |
| `SMARTPROXY_PASSWORD` | Your SmartProxy password | Required |
| `API_HOST` | Server host | `0.0.0.0` |
| `API_PORT` | Server port | `8000` |
| `DEBUG` | Debug mode | `true` |
| `MAX_REQUESTS_PER_HOUR` | Rate limit | `500` |
| `MAX_CONCURRENT_REQUESTS` | Concurrent requests | `5` |

### Rate Limiting

Adjust based on your SmartProxy plan:

```env
# Conservative (starter plans)
MAX_REQUESTS_PER_HOUR=500
MAX_CONCURRENT_REQUESTS=5

# Aggressive (higher tier plans)  
MAX_REQUESTS_PER_HOUR=2000
MAX_CONCURRENT_REQUESTS=20
```

## Usage Examples

### Python Client Example

```python
import httpx
import asyncio

async def analyze_profile():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/instagram/profile/instagram"
        )
        data = response.json()
        
        profile = data["profile"]
        print(f"Username: {profile['username']}")
        print(f"Followers: {profile['followers']:,}")
        print(f"Engagement Rate: {profile['engagement_rate']:.2f}%")

asyncio.run(analyze_profile())
```

### Frontend Integration

```javascript
// React/JavaScript example
const analyzeProfile = async (username) => {
  try {
    const response = await fetch(
      `http://localhost:8000/api/v1/instagram/profile/${username}`
    );
    const data = await response.json();
    
    console.log('Profile Analysis:', data);
    return data;
  } catch (error) {
    console.error('Analysis failed:', error);
  }
};
```

## Error Handling

The API returns structured error responses:

```json
{
  "detail": "SmartProxy Error: Authentication failed - check credentials"
}
```

Common error codes:
- `400`: SmartProxy API errors (auth, rate limits)
- `404`: Profile/hashtag not found
- `422`: Invalid input parameters
- `500`: Server configuration issues

## Development

### Project Structure

```
analyticsfollowingbackend/
├── app/
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── core/
│   │   ├── config.py          # Configuration settings
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── logging_config.py  # Logging setup
│   ├── models/
│   │   └── instagram.py       # Data models
│   └── scrapers/
│       ├── smartproxy_client.py    # SmartProxy API client
│       └── instagram_analyzer.py   # Analysis logic
├── logs/                      # Application logs
├── main.py                    # FastAPI application
├── requirements.txt           # Dependencies
└── .env                      # Environment variables
```

### Adding New Features

1. Define models in `app/models/`
2. Add scraping logic in `app/scrapers/`
3. Create API endpoints in `app/api/routes.py`
4. Update configuration in `app/core/config.py`

## Deployment

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

### Production Considerations

- Use environment variables for sensitive config
- Set up proper logging and monitoring
- Configure reverse proxy (nginx)
- Enable HTTPS
- Set appropriate rate limits

## Troubleshooting

### Common Issues

**Authentication Error:**
```
SmartProxy Error: Authentication failed - check credentials
```
- Verify your SmartProxy username/password in `.env`
- Check your SmartProxy account status and subscription

**Rate Limit Exceeded:**
```
SmartProxy Error: Rate limit exceeded
```
- Reduce `MAX_CONCURRENT_REQUESTS` in config
- Upgrade your SmartProxy plan
- Implement request throttling

**Import Errors:**
```
ModuleNotFoundError: No module named 'pydantic_settings'
```
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version compatibility

### Testing Connection

```python
# Test your SmartProxy setup
import asyncio
from app.scrapers.smartproxy_client import SmartProxyClient

async def test_connection():
    async with SmartProxyClient("username", "password") as client:
        try:
            result = await client.scrape_instagram_profile("instagram")
            print("✅ Connection successful!")
        except Exception as e:
            print(f"❌ Connection failed: {e}")

asyncio.run(test_connection())
```

## Support

For issues related to:
- **SmartProxy API**: Contact SmartProxy support
- **Backend Implementation**: Check logs in `/logs/app.log`
- **Configuration**: Review environment variables and settings

## License

This project is for educational and development purposes. Ensure compliance with Instagram's Terms of Service and SmartProxy's usage policies.# Backend deployment ready
