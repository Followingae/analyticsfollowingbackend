import asyncio
import logging
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.scrapers.enhanced_decodo_client import EnhancedDecodoClient, DecodoAPIError, DecodoInstabilityError

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_enhanced_decodo():
    """Test Enhanced Decodo client with mkbhd"""
    
    print("Testing Enhanced Decodo Client with mkbhd...")
    print("=" * 60)
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        print("Decodo credentials not configured!")
        return
    
    try:
        async with EnhancedDecodoClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as client:
            
            print("1. Testing comprehensive profile analysis...")
            analysis = await client.analyze_profile_comprehensive("mkbhd")
            
            print("\nProfile Analysis Results:")
            print(f"Username: {analysis.profile.username}")
            print(f"Full Name: {analysis.profile.full_name}")
            print(f"Followers: {analysis.profile.followers:,}")
            print(f"Following: {analysis.profile.following:,}")
            print(f"Posts: {analysis.profile.posts_count:,}")
            print(f"Verified: {analysis.profile.is_verified}")
            print(f"Business: {analysis.profile.is_private}")
            print(f"Engagement Rate: {analysis.profile.engagement_rate}%")
            print(f"Influence Score: {analysis.profile.influence_score}/10")
            print(f"Content Quality: {analysis.profile.content_quality_score}/10")
            print(f"Data Quality: {analysis.data_quality_score}")
            print(f"Scraping Method: {analysis.scraping_method}")
            
            print("\nGrowth Recommendations:")
            for i, rec in enumerate(analysis.growth_recommendations, 1):
                print(f"  {i}. {rec}")
            
            print("\nContent Strategy:")
            strategy = analysis.content_strategy
            print(f"  Posting Frequency: {strategy.get('posting_frequency_per_day', 'N/A')} posts/day")
            print(f"  Best Hour: {strategy.get('best_posting_hour', 'N/A')}:00")
            
            print("\nTest completed successfully!")
            
    except (DecodoAPIError, DecodoInstabilityError) as e:
        print(f"Decodo error: {str(e)}")
        logger.error(f"Decodo error during test: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error during test: {str(e)}")

async def test_retry_mechanism():
    """Test the retry mechanism with a potentially unstable request"""
    print("\n" + "=" * 60)
    print("Testing Retry Mechanism...")
    print("=" * 60)
    
    if not settings.SMARTPROXY_USERNAME or not settings.SMARTPROXY_PASSWORD:
        print("Decodo credentials not configured!")
        return
    
    # Test with a few different usernames to see retry behavior
    test_usernames = ["mkbhd", "instagram", "cristiano"]
    
    for username in test_usernames:
        print(f"\nTesting retry mechanism with: {username}")
        try:
            async with EnhancedDecodoClient(
                settings.SMARTPROXY_USERNAME,
                settings.SMARTPROXY_PASSWORD
            ) as client:
                
                raw_data = await client.get_instagram_profile_comprehensive(username)
                profile = client.parse_profile_data(raw_data, username)
                
                print(f"✅ Success: {profile.username} - {profile.followers:,} followers")
                
        except (DecodoAPIError, DecodoInstabilityError) as e:
            print(f"❌ Failed after retries: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_enhanced_decodo())
    asyncio.run(test_retry_mechanism())