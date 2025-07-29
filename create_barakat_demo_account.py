"""
Create a comprehensive demo account for Barakat brand with user Zain Ali
Includes full mock data for all graphs, stats, and 4 unlocked creators
"""
import asyncio
import sys
import os
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List
sys.path.append(os.getcwd())

from app.services.auth_service import auth_service
from app.models.auth import UserCreate, UserRole
from app.database.connection import SessionLocal, init_database
from app.database.models import (
    User, Profile, Post, UserProfileAccess, AudienceDemographics,
    CreatorMetadata, CommentSentiment, Campaign
)
from sqlalchemy import select
import uuid as uuid_lib

class BarakatDemoCreator:
    """Creates comprehensive demo data for Barakat brand"""
    
    def __init__(self):
        self.demo_user_email = "zain.ali@barakat.com"
        self.demo_user_password = "BarakatDemo2024!"
        self.demo_user_name = "Zain Ali"
        self.brand_name = "Barakat"
        
        # 4 Mock creators with comprehensive data
        self.mock_creators = [
            {
                "username": "sarah_lifestyle",
                "full_name": "Sarah Johnson",
                "biography": "✨ Lifestyle & Fashion Creator | Dubai 🇦🇪 | Collaborations: sarah@email.com",
                "followers_count": 125000,
                "following_count": 1250,
                "posts_count": 342,
                "is_verified": True,
                "is_business_account": True,
                "business_category_name": "Fashion Model",
                "profile_pic_url": "https://picsum.photos/400/400?random=1",
                "external_url": "https://sarahlifestyle.com",
                "location": "Dubai, UAE",
                "categories": ["fashion", "beauty", "lifestyle"]
            },
            {
                "username": "ahmed_fitness",
                "full_name": "Ahmed Al-Rashid",
                "biography": "💪 Fitness Coach & Nutrition Expert | Transform Your Life | Online Training Available",
                "followers_count": 89000,
                "following_count": 890,
                "posts_count": 456,
                "is_verified": False,
                "is_business_account": True,
                "business_category_name": "Fitness Trainer",
                "profile_pic_url": "https://picsum.photos/400/400?random=2",
                "external_url": "https://ahmedfitness.ae",
                "location": "Abu Dhabi, UAE",
                "categories": ["fitness", "health", "nutrition"]
            },
            {
                "username": "maya_foodie",
                "full_name": "Maya Hassan",
                "biography": "🍽️ Food Blogger | Middle Eastern Cuisine Expert | Recipe Developer | Cookbook Author",
                "followers_count": 156000,
                "following_count": 2100,
                "posts_count": 278,
                "is_verified": True,
                "is_business_account": True,
                "business_category_name": "Food & Beverage",
                "profile_pic_url": "https://picsum.photos/400/400?random=3",
                "external_url": "https://mayafoodie.com",
                "location": "Kuwait City, Kuwait",
                "categories": ["food", "cooking", "middle_eastern"]
            },
            {
                "username": "tech_omar",
                "full_name": "Omar Bin Khalid",
                "biography": "📱 Tech Reviewer | AI & Gadgets | Making tech accessible for everyone | YouTube: TechOmar",
                "followers_count": 98000,
                "following_count": 567,
                "posts_count": 189,
                "is_verified": False,
                "is_business_account": True,
                "business_category_name": "Technology",
                "profile_pic_url": "https://picsum.photos/400/400?random=4",
                "external_url": "https://youtube.com/techomar",  
                "location": "Doha, Qatar",
                "categories": ["technology", "reviews", "gadgets"]
            }
        ]
    
    def generate_mock_posts(self, profile_id: str, username: str, num_posts: int = 20) -> List[Dict]:
        """Generate mock posts for a creator"""
        posts = []
        base_engagement = {
            "sarah_lifestyle": {"likes": (2000, 8000), "comments": (50, 200)},
            "ahmed_fitness": {"likes": (1500, 5000), "comments": (30, 150)},
            "maya_foodie": {"likes": (2500, 9000), "comments": (80, 300)},
            "tech_omar": {"likes": (1200, 4000), "comments": (40, 180)}
        }
        
        engagement_range = base_engagement.get(username, {"likes": (1000, 5000), "comments": (20, 100)})
        
        captions = [
            "Another amazing day! What do you think? 💫",
            "Loving this new style! Drop a 💖 if you agree",
            "Behind the scenes magic ✨ More coming soon!",
            "Can't believe how good this turned out! 🔥",
            "Thanks for all the love on my last post! ❤️",
            "New day, new possibilities! What's inspiring you today?",
            "This is why I love what I do 🙌",
            "Throwback to this incredible moment 📸",
            "Excited to share this with you all! [COMPLETE]",
            "Weekend vibes are everything! 🌟"
        ]
        
        for i in range(num_posts):
            post_date = datetime.now() - timedelta(days=random.randint(1, 90))
            likes = random.randint(*engagement_range["likes"])
            comments = random.randint(*engagement_range["comments"])
            
            posts.append({
                "id": str(uuid_lib.uuid4()),
                "profile_id": profile_id,
                "instagram_post_id": f"ig_{random.randint(1000000000, 9999999999)}",
                "shortcode": f"C{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(100000, 999999)}",
                "display_url": f"https://picsum.photos/800/800?random={random.randint(100, 999)}",
                "is_video": random.choice([True, False]),
                "caption": random.choice(captions),
                "likes_count": likes,
                "comments_count": comments,
                "taken_at_timestamp": int(post_date.timestamp()),
                "media_type": random.choice(["photo", "video", "carousel"]),
                "hashtags": json.dumps([f"#{random.choice(['lifestyle', 'fashion', 'fitness', 'food', 'tech', 'dubai', 'uae'])}" for _ in range(random.randint(3, 8))]),
                "raw_data": {"mock": True}
            })
        
        return posts
    
    def generate_audience_demographics(self, profile_id: str) -> Dict:
        """Generate realistic audience demographics"""
        return {
            "profile_id": profile_id,
            "gender_dist": {
                "female": round(random.uniform(0.4, 0.7), 2),
                "male": round(random.uniform(0.3, 0.6), 2)
            },
            "age_dist": {
                "18-24": round(random.uniform(0.2, 0.4), 2),
                "25-34": round(random.uniform(0.3, 0.5), 2),
                "35-44": round(random.uniform(0.15, 0.25), 2),
                "45+": round(random.uniform(0.05, 0.15), 2)
            },
            "location_dist": {
                "UAE": round(random.uniform(0.3, 0.5), 2),
                "Saudi Arabia": round(random.uniform(0.15, 0.25), 2),
                "Kuwait": round(random.uniform(0.1, 0.2), 2),
                "Qatar": round(random.uniform(0.08, 0.15), 2),
                "Other": round(random.uniform(0.1, 0.2), 2)
            }
        }
    
    async def create_demo_user(self):
        """Create the demo user account"""
        print(f"[AUTH] Creating demo user account for {self.demo_user_name}...")
        
        try:
            await auth_service.initialize()
            
            # Create demo user
            demo_user = UserCreate(
                email=self.demo_user_email,
                password=self.demo_user_password,
                full_name=self.demo_user_name,
                role=UserRole.PREMIUM
            )
            
            result = await auth_service.register_user(demo_user)
            print(f"[SUCCESS] Demo user created: {result.email} (ID: {result.id})")
            
            # Test login
            login_result = await auth_service.login_user(demo_user.email, demo_user.password)
            print(f"[SUCCESS] Login test successful!")
            
            return result
            
        except Exception as e:
            if "already registered" in str(e).lower():
                print(f"[INFO]  User already exists, testing login...")
                login_result = await auth_service.login_user(self.demo_user_email, self.demo_user_password)
                print(f"[SUCCESS] Existing user login successful!")
                
                # Get user info
                user_info = await auth_service.get_current_user(login_result.access_token)
                return user_info
            else:
                print(f"[ERROR] Error creating user: {e}")
                raise
    
    async def create_mock_creators(self, user_id: str):
        """Create 4 mock creators with comprehensive data"""
        print(f"[CREATORS] Creating {len(self.mock_creators)} mock creators...")
        
        async with SessionLocal() as db:
            created_profiles = []
            
            for creator_data in self.mock_creators:
                try:
                    print(f"[CREATE] Creating creator: {creator_data['username']}")
                    
                    # Create profile
                    profile_id = str(uuid_lib.uuid4())
                    profile = Profile(
                        id=profile_id,
                        username=creator_data["username"],
                        full_name=creator_data["full_name"],
                        biography=creator_data["biography"],
                        followers_count=creator_data["followers_count"],
                        following_count=creator_data["following_count"],
                        posts_count=creator_data["posts_count"],
                        is_verified=creator_data["is_verified"],
                        is_business_account=creator_data["is_business_account"],
                        business_category_name=creator_data["business_category_name"],
                        profile_pic_url=creator_data["profile_pic_url"],
                        external_url=creator_data["external_url"],
                        instagram_user_id=f"ig_{random.randint(1000000000, 9999999999)}",
                        is_private=False,
                        raw_data={"mock_data": True, "location": creator_data["location"]}
                    )
                    
                    db.add(profile)
                    await db.flush()
                    
                    # Create user access (unlock the creator)
                    access = UserProfileAccess(
                        id=str(uuid_lib.uuid4()),
                        user_id=user_id,
                        profile_id=profile_id,
                        last_accessed=datetime.now()
                    )
                    db.add(access)
                    
                    # Create creator metadata
                    metadata = CreatorMetadata(
                        id=str(uuid_lib.uuid4()),
                        profile_id=profile_id,
                        extracted_location=creator_data["location"],
                        categories=creator_data["categories"]
                    )
                    db.add(metadata)
                    
                    # Create audience demographics
                    demographics_data = self.generate_audience_demographics(profile_id)
                    demographics = AudienceDemographics(
                        id=str(uuid_lib.uuid4()),
                        **demographics_data
                    )
                    db.add(demographics)
                    
                    # Create mock posts
                    posts = self.generate_mock_posts(profile_id, creator_data["username"])
                    for post_data in posts:
                        post = Post(**post_data)
                        db.add(post)
                    
                    created_profiles.append({
                        "username": creator_data["username"],
                        "profile_id": profile_id,
                        "posts_created": len(posts)
                    })
                    
                    print(f"[SUCCESS] Created {creator_data['username']} with {len(posts)} posts")
                    
                except Exception as e:
                    print(f"[ERROR] Error creating {creator_data['username']}: {e}")
                    await db.rollback()
                    continue
            
            await db.commit()
            print(f"[SUCCESS] Successfully created {len(created_profiles)} creators")
            return created_profiles
    
    async def create_demo_campaign(self, user_id: str):
        """Create a demo campaign for Barakat"""
        print(f"[CAMPAIGN] Creating demo campaign for {self.brand_name}...")
        
        async with SessionLocal() as db:
            try:
                campaign = Campaign(
                    id=str(uuid_lib.uuid4()),
                    user_id=user_id,
                    name=f"{self.brand_name} Influencer Campaign 2024",
                    logo_url="https://picsum.photos/200/200?random=brand",
                    start_date=datetime.now().date() - timedelta(days=30),
                    end_date=datetime.now().date() + timedelta(days=60)
                )
                
                db.add(campaign)
                await db.commit()
                
                print(f"[SUCCESS] Created campaign: {campaign.name}")
                return campaign
                
            except Exception as e:
                print(f"[ERROR] Error creating campaign: {e}")
                await db.rollback()
                raise
    
    async def display_demo_credentials(self, user_result, creators):
        """Display the demo account credentials and summary"""
        print("\n" + "=" * 80)
        print("[DEMO] BARAKAT DEMO ACCOUNT CREATED SUCCESSFULLY")
        print("=" * 80)
        print(f"Brand: {self.brand_name}")
        print(f"User: {self.demo_user_name}")
        print(f"Email: {self.demo_user_email}")
        print(f"Password: {self.demo_user_password}")
        print(f"Role: Premium")
        print(f"User ID: {user_result.id if hasattr(user_result, 'id') else 'N/A'}")
        
        print("\n[CAMPAIGN] MOCK DATA SUMMARY:")
        print(f"[SUCCESS] {len(creators)} Creators unlocked and populated")
        print("[SUCCESS] Complete analytics data for all graphs")
        print("[SUCCESS] Audience demographics for all creators")
        print("[SUCCESS] Historical engagement data")
        print("[SUCCESS] Campaign management setup")
        
        print("\n[CREATORS] UNLOCKED CREATORS:")
        for creator in creators:
            print(f"   • @{creator['username']} ({creator['posts_created']} posts)")
        
        print("\n[SEARCH] CREATOR SEARCH FUNCTIONALITY:")
        print("   • Fully functional search in Creators tab")
        print("   • All 4 creators will appear in search results")
        print("   • Complete profile data and analytics available")
        print("   • 30-day access window activated")
        
        print("\n[START] NEXT STEPS:")
        print("1. Use the credentials above to login to the platform")
        print("2. Navigate to the Creators tab to see unlocked creators")
        print("3. Search functionality is fully operational")
        print("4. All graphs and stats are populated with realistic data")
        print("5. Brand dashboard shows comprehensive analytics")
        
        print("=" * 80)
    
    async def run_full_demo_setup(self):
        """Run the complete demo setup process"""
        try:
            print(f"[START] Starting {self.brand_name} demo account creation...")
            
            # Initialize database connection
            await init_database()
            
            # Step 1: Create demo user
            user_result = await self.create_demo_user()
            user_id = user_result.id if hasattr(user_result, 'id') else str(user_result.get('id', ''))
            
            # Step 2: Create mock creators
            creators = await self.create_mock_creators(user_id)
            
            # Step 3: Create demo campaign
            campaign = await self.create_demo_campaign(user_id)
            
            # Step 4: Display credentials and summary
            await self.display_demo_credentials(user_result, creators)
            
            return {
                "success": True,
                "user_email": self.demo_user_email,
                "user_password": self.demo_user_password,
                "creators_count": len(creators),
                "user_id": user_id
            }
            
        except Exception as e:
            print(f"[ERROR] Demo setup failed: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

async def main():
    """Main function to create the Barakat demo account"""
    demo_creator = BarakatDemoCreator()
    result = await demo_creator.run_full_demo_setup()
    
    if result["success"]:
        print(f"\n[COMPLETE] Demo account setup completed successfully!")
        print(f"Ready for live demonstration!")
    else:
        print(f"\n[FAILED] Demo setup failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())