import asyncio
import logging
from app.core.logging_config import setup_logging
from app.scrapers.inhouse_scraper import InHouseInstagramScraper

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_inhouse_scraper():
    """Test the in-house Instagram scraper"""
    
    print("🧪 Testing In-house Instagram Scraper...")
    
    try:
        async with InHouseInstagramScraper() as scraper:
            print("\n🔍 Testing profile scraping...")
            
            # Test with a well-known account
            test_username = "instagram"
            print(f"Testing with username: {test_username}")
            
            # Test raw profile scraping
            raw_data = await scraper.scrape_profile(test_username)
            print(f"✅ Raw data extracted!")
            print(f"📊 Raw data keys: {list(raw_data.keys()) if raw_data else 'No data'}")
            
            if raw_data:
                print(f"📈 Sample data:")
                for key, value in list(raw_data.items())[:5]:
                    print(f"  {key}: {str(value)[:100]}")
            
            # Test parsed profile
            profile = scraper._parse_profile_data(raw_data, test_username)
            print(f"\n✅ Profile parsed!")
            print(f"👤 Username: {profile.username}")
            print(f"📝 Full Name: {profile.full_name}")
            print(f"👥 Followers: {profile.followers:,}")
            print(f"📸 Posts: {profile.posts_count}")
            print(f"✓ Verified: {profile.is_verified}")
            
            # Test comprehensive analysis
            print(f"\n🔬 Testing comprehensive analysis...")
            analysis = await scraper.analyze_profile_comprehensive(test_username)
            
            print(f"✅ Comprehensive analysis complete!")
            print(f"📊 Analysis data quality: {analysis.data_quality_score}")
            print(f"💡 Recommendations count: {len(analysis.growth_recommendations)}")
            print(f"📈 Content strategy keys: {list(analysis.content_strategy.keys())}")
            
            # Print some recommendations
            if analysis.growth_recommendations:
                print(f"\n💡 Sample recommendations:")
                for i, rec in enumerate(analysis.growth_recommendations[:3], 1):
                    print(f"  {i}. {rec}")
                    
    except Exception as e:
        logger.exception("Error during testing")
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_inhouse_scraper())