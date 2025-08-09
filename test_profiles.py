import asyncio
import httpx
import json

async def test_multiple_profiles():
    profiles = ['karenwazen', 'marrysweet884', 'robinaiyudauthappa', 'shehnai_jewellers', 'ahmed.othman']
    
    # Use the test account
    login_data = {
        'email': 'testuser@example.com',
        'password': 'TestPassword123!'
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Login
            login_response = await client.post(
                'http://localhost:8000/api/v1/auth/login',
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if login_response.status_code != 200:
                print(f'Login failed: {login_response.text}')
                return
            
            token = login_response.json().get('access_token')
            headers = {'Authorization': f'Bearer {token}'}
            
            results = {}
            
            for username in profiles:
                print(f'Fetching profile: {username}')
                
                try:
                    profile_response = await client.get(
                        f'http://localhost:8000/api/v1/instagram/profile/{username}',
                        headers=headers
                    )
                    
                    if profile_response.status_code == 200:
                        profile_data = profile_response.json()
                        results[username] = profile_data
                        
                        # Save individual files
                        with open(f'{username}_data.json', 'w') as f:
                            json.dump(profile_data, f, indent=2)
                        
                        print(f'  ✓ {username}: Success ({profile_data.get("meta", {}).get("posts_stored", 0)} posts stored)')
                    else:
                        print(f'  ✗ {username}: Failed - {profile_response.status_code}')
                        results[username] = {'error': profile_response.text}
                        
                except Exception as e:
                    print(f'  ✗ {username}: Error - {e}')
                    results[username] = {'error': str(e)}
                
                # Wait between requests
                await asyncio.sleep(2)
            
            # Save combined results
            with open('all_profiles_test.json', 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f'\nCompleted testing {len(profiles)} profiles')
            print(f'Success: {sum(1 for r in results.values() if "error" not in r)}')
            print(f'Failed: {sum(1 for r in results.values() if "error" in r)}')
            
            return results
            
    except Exception as e:
        print(f'Error: {e}')
        return None

if __name__ == '__main__':
    asyncio.run(test_multiple_profiles())