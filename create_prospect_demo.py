"""
Complete Prospect Brand Demo User Creation
Creates a full-featured demo account for showing to potential brand clients
"""
import asyncio
import asyncpg
import logging
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database and Supabase configuration
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Demo prospect user credentials
PROSPECT_EMAIL = "demo@prospectbrands.com"
PROSPECT_PASSWORD = "ProspectDemo2024!"
PROSPECT_BRAND_NAME = "ProspectBrands"
PROSPECT_FULL_NAME = "Sarah Marketing Manager"

# Mock influencer profiles
MOCK_INFLUENCERS = [
    {
        "username": "lifestyle_emma",
        "full_name": "Emma Rodriguez",
        "biography": "Lifestyle & Fashion Influencer | Dubai Based | Brand Collaborations: emma@lifestyle.ae",
        "followers_count": 245000,
        "following_count": 1850,
        "posts_count": 892,
        "is_verified": True,
        "is_business_account": True,
        "profile_pic_url": "https://picsum.photos/400/400?random=101",
        "external_url": "https://emmalifestyle.com",
        "business_category_name": "Lifestyle",
        "location": "Dubai, UAE",
        "engagement_rate": 4.8,
        "categories": ["lifestyle", "fashion", "beauty"],
        "posts": [
            {"likes": 12500, "comments": 340, "caption": "New collection drop! 🌟 Loving these summer pieces", "date_days_ago": 1},
            {"likes": 8900, "comments": 256, "caption": "Weekend vibes in Dubai Marina ✨", "date_days_ago": 3},
            {"likes": 15600, "comments": 423, "caption": "Behind the scenes of today's photoshoot 📸", "date_days_ago": 5},
            {"likes": 9800, "comments": 198, "caption": "Morning skincare routine that changed my life!", "date_days_ago": 7},
            {"likes": 11300, "comments": 287, "caption": "Exploring hidden gems in Old Dubai 🏛️", "date_days_ago": 10}
        ]
    },
    {
        "username": "fitness_ahmed",
        "full_name": "Ahmed Al-Mansouri",
        "biography": "Certified Personal Trainer | Nutrition Coach | Transform Your Life 💪 | Online Programs Available",
        "followers_count": 187000,
        "following_count": 943,
        "posts_count": 1247,
        "is_verified": False,
        "is_business_account": True,
        "profile_pic_url": "https://picsum.photos/400/400?random=102",
        "external_url": "https://ahmedfitness.ae",
        "business_category_name": "Health & Fitness",
        "location": "Abu Dhabi, UAE",
        "engagement_rate": 6.2,
        "categories": ["fitness", "health", "nutrition"],
        "posts": [
            {"likes": 18400, "comments": 567, "caption": "5 exercises that will transform your core! Save this post 💪", "date_days_ago": 2},
            {"likes": 13200, "comments": 389, "caption": "Pre-workout meal prep ideas for busy professionals", "date_days_ago": 4},
            {"likes": 21000, "comments": 678, "caption": "Client transformation Tuesday! 6 months of dedication 🔥", "date_days_ago": 6},
            {"likes": 9500, "comments": 234, "caption": "Morning workout motivation - let's crush this day!", "date_days_ago": 8},
            {"likes": 16800, "comments": 445, "caption": "Myth busting: 5 fitness facts you need to know", "date_days_ago": 12}
        ]
    },
    {
        "username": "food_maya",
        "full_name": "Maya Hassan",
        "biography": "Food Blogger & Recipe Developer | Middle Eastern Cuisine Expert | Cookbook Author 📚 | maya@foodiejourney.com",
        "followers_count": 156000,
        "following_count": 2100,
        "posts_count": 743,
        "is_verified": True,
        "is_business_account": True,
        "profile_pic_url": "https://picsum.photos/400/400?random=103",
        "external_url": "https://mayafoodie.com",
        "business_category_name": "Food & Beverage",
        "location": "Kuwait City, Kuwait",
        "engagement_rate": 5.9,
        "categories": ["food", "cooking", "middle_eastern"],
        "posts": [
            {"likes": 14200, "comments": 389, "caption": "Traditional Mansaf recipe passed down 3 generations 🍽️", "date_days_ago": 1},
            {"likes": 11800, "comments": 298, "caption": "Behind the scenes of my cookbook photoshoot 📸", "date_days_ago": 4},
            {"likes": 19500, "comments": 534, "caption": "5-ingredient Kunafa that will blow your mind! Recipe in bio", "date_days_ago": 6},
            {"likes": 8900, "comments": 156, "caption": "Spice market adventures in Kuwait's Souq Al-Mubarakiya", "date_days_ago": 9},
            {"likes": 13600, "comments": 367, "caption": "Ramadan prep: Make-ahead Iftar recipes", "date_days_ago": 14}
        ]
    }
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProspectDemoCreator:
    def __init__(self):
        self.db_conn = None
        self.supabase = None
        
    async def initialize(self):
        """Initialize database and Supabase connections"""
        try:
            # Database connection
            self.db_conn = await asyncpg.connect(DATABASE_URL)
            logger.info("[SUCCESS] Connected to database")
            
            # Supabase connection
            from supabase import create_client
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("[SUCCESS] Connected to Supabase")
            
            return True
        except Exception as e:
            logger.error(f"[ERROR] Initialization failed: {e}")
            return False
    
    async def create_prospect_user(self) -> str:
        """Create prospect brand demo user in Supabase Auth"""
        try:
            logger.info(f"[USER] Creating prospect demo user: {PROSPECT_EMAIL}")
            
            # Delete existing user if exists
            try:
                users = self.supabase.auth.admin.list_users()
                for user in users:
                    if user.email == PROSPECT_EMAIL:
                        self.supabase.auth.admin.delete_user(user.id)
                        logger.info(f"[DELETE] Removed existing user: {PROSPECT_EMAIL}")
            except Exception as e:
                logger.warning(f"[WARNING] User cleanup: {e}")
            
            # Create new prospect user
            result = self.supabase.auth.admin.create_user({
                "email": PROSPECT_EMAIL,
                "password": PROSPECT_PASSWORD,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": PROSPECT_FULL_NAME,
                    "role": "premium",
                    "company": PROSPECT_BRAND_NAME
                }
            })
            
            if result.user:
                user_id = result.user.id
                logger.info(f"[SUCCESS] Created Supabase user: {user_id}")
                
                # Create user in database
                await self.db_conn.execute("""
                    INSERT INTO users (
                        id, email, hashed_password, role, credits, full_name, 
                        status, supabase_user_id, last_login, created_at
                    ) VALUES (
                        $1::uuid, $2, 'supabase_managed', 'premium', 5000, $3,
                        'active', $4, NOW(), NOW()
                    ) ON CONFLICT (email) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        status = 'active',
                        supabase_user_id = EXCLUDED.supabase_user_id,
                        role = 'premium',
                        credits = 5000,
                        last_login = NOW()
                """, user_id, PROSPECT_EMAIL, PROSPECT_FULL_NAME, user_id)
                
                logger.info(f"[SUCCESS] Created database user: {PROSPECT_EMAIL}")
                return user_id
            else:
                logger.error("[ERROR] Failed to create Supabase user")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] User creation failed: {e}")
            return None
    
    async def create_mock_influencers(self, user_id: str) -> List[str]:
        """Create 3 complete mock influencer profiles"""
        created_profiles = []
        
        for influencer in MOCK_INFLUENCERS:
            try:
                logger.info(f"[CREATOR] Creating influencer: {influencer['username']}")
                
                profile_id = str(uuid.uuid4())
                
                # Create profile with complete data
                await self.db_conn.execute("""
                    INSERT INTO profiles (
                        id, username, full_name, biography, instagram_user_id,
                        followers_count, following_count, posts_count,
                        is_verified, is_private, is_business_account,
                        profile_pic_url, external_url, business_category_name,
                        overall_category_name, engagement_rate,
                        raw_data, data_quality_score, last_refreshed
                    ) VALUES (
                        $1::uuid, $2, $3, $4, $5,
                        $6, $7, $8,
                        $9, false, $10,
                        $11, $12, $13,
                        $14, $15,
                        $16::jsonb, 100, NOW()
                    )
                """, 
                    profile_id, influencer['username'], influencer['full_name'],
                    influencer['biography'], f"ig_{random.randint(1000000, 9999999)}",
                    influencer['followers_count'], influencer['following_count'], influencer['posts_count'],
                    influencer['is_verified'], influencer['is_business_account'],
                    influencer['profile_pic_url'], influencer['external_url'], influencer['business_category_name'],
                    influencer['business_category_name'], int(influencer['engagement_rate'] * 100),
                    json.dumps({"mock_data": True, "location": influencer['location']}))
                
                # Create user access (unlock this influencer for the prospect)
                await self.db_conn.execute("""
                    INSERT INTO user_profile_access (id, user_id, profile_id, last_accessed)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, NOW())
                    ON CONFLICT (user_id, profile_id) DO UPDATE SET last_accessed = NOW()
                """, str(uuid.uuid4()), user_id, profile_id)
                
                # Create audience demographics
                await self.create_audience_demographics(profile_id)
                
                # Create creator metadata
                await self.create_creator_metadata(profile_id, influencer)
                
                # Create posts with engagement data
                await self.create_posts(profile_id, influencer)
                
                created_profiles.append(profile_id)
                logger.info(f"[SUCCESS] Created complete profile: {influencer['username']}")
                
            except Exception as e:
                logger.error(f"[ERROR] Failed to create {influencer['username']}: {e}")
        
        return created_profiles
    
    async def create_audience_demographics(self, profile_id: str):
        """Create realistic audience demographics"""
        demographics_data = {
            "gender_dist": {"male": 0.35, "female": 0.65},
            "age_dist": {
                "13-17": 0.08,
                "18-24": 0.32,
                "25-34": 0.41,
                "35-44": 0.15,
                "45-54": 0.04
            },
            "location_dist": {
                "United Arab Emirates": 0.28,
                "Saudi Arabia": 0.22,
                "Kuwait": 0.15,
                "Qatar": 0.12,
                "Bahrain": 0.08,
                "Oman": 0.07,
                "Other": 0.08
            }
        }
        
        await self.db_conn.execute("""
            INSERT INTO audience_demographics (
                id, profile_id, gender_dist, age_dist, location_dist, last_sampled
            ) VALUES (
                $1::uuid, $2::uuid, $3::jsonb, $4::jsonb, $5::jsonb, NOW()
            )
        """, str(uuid.uuid4()), profile_id,
             json.dumps(demographics_data["gender_dist"]),
             json.dumps(demographics_data["age_dist"]),
             json.dumps(demographics_data["location_dist"]))
    
    async def create_creator_metadata(self, profile_id: str, influencer: Dict):
        """Create creator metadata"""
        await self.db_conn.execute("""
            INSERT INTO creator_metadata (
                id, profile_id, extracted_location, categories, last_updated
            ) VALUES (
                $1::uuid, $2::uuid, $3, $4, NOW()
            )
        """, str(uuid.uuid4()), profile_id,
             influencer['location'], influencer['categories'])
    
    async def create_posts(self, profile_id: str, influencer: Dict):
        """Create posts with realistic engagement data"""
        for i, post_data in enumerate(influencer['posts']):
            post_date = datetime.now() - timedelta(days=post_data['date_days_ago'])
            
            post_id = str(uuid.uuid4())
            shortcode = f"{influencer['username']}_post_{i+1}"
            
            # Calculate engagement rate
            total_engagement = post_data['likes'] + post_data['comments']
            engagement_rate = int((total_engagement / influencer['followers_count']) * 10000)  # Basis points
            
            # Check if posts table has the required columns, create basic post
            try:
                await self.db_conn.execute("""
                    INSERT INTO posts (
                        id, profile_id, shortcode,
                        display_url, is_video, likes_count, comments_count,
                        caption, taken_at_timestamp, typename, media_type,
                        engagement_rate, performance_score,
                        raw_data, created_at
                    ) VALUES (
                        $1::uuid, $2::uuid, $3,
                        $4, $5, $6, $7,
                        $8, $9, 'GraphImage', 'photo',
                        $10, $11,
                        $12::jsonb, $13
                    )
                """, 
                    post_id, profile_id, shortcode,
                    f"https://picsum.photos/600/600?random={i+200}", False,
                    post_data['likes'], post_data['comments'],
                    post_data['caption'], int(post_date.timestamp()),
                    engagement_rate, random.randint(75, 95),
                    json.dumps({"mock_data": True}), post_date)
            except Exception as post_error:
                logger.warning(f"[WARNING] Could not create post: {post_error}")
                continue
            
            # Create comment sentiment
            sentiment_data = {
                "positive": round(random.uniform(0.7, 0.85), 2),
                "neutral": round(random.uniform(0.10, 0.20), 2),
                "negative": round(random.uniform(0.05, 0.15), 2)
            }
            
            await self.db_conn.execute("""
                INSERT INTO comment_sentiment (
                    id, post_id, sentiment, calculated_at
                ) VALUES (
                    $1::uuid, $2::uuid, $3::jsonb, NOW()
                )
            """, str(uuid.uuid4()), post_id, json.dumps(sentiment_data))
    
    async def create_dashboard_analytics(self, user_id: str, profile_ids: List[str]):
        """Create comprehensive dashboard analytics data"""
        try:
            # Create search history for realistic usage
            search_terms = [
                "lifestyle influencer dubai",
                "fitness coach uae",
                "food blogger kuwait",
                "fashion influencer",
                "health and wellness",
                "middle eastern food",
                "dubai lifestyle",
                "fitness transformation"
            ]
            
            # Create realistic search history over past 30 days
            for i, term in enumerate(search_terms):
                search_date = datetime.now() - timedelta(days=random.randint(1, 30))
                profile_searched = random.choice(profile_ids) if profile_ids else None
                
                if profile_searched:
                    # Get profile username for search
                    username_result = await self.db_conn.fetchval(
                        "SELECT username FROM profiles WHERE id = $1", profile_searched
                    )
                    
                    search_id = str(uuid.uuid4())
                    await self.db_conn.execute("""
                        INSERT INTO user_searches (
                            id, user_id, instagram_username, search_timestamp,
                            analysis_type, search_metadata
                        ) VALUES (
                            $1::uuid, $2::uuid, $3, $4,
                            'profile_analysis', $5::jsonb
                        )
                    """, search_id, user_id, username_result, search_date,
                         json.dumps({"search_term": term, "mock_data": True}))
            
            logger.info(f"[SUCCESS] Created {len(search_terms)} search history entries")
            
        except Exception as e:
            logger.error(f"[ERROR] Dashboard analytics creation failed: {e}")
    
    async def test_authentication(self) -> bool:
        """Test the created user can authenticate"""
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/auth/login",
                    json={
                        "email": PROSPECT_EMAIL,
                        "password": PROSPECT_PASSWORD
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[SUCCESS] Authentication test passed!")
                    logger.info(f"[SUCCESS] User: {data.get('user', {}).get('email')}")
                    logger.info(f"[SUCCESS] Role: {data.get('user', {}).get('role')}")
                    return True
                else:
                    logger.error(f"[ERROR] Authentication failed: {response.status_code}")
                    logger.error(f"[ERROR] Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"[ERROR] Authentication test failed: {e}")
            return False
    
    async def cleanup(self):
        """Close connections"""
        if self.db_conn:
            await self.db_conn.close()

async def main():
    """Create complete prospect demo"""
    print("[START] CREATING PROSPECT BRAND DEMO")
    print("=" * 60)
    print(f"Demo User: {PROSPECT_EMAIL}")
    print(f"Brand Name: {PROSPECT_BRAND_NAME}")
    print(f"Contact: {PROSPECT_FULL_NAME}")
    print("=" * 60)
    
    creator = ProspectDemoCreator()
    
    try:
        # Initialize connections
        if not await creator.initialize():
            print("[ERROR] Failed to initialize connections")
            return
        
        # Create prospect user
        user_id = await creator.create_prospect_user()
        if not user_id:
            print("[ERROR] Failed to create prospect user")
            return
        
        # Create mock influencers
        print(f"\n[CREATORS] Creating {len(MOCK_INFLUENCERS)} complete influencer profiles...")
        profile_ids = await creator.create_mock_influencers(user_id)
        print(f"[SUCCESS] Created {len(profile_ids)} influencer profiles")
        
        # Create dashboard analytics
        print("\n[ANALYTICS] Creating dashboard analytics data...")
        await creator.create_dashboard_analytics(user_id, profile_ids)
        
        # Test authentication
        print("\n[TEST] Testing authentication...")
        auth_success = await creator.test_authentication()
        
        # Final summary
        print("\n" + "=" * 60)
        print("[COMPLETE] PROSPECT DEMO CREATED SUCCESSFULLY!")
        print("=" * 60)
        
        print(f"\n[CREDENTIALS] LOGIN DETAILS:")
        print(f"Email: {PROSPECT_EMAIL}")
        print(f"Password: {PROSPECT_PASSWORD}")
        print(f"Brand: {PROSPECT_BRAND_NAME}")
        print(f"Contact: {PROSPECT_FULL_NAME}")
        
        print(f"\n[FEATURES] DEMO INCLUDES:")
        print(f"• Premium account with 5,000 credits")
        print(f"• {len(profile_ids)} fully unlocked influencers with 100% data")
        print(f"• Complete audience demographics and analytics")
        print(f"• Realistic engagement data and post history")
        print(f"• Functioning creator search and discovery")
        print(f"• Dashboard with usage analytics")
        
        print(f"\n[INFLUENCERS] UNLOCKED CREATORS:")
        for influencer in MOCK_INFLUENCERS:
            print(f"• {influencer['username']} - {influencer['full_name']}")
            print(f"  {influencer['followers_count']:,} followers | {influencer['engagement_rate']}% engagement")
            print(f"  Categories: {', '.join(influencer['categories'])}")
        
        print(f"\n[ENDPOINT] API LOGIN:")
        print("https://analytics-following-backend-5qfwj.ondigitalocean.app/api/v1/auth/login")
        
        if auth_success:
            print(f"\n[READY] Demo is fully functional and ready for prospects!")
        else:
            print(f"\n[WARNING] Demo created but authentication needs verification")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Demo creation failed: {e}")
    finally:
        await creator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())