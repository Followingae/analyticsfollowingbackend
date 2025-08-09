import asyncio
import httpx
import json
import traceback

async def simple_test():
    try:
        print("Starting simple test...")
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Register
            register_data = {
                'email': 'simpletest@example.com',
                'password': 'TestPassword123!',
                'full_name': 'Simple Test User'
            }
            
            print("Registering user...")
            register_response = await client.post(
                'http://localhost:8000/api/v1/auth/register',
                json=register_data
            )
            print(f'Register status: {register_response.status_code}')
            
            if register_response.status_code != 200:
                print(f'Register failed: {register_response.text}')
                return
            
            # Login
            login_data = {
                'email': 'simpletest@example.com',
                'password': 'TestPassword123!'
            }
            
            print("Logging in...")
            login_response = await client.post(
                'http://localhost:8000/api/v1/auth/login',
                json=login_data
            )
            print(f'Login status: {login_response.status_code}')
            
            if login_response.status_code != 200:
                print(f'Login failed: {login_response.text}')
                return
            
            token = login_response.json().get('access_token')
            print("Got token!")
            
            # Test one profile
            headers = {'Authorization': f'Bearer {token}'}
            print("Fetching karenwazen profile...")
            
            profile_response = await client.get(
                'http://localhost:8000/api/v1/instagram/profile/karenwazen',
                headers=headers
            )
            print(f'Profile status: {profile_response.status_code}')
            
            if profile_response.status_code == 200:
                data = profile_response.json()
                print("SUCCESS! Got profile data")
                with open('simple_test_result.json', 'w') as f:
                    json.dump(data, f, indent=2)
                return data
            else:
                print(f'Profile failed: {profile_response.text}')
                
    except Exception as e:
        print(f'Exception: {e}')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(simple_test())