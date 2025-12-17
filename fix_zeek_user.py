"""
Fix script to add missing team, membership, and wallet for zeek@testing.com
"""
import asyncio
import uuid
from sqlalchemy import select, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.database.unified_models import User, Team, TeamMember, CreditWallet
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_zeek_user():
    # Create async engine directly
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(DATABASE_URL, echo=False)

    async with AsyncSession(engine) as db:
        try:
            # Find zeek@testing.com user
            result = await db.execute(
                select(User).where(User.email == "zeek@testing.com")
            )
            user = result.scalar_one_or_none()

            if not user:
                print("[ERROR] User zeek@testing.com not found!")
                return

            print(f"[SUCCESS] Found user: {user.email}")
            print(f"   ID: {user.id}")
            print(f"   Supabase ID: {user.supabase_user_id}")
            print(f"   Role: {user.role}")

            # Check if team already exists
            team_result = await db.execute(
                select(TeamMember).where(TeamMember.user_id == user.id)
            )
            existing_team = team_result.scalar_one_or_none()

            if existing_team:
                print("[WARNING] User already has a team membership!")
                return

            # Create team for the user (Standard tier based on logs)
            team = Team(
                id=uuid.uuid4(),
                name="Zeek's Team",
                subscription_tier='standard',  # User signed up with standard plan
                max_team_members=2,
                monthly_profile_limit=500,
                monthly_email_limit=250,
                monthly_posts_limit=125
            )
            db.add(team)
            print(f"[SUCCESS] Created team: {team.name} (standard tier)")

            # Add user as team owner - use Supabase user ID
            team_member = TeamMember(
                id=uuid.uuid4(),
                team_id=team.id,
                user_id=user.supabase_user_id,  # Use Supabase ID instead
                role='owner',
                status='active'
            )
            db.add(team_member)
            print("[SUCCESS] Added user as team owner")

            # Check if wallet already exists
            wallet_result = await db.execute(
                select(CreditWallet).where(CreditWallet.user_id == user.supabase_user_id)
            )
            existing_wallet = wallet_result.scalar_one_or_none()

            if existing_wallet:
                print(f"[WARNING] User already has a wallet with {existing_wallet.current_balance} credits")
            else:
                # Create credit wallet with standard tier credits
                from datetime import datetime, timedelta
                now = datetime.utcnow()
                end_of_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

                wallet = CreditWallet(
                    user_id=user.supabase_user_id,  # Use Supabase ID for wallet
                    current_balance=2000,  # Standard tier gets 2000 credits
                    lifetime_earned=2000,
                    lifetime_spent=0,
                    total_earned_this_cycle=2000,
                    total_spent_this_cycle=0,
                    current_billing_cycle_start=now,
                    current_billing_cycle_end=end_of_month
                )
                db.add(wallet)
                print("[SUCCESS] Created credit wallet with 2000 credits")

            # Commit all changes
            await db.commit()
            print("\n[COMPLETE] Successfully fixed zeek@testing.com!")
            print("   - Team created: Zeek's Team (standard)")
            print("   - Team membership: owner")
            print("   - Credit wallet: 2000 credits")
            print("\n[SUCCESS] User can now login and access all features!")

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(fix_zeek_user())