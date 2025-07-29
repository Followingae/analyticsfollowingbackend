"""
Manually confirm the demo user account to bypass email confirmation
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from supabase import create_client
from app.core.config import settings

async def confirm_demo_user():
    """Manually confirm the demo user account"""
    try:
        print("[INIT] Initializing Supabase client...")
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        demo_email = "zzain.ali@outlook.com"
        
        print(f"[AUTH] Checking user status for: {demo_email}")
        
        # Try to get user info from Supabase Auth
        try:
            # Use admin API to get user by email
            users = supabase.auth.admin.list_users()
            demo_user = None
            
            for user in users:
                if user.email == demo_email:
                    demo_user = user
                    break
            
            if demo_user:
                print(f"[SUCCESS] Found user: {demo_user.id}")
                print(f"Email Confirmed: {demo_user.email_confirmed_at is not None}")
                print(f"User Status: {demo_user.email_confirmed_at}")
                
                # If not confirmed, confirm manually
                if not demo_user.email_confirmed_at:
                    print("[ACTION] Confirming user email manually...")
                    
                    # Update user to confirm email
                    update_result = supabase.auth.admin.update_user_by_id(
                        demo_user.id,
                        {"email_confirm": True}
                    )
                    
                    if update_result.user:
                        print("[SUCCESS] User email confirmed manually!")
                        print(f"User can now login with: {demo_email}")
                    else:
                        print("[ERROR] Failed to confirm user email")
                else:
                    print("[INFO] User email already confirmed")
                
                # Display final status
                print("\n" + "=" * 60)
                print("BARAKAT DEMO ACCOUNT - READY FOR LOGIN")
                print("=" * 60)
                print(f"Email: {demo_email}")
                print("Password: BarakatDemo2024!")
                print("Status: Email Confirmed ✓")
                print("Ready for frontend login!")
                print("=" * 60)
                
                return True
            else:
                print(f"[ERROR] User not found: {demo_email}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to check user status: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Confirmation failed: {e}")
        return False

async def main():
    """Main function"""
    result = await confirm_demo_user()
    
    if result:
        print("\n[COMPLETE] Demo user confirmation completed!")
    else:
        print("\n[FAILED] Demo user confirmation failed!")

if __name__ == "__main__":
    asyncio.run(main())