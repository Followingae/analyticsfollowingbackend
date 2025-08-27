"""
CDN Configuration Validator
Check if all CDN environment variables are properly set
"""
import os
from dotenv import load_dotenv

load_dotenv()

def check_cdn_config():
    required_vars = {
        'CF_ACCOUNT_ID': '189e3487e64c5c71c8bdae14f475f075',
        'CF_ZONE_ID': '67bd2af60cb3aab769f3035ab0b99288', 
        'CF_API_TOKEN': '2Q84lIQVbEold-9M60A4B15RSW0U2MxmeHyEQ2Me',
        'R2_BUCKET_NAME': 'thumbnails-prod',
        'R2_PUBLIC_BASE': 'https://cdn.following.ae/th',
        'CDN_BASE_URL': 'https://cdn.following.ae'
    }

    print('CDN Environment Variables Status:')
    print('=' * 60)
    
    all_set = True
    for var, expected in required_vars.items():
        actual = os.getenv(var)
        if actual:
            status = '✅ SET'
            if var == 'CF_API_TOKEN':
                print(f'{var}: {status} (***{actual[-4:]})')
            else:
                print(f'{var}: {status}')
                print(f'  Value: {actual}')
        else:
            status = '❌ MISSING'
            print(f'{var}: {status}')
            print(f'  Expected: {expected}')
            all_set = False
        print()
    
    print('=' * 60)
    if all_set:
        print('✅ ALL CDN ENVIRONMENT VARIABLES ARE CONFIGURED!')
    else:
        print('❌ SOME CDN ENVIRONMENT VARIABLES ARE MISSING')
        print('Please add the missing variables to your .env file')
    
    return all_set

if __name__ == "__main__":
    check_cdn_config()