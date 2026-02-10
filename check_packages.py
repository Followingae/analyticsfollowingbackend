import asyncio
from app.database.connection import get_session
from sqlalchemy import text

async def check_packages():
    async with get_session() as db:
        # Check credit packages
        result = await db.execute(text("SELECT * FROM credit_packages ORDER BY id"))
        packages = result.fetchall()

        print("Credit Packages:")
        for p in packages:
            print(f"  ID: {p.id}, Name: {p.name}, Credits: {p.credits_per_month}, Price: ${p.price_usd}")

        # Check user roles and subscription tiers
        result = await db.execute(text("""
            SELECT role, subscription_tier, COUNT(*) as count
            FROM users
            GROUP BY role, subscription_tier
        """))
        users = result.fetchall()

        print("\nUser Distribution:")
        for u in users:
            print(f"  Role: {u.role}, Tier: {u.subscription_tier}, Count: {u.count}")

if __name__ == "__main__":
    asyncio.run(check_packages())