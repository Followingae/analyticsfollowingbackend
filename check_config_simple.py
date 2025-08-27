"""Simple CDN Configuration Check"""
import os
from dotenv import load_dotenv

load_dotenv()

print("CDN Configuration Status:")
print("=" * 50)

vars_to_check = [
    'CF_ACCOUNT_ID',
    'CF_ZONE_ID', 
    'CF_API_TOKEN',
    'R2_BUCKET_NAME',
    'R2_PUBLIC_BASE',
    'CDN_BASE_URL'
]

all_set = True
for var in vars_to_check:
    value = os.getenv(var)
    if value:
        if 'TOKEN' in var:
            print(f"{var}: SET (***{value[-4:]})")
        else:
            print(f"{var}: SET ({value})")
    else:
        print(f"{var}: MISSING")
        all_set = False

print("=" * 50)
if all_set:
    print("SUCCESS: All CDN variables configured!")
else:
    print("WARNING: Some CDN variables missing!")