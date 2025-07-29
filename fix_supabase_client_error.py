"""
Fix Supabase client initialization error
"""
import sys
import os
sys.path.append(os.getcwd())

from app.core.config import settings

def test_supabase_client_creation():
    """Test different ways to create Supabase client"""
    print("TESTING SUPABASE CLIENT CREATION")
    print("=" * 40)
    
    try:
        # Test basic client creation
        print("[TEST] Basic Supabase client creation...")
        from supabase import create_client
        
        # Try the simple way
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        print("[SUCCESS] Basic client creation works")
        
        # Test client functionality
        print("[TEST] Testing client auth functionality...")
        try:
            # Test listing users (requires service role key)
            users = client.auth.admin.list_users()
            print(f"[SUCCESS] Auth admin works - found {len(users)} users")
        except Exception as auth_error:
            print(f"[WARNING] Auth admin failed: {auth_error}")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Supabase client creation failed: {e}")
        return False

def check_supabase_version():
    """Check Supabase version"""
    try:
        import supabase
        print(f"\\nSupabase version: {supabase.__version__}")
    except:
        print("\\nCould not determine Supabase version")

def display_fix_instructions():
    """Display fix instructions"""
    print(f"\\n{'='*50}")
    print("SUPABASE CLIENT FIX")
    print(f"{'='*50}")
    
    print("\\nISSUE:")
    print("- Supabase client failing with 'proxy' parameter error")
    print("- This suggests version compatibility issue")
    
    print("\\nSOLUTION:")
    print("1. Update requirements.txt with specific Supabase version")
    print("2. Remove any proxy configuration from client creation")
    print("3. Use simple client creation method")
    
    print("\\nTEMPORARY FIX:")
    print("The auth service is using basic create_client() which should work")
    print("The error might be coming from somewhere else")
    
    print("\\nNEXT STEPS:")
    print("1. Check if there are multiple places creating Supabase clients")
    print("2. Ensure no proxy parameters are being passed")
    print("3. Update Supabase package if needed")

def main():
    """Main test function"""
    success = test_supabase_client_creation()
    check_supabase_version()
    display_fix_instructions()
    
    if success:
        print("\\n[SUCCESS] Supabase client creation works locally")
        print("The issue might be in the deployment environment")
    else:
        print("\\n[ERROR] Supabase client creation failed")

if __name__ == "__main__":
    main()