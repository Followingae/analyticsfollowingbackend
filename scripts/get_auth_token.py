"""
Get a valid auth token for testing
"""
import asyncio
import httpx
import json

async def get_auth_token():
    """Get auth token by logging in"""
    async with httpx.AsyncClient() as client:
        # Login request
        response = await client.post(
            "http://localhost:8000/api/v1/auth/login",
            json={
                "email": "zain@following.ae",
                "password": "Following0925_25"
            }
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"Token obtained successfully!")
            print(f"\nToken: {token}")
            print(f"\nUse this command to test HRM endpoints:")
            print(f'curl -X GET "http://localhost:8000/api/v1/hrm/employees" -H "Authorization: Bearer {token}" | python -m json.tool')
            return token
        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            return None

if __name__ == "__main__":
    asyncio.run(get_auth_token())