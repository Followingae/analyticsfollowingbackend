"""
Currency Service - Industry Standard Implementation
Provides centralized currency handling for multi-tenant B2B SaaS platform
"""

from typing import Dict, Optional, Union, Any
from decimal import Decimal
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException
import logging

from app.database.connection import get_db
from app.database.unified_models import (
    TeamCurrencySettings,
    Team,
    TeamMember
)
from app.services.redis_cache_service import redis_cache as cache_manager

logger = logging.getLogger(__name__)

class CurrencyService:
    """
    Industry standard currency service following the currency-per-tenant pattern.
    Used by Stripe, Shopify, Salesforce, and other major B2B SaaS platforms.
    """

    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for currency settings
        self.default_currency = {
            "code": "USD",
            "symbol": "$",
            "decimal_places": 2
        }

    async def get_team_currency(self, team_id: str, db: AsyncSession = None) -> Dict[str, Any]:
        """
        Get currency settings for a specific team.
        Returns cached result for performance.
        """
        if not db:
            async with get_db() as db:
                return await self._get_team_currency_internal(team_id, db)
        return await self._get_team_currency_internal(team_id, db)

    async def _get_team_currency_internal(self, team_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Internal method to get team currency from database."""
        cache_key = f"team_currency:{team_id}"

        # Try cache first
        cached_currency = await cache_manager.get(cache_key)
        if cached_currency:
            return cached_currency

        try:
            # Query team currency settings
            query = select(TeamCurrencySettings).where(
                TeamCurrencySettings.team_id == team_id
            )
            result = await db.execute(query)
            currency_settings = result.scalar_one_or_none()

            if currency_settings:
                currency_data = {
                    "code": currency_settings.currency_code,
                    "symbol": currency_settings.currency_symbol,
                    "decimal_places": currency_settings.decimal_places
                }
            else:
                # Fallback to system default
                currency_data = await self._get_system_default_currency(db)

                # Auto-create currency settings for team
                await self._create_team_currency_settings(team_id, currency_data, db)

            # Cache the result
            await cache_manager.set(cache_key, currency_data, ttl=self.cache_ttl)
            return currency_data

        except Exception as e:
            logger.error(f"Error getting team currency for team {team_id}: {str(e)}")
            return self.default_currency

    async def get_user_currency(self, user_id: str, db: AsyncSession = None) -> Dict[str, Any]:
        """
        Get currency for a user (uses their primary team's currency).
        """
        if not db:
            async with get_db() as db:
                return await self._get_user_currency_internal(user_id, db)
        return await self._get_user_currency_internal(user_id, db)

    async def _get_user_currency_internal(self, user_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Internal method to get user currency via their team."""
        cache_key = f"user_currency:{user_id}"

        # Try cache first
        cached_currency = await cache_manager.get(cache_key)
        if cached_currency:
            return cached_currency

        try:
            # Get user's primary team
            query = select(TeamMember.team_id).where(
                and_(
                    TeamMember.user_id == user_id,
                    TeamMember.status == 'active'
                )
            ).limit(1)

            result = await db.execute(query)
            team_id = result.scalar_one_or_none()

            if team_id:
                currency_data = await self._get_team_currency_internal(str(team_id), db)
            else:
                # User has no team, use system default
                currency_data = await self._get_system_default_currency(db)

            # Cache the result (shorter TTL since team membership can change)
            await cache_manager.set(cache_key, currency_data, ttl=1800)  # 30 minutes
            return currency_data

        except Exception as e:
            logger.error(f"Error getting user currency for user {user_id}: {str(e)}")
            return self.default_currency

    async def update_team_currency(
        self,
        team_id: str,
        currency_code: str,
        currency_symbol: str = None,
        decimal_places: int = 2,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Update currency settings for a team.
        Only superadmins should be able to call this.
        """
        if not db:
            async with get_db() as db:
                return await self._update_team_currency_internal(
                    team_id, currency_code, currency_symbol, decimal_places, db
                )
        return await self._update_team_currency_internal(
            team_id, currency_code, currency_symbol, decimal_places, db
        )

    async def _update_team_currency_internal(
        self,
        team_id: str,
        currency_code: str,
        currency_symbol: str,
        decimal_places: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Internal method to update team currency settings."""
        try:
            # Validate currency code
            if not self._is_valid_currency_code(currency_code):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid currency code: {currency_code}"
                )

            # Set default symbol if not provided
            if not currency_symbol:
                currency_symbol = self._get_currency_symbol(currency_code)

            # Check if settings exist
            query = select(TeamCurrencySettings).where(
                TeamCurrencySettings.team_id == team_id
            )
            result = await db.execute(query)
            existing_settings = result.scalar_one_or_none()

            if existing_settings:
                # Update existing settings
                existing_settings.currency_code = currency_code
                existing_settings.currency_symbol = currency_symbol
                existing_settings.decimal_places = decimal_places
            else:
                # Create new settings
                new_settings = TeamCurrencySettings(
                    team_id=team_id,
                    currency_code=currency_code,
                    currency_symbol=currency_symbol,
                    decimal_places=decimal_places
                )
                db.add(new_settings)

            await db.commit()

            # Clear cache
            cache_key = f"team_currency:{team_id}"
            await cache_manager.delete(cache_key)

            # Clear user currency caches for this team
            await self._clear_team_user_caches(team_id, db)

            return {
                "code": currency_code,
                "symbol": currency_symbol,
                "decimal_places": decimal_places
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating team currency: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to update team currency settings"
            )

    async def format_amount(
        self,
        amount_cents: int,
        currency_info: Dict[str, Any] = None,
        team_id: str = None,
        user_id: str = None
    ) -> str:
        """
        Format an amount in cents to a human-readable currency string.

        Args:
            amount_cents: Amount in cents/smallest currency unit
            currency_info: Optional currency info (if not provided, will fetch)
            team_id: Team ID to get currency for
            user_id: User ID to get currency for (if no team_id)

        Returns:
            Formatted string like "$12.34" or "€15.99"
        """
        if not currency_info:
            if team_id:
                currency_info = await self.get_team_currency(team_id)
            elif user_id:
                currency_info = await self.get_user_currency(user_id)
            else:
                currency_info = self.default_currency

        decimal_places = currency_info.get("decimal_places", 2)
        symbol = currency_info.get("symbol", "$")

        # Convert cents to currency amount
        amount = amount_cents / (10 ** decimal_places)

        # Format with appropriate decimal places
        formatted_amount = f"{amount:.{decimal_places}f}"

        return f"{symbol}{formatted_amount}"

    async def parse_amount(
        self,
        amount_str: str,
        currency_info: Dict[str, Any] = None,
        team_id: str = None,
        user_id: str = None
    ) -> int:
        """
        Parse a currency string to cents/smallest currency unit.

        Args:
            amount_str: String like "$12.34" or "15.99"
            currency_info: Optional currency info
            team_id: Team ID to get currency for
            user_id: User ID to get currency for

        Returns:
            Amount in cents
        """
        if not currency_info:
            if team_id:
                currency_info = await self.get_team_currency(team_id)
            elif user_id:
                currency_info = await self.get_user_currency(user_id)
            else:
                currency_info = self.default_currency

        decimal_places = currency_info.get("decimal_places", 2)
        symbol = currency_info.get("symbol", "$")

        # Remove currency symbol and whitespace
        clean_amount = amount_str.replace(symbol, "").strip()

        try:
            # Convert to decimal and then to cents
            amount_decimal = Decimal(clean_amount)
            amount_cents = int(amount_decimal * (10 ** decimal_places))
            return amount_cents
        except:
            raise ValueError(f"Invalid amount format: {amount_str}")

    async def _get_system_default_currency(self, db: AsyncSession) -> Dict[str, Any]:
        """Get system default currency from configuration."""
        # For now, just return the hardcoded default
        # TODO: Implement system configuration table if needed
        return self.default_currency

    async def _create_team_currency_settings(
        self,
        team_id: str,
        currency_data: Dict[str, Any],
        db: AsyncSession
    ):
        """Auto-create currency settings for a team."""
        try:
            new_settings = TeamCurrencySettings(
                team_id=team_id,
                currency_code=currency_data["code"],
                currency_symbol=currency_data["symbol"],
                decimal_places=currency_data["decimal_places"]
            )
            db.add(new_settings)
            await db.commit()

        except Exception as e:
            logger.error(f"Error creating team currency settings: {str(e)}")
            await db.rollback()

    async def _clear_team_user_caches(self, team_id: str, db: AsyncSession):
        """Clear user currency caches for all members of a team."""
        try:
            # Get all team members
            query = select(TeamMember.user_id).where(
                TeamMember.team_id == team_id
            )
            result = await db.execute(query)
            user_ids = [row[0] for row in result.fetchall()]

            # Clear user currency caches
            for user_id in user_ids:
                cache_key = f"user_currency:{user_id}"
                await cache_manager.delete(cache_key)

        except Exception as e:
            logger.error(f"Error clearing team user caches: {str(e)}")

    def _is_valid_currency_code(self, code: str) -> bool:
        """Validate currency code (basic validation)."""
        if not code or len(code) != 3:
            return False

        # Add more sophisticated validation if needed
        # For now, just check it's 3 uppercase letters
        return code.isalpha() and code.isupper()

    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get default symbol for a currency code."""
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "AED": "د.إ",
            "SAR": "ر.س",
            "JPY": "¥",
            "CNY": "¥",
            "INR": "₹",
            "CAD": "C$",
            "AUD": "A$"
        }
        return currency_symbols.get(currency_code, currency_code)


# Singleton instance
currency_service = CurrencyService()
