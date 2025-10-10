"""
Credit Pricing Service - Pricing rules and cost calculations
Manages credit costs for different actions and handles free allowances
"""
import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text

from app.database.connection import get_session
from app.database.unified_models import (
    CreditPricingRule, CreditUsageTracking, CreditPackage
)
from app.models.credits import (
    CreditPricingRule as CreditPricingRuleModel,
    CreditPricingRuleCreate, CreditPricingRuleUpdate
)
from app.cache.redis_cache_manager import cache_manager
from app.core.exceptions import ValidationError
from app.models.teams import ACTION_CREDIT_COSTS, CREDIT_TOPUP_PACKAGES

logger = logging.getLogger(__name__)


class CreditPricingService:
    """
    Comprehensive credit pricing management service
    Handles pricing rules, free allowances, and cost calculations
    """
    
    def __init__(self):
        self.cache_prefix = "credit_pricing"
        self.rules_cache_ttl = 3600  # 1 hour
        self.allowance_cache_ttl = 1800  # 30 minutes
    
    # =========================================================================
    # PRICING RULES MANAGEMENT
    # =========================================================================
    
    async def get_all_pricing_rules(self, include_inactive: bool = False) -> List[CreditPricingRuleModel]:
        """Get all pricing rules with caching"""
        cache_key = f"{self.cache_prefix}:all_rules:{include_inactive}"
        
        # Try cache first (with graceful Redis fallback)
        cached_data = None
        try:
            if cache_manager.redis_client:
                cached_data = await cache_manager.redis_client.get(cache_key)
            else:
                # Initialize cache manager if not already done
                await cache_manager.initialize()
                if cache_manager.redis_client:
                    cached_data = await cache_manager.redis_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache unavailable for all pricing rules: {e}")
            cached_data = None
            
        if cached_data:
            import json
            cached_rules = json.loads(cached_data)
            return [CreditPricingRuleModel(**rule) for rule in cached_rules]
        
        try:
            async with get_session() as session:
                query = select(CreditPricingRule)
                
                if not include_inactive:
                    query = query.where(CreditPricingRule.is_active == True)
                
                query = query.order_by(CreditPricingRule.action_type)
                
                result = await session.execute(query)
                rules = result.scalars().all()
                
                # Convert to Pydantic models
                rule_models = [
                    CreditPricingRuleModel(
                        id=rule.id,
                        action_type=rule.action_type,
                        display_name=rule.display_name,
                        cost_per_action=rule.cost_per_action,
                        free_allowance_per_month=rule.free_allowance_per_month,
                        description=rule.description,
                        is_active=rule.is_active,
                        created_at=rule.created_at,
                        updated_at=rule.updated_at
                    )
                    for rule in rules
                ]
                
                # Cache the results (with graceful Redis fallback)
                try:
                    if cache_manager.redis_client:
                        import json
                        cache_data = [rule.dict() for rule in rule_models]
                        await cache_manager.redis_client.setex(
                            cache_key, 
                            self.rules_cache_ttl, 
                            json.dumps(cache_data, default=str)
                        )
                except Exception as e:
                    logger.warning(f"Failed to cache all pricing rules: {e}")
                
                return rule_models
                
        except Exception as e:
            logger.error(f"Error getting pricing rules: {e}")
            return []
    
    async def get_pricing_rule(self, action_type: str) -> Optional[CreditPricingRuleModel]:
        """Get pricing rule for specific action type"""
        cache_key = f"{self.cache_prefix}:rule:{action_type}"
        
        # Try cache first (with graceful Redis fallback)
        cached_data = None
        try:
            if cache_manager.redis_client:
                cached_data = await cache_manager.redis_client.get(cache_key)
            else:
                # Initialize cache manager if not already done
                await cache_manager.initialize()
                if cache_manager.redis_client:
                    cached_data = await cache_manager.redis_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache unavailable for pricing rule {action_type}: {e}")
            cached_data = None
        
        if cached_data:
            import json
            cached_rule = json.loads(cached_data)
            return CreditPricingRuleModel(**cached_rule)
        
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CreditPricingRule)
                    .where(
                        and_(
                            CreditPricingRule.action_type == action_type,
                            CreditPricingRule.is_active == True
                        )
                    )
                )
                
                rule = result.scalar_one_or_none()
                if not rule:
                    return None
                
                rule_model = CreditPricingRuleModel(
                    id=rule.id,
                    action_type=rule.action_type,
                    display_name=rule.display_name,
                    cost_per_action=rule.cost_per_action,
                    free_allowance_per_month=rule.free_allowance_per_month,
                    description=rule.description,
                    is_active=rule.is_active,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at
                )
                
                # Cache the rule (with graceful Redis fallback)
                try:
                    if cache_manager.redis_client:
                        import json
                        await cache_manager.redis_client.setex(
                            cache_key, 
                            self.rules_cache_ttl, 
                            json.dumps(rule_model.dict(), default=str)
                        )
                except Exception as e:
                    logger.warning(f"Failed to cache pricing rule {action_type}: {e}")
                
                return rule_model
                
        except Exception as e:
            logger.error(f"Error getting pricing rule for action '{action_type}': {e}")
            return None
    
    async def create_pricing_rule(
        self, 
        rule_data: CreditPricingRuleCreate
    ) -> CreditPricingRuleModel:
        """Create new pricing rule"""
        try:
            async with get_session() as session:
                # Check if action type already exists
                existing = await session.execute(
                    select(CreditPricingRule)
                    .where(CreditPricingRule.action_type == rule_data.action_type)
                )
                
                if existing.scalar_one_or_none():
                    raise ValidationError(f"Pricing rule for action '{rule_data.action_type}' already exists")
                
                # Create new rule
                rule = CreditPricingRule(
                    action_type=rule_data.action_type,
                    display_name=rule_data.display_name,
                    cost_per_action=rule_data.cost_per_action,
                    free_allowance_per_month=rule_data.free_allowance_per_month,
                    description=rule_data.description,
                    is_active=rule_data.is_active
                )
                
                session.add(rule)
                await session.commit()
                await session.refresh(rule)
                
                # Clear cache
                await self._clear_pricing_cache()
                
                logger.info(f"Created pricing rule for action '{rule_data.action_type}'")
                
                return CreditPricingRuleModel(
                    id=rule.id,
                    action_type=rule.action_type,
                    display_name=rule.display_name,
                    cost_per_action=rule.cost_per_action,
                    free_allowance_per_month=rule.free_allowance_per_month,
                    description=rule.description,
                    is_active=rule.is_active,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at
                )
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating pricing rule: {e}")
            raise
    
    async def update_pricing_rule(
        self,
        action_type: str,
        update_data: CreditPricingRuleUpdate
    ) -> Optional[CreditPricingRuleModel]:
        """Update existing pricing rule"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CreditPricingRule)
                    .where(CreditPricingRule.action_type == action_type)
                )
                
                rule = result.scalar_one_or_none()
                if not rule:
                    return None
                
                # Apply updates
                update_dict = update_data.dict(exclude_unset=True)
                for field, value in update_dict.items():
                    setattr(rule, field, value)
                
                await session.commit()
                await session.refresh(rule)
                
                # Clear cache
                await self._clear_pricing_cache()
                
                logger.info(f"Updated pricing rule for action '{action_type}': {update_dict}")
                
                return CreditPricingRuleModel(
                    id=rule.id,
                    action_type=rule.action_type,
                    display_name=rule.display_name,
                    cost_per_action=rule.cost_per_action,
                    free_allowance_per_month=rule.free_allowance_per_month,
                    description=rule.description,
                    is_active=rule.is_active,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at
                )
                
        except Exception as e:
            logger.error(f"Error updating pricing rule for action '{action_type}': {e}")
            raise
    
    # =========================================================================
    # COST CALCULATIONS
    # =========================================================================
    
    async def get_action_cost(
        self,
        action_type: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Get cost information for an action
        
        Args:
            action_type: Action type to price
            quantity: Number of actions (for bulk pricing)
            
        Returns:
            Dictionary with cost information
        """
        rule = await self.get_pricing_rule(action_type)
        if not rule:
            return {
                "action_type": action_type,
                "cost_per_action": 0,
                "total_cost": 0,
                "free_allowance": 0,
                "error": "Action type not found"
            }
        
        total_cost = rule.cost_per_action * quantity
        
        return {
            "action_type": action_type,
            "display_name": rule.display_name,
            "cost_per_action": rule.cost_per_action,
            "quantity": quantity,
            "total_cost": total_cost,
            "free_allowance_per_month": rule.free_allowance_per_month,
            "description": rule.description
        }
    
    async def calculate_required_credits(
        self,
        user_id: UUID,
        action_type: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate credits required considering free allowances
        
        Args:
            user_id: User UUID
            action_type: Action type
            quantity: Number of actions
            
        Returns:
            Dictionary with credit calculation
        """
        # Get pricing rule
        rule = await self.get_pricing_rule(action_type)
        if not rule:
            return {
                "error": f"No pricing rule found for action '{action_type}'",
                "credits_required": 0
            }
        
        # Get user's current month usage
        current_month = date.today().replace(day=1)
        free_used = await self.get_free_allowance_used(user_id, action_type, current_month)
        
        # Calculate free actions available
        free_remaining = max(0, rule.free_allowance_per_month - free_used)
        free_actions_for_request = min(quantity, free_remaining)
        paid_actions_needed = quantity - free_actions_for_request
        
        credits_required = paid_actions_needed * rule.cost_per_action
        
        return {
            "action_type": action_type,
            "quantity": quantity,
            "cost_per_action": rule.cost_per_action,
            "free_allowance_per_month": rule.free_allowance_per_month,
            "free_used_this_month": free_used,
            "free_remaining": free_remaining,
            "free_actions_for_request": free_actions_for_request,
            "paid_actions_needed": paid_actions_needed,
            "credits_required": credits_required,
            "will_use_free_allowance": free_actions_for_request > 0
        }
    
    async def get_bulk_pricing(
        self,
        action_costs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate bulk pricing for multiple actions
        
        Args:
            action_costs: List of {action_type: str, quantity: int}
            
        Returns:
            Dictionary with bulk pricing breakdown
        """
        total_cost = 0
        actions_breakdown = []
        
        for action_data in action_costs:
            action_type = action_data["action_type"]
            quantity = action_data.get("quantity", 1)
            
            cost_info = await self.get_action_cost(action_type, quantity)
            actions_breakdown.append(cost_info)
            total_cost += cost_info.get("total_cost", 0)
        
        return {
            "actions_breakdown": actions_breakdown,
            "total_cost": total_cost,
            "action_count": len(actions_breakdown),
            "total_quantity": sum(action.get("quantity", 0) for action in actions_breakdown)
        }
    
    # =========================================================================
    # FREE ALLOWANCE MANAGEMENT
    # =========================================================================
    
    async def get_free_allowance_used(
        self,
        user_id: UUID,
        action_type: str,
        month_year: Optional[date] = None
    ) -> int:
        """Get number of free allowance actions used in a month"""
        if not month_year:
            month_year = date.today().replace(day=1)
        
        cache_key = f"{self.cache_prefix}:allowance_used:{user_id}:{action_type}:{month_year}"
        
        # Try cache first (with graceful Redis fallback)
        cached_data = None
        try:
            if cache_manager.redis_client:
                cached_data = await cache_manager.redis_client.get(cache_key)
            else:
                await cache_manager.initialize()
                if cache_manager.redis_client:
                    cached_data = await cache_manager.redis_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache unavailable for allowance used {user_id}:{action_type}: {e}")
            cached_data = None
            
        if cached_data is not None:
            import json
            cached_count = json.loads(cached_data)
            return cached_count
        
        try:
            # TEMPORARY FIX: Skip usage tracking due to model mismatch
            # TODO: Fix CreditUsageTracking model schema mismatch
            logger.warning(f"TEMP FIX: Skipping free allowance check for user {user_id}, action {action_type}")
            free_used = 0
                
            # Cache the result (with graceful Redis fallback)
            try:
                if cache_manager.redis_client:
                    import json
                    await cache_manager.redis_client.setex(
                        cache_key, 
                        self.allowance_cache_ttl, 
                        json.dumps(free_used, default=str)
                    )
            except Exception as e:
                logger.warning(f"Failed to cache allowance used for {user_id}:{action_type}: {e}")
                
            return free_used
                
        except Exception as e:
            logger.error(f"Error getting free allowance used for user {user_id}: {e}")
            return 0
    
    async def get_user_allowance_status(
        self,
        user_id: UUID,
        month_year: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive allowance status for all action types
        
        Args:
            user_id: User UUID
            month_year: Month to check (defaults to current month)
            
        Returns:
            Dictionary with allowance status for all actions
        """
        if not month_year:
            month_year = date.today().replace(day=1)
        
        cache_key = f"{self.cache_prefix}:user_allowances:{user_id}:{month_year}"
        
        # Try cache first (with graceful Redis fallback)
        cached_data = None
        try:
            if cache_manager.redis_client:
                cached_data = await cache_manager.redis_client.get(cache_key)
            else:
                await cache_manager.initialize()
                if cache_manager.redis_client:
                    cached_data = await cache_manager.redis_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache unavailable for user allowances {user_id}: {e}")
            cached_data = None
            
        if cached_data:
            import json
            cached_status = json.loads(cached_data)
            return cached_status
        
        try:
            # Get all active pricing rules
            rules = await self.get_all_pricing_rules()
            
            # TEMPORARY FIX: Skip usage tracking due to model mismatch
            # TODO: Fix CreditUsageTracking model schema mismatch
            logger.warning(f"TEMP FIX: Skipping allowance status for user {user_id}")
            usage_records = {}
            
            # Build allowance status
            allowance_status = {}
            
            for rule in rules:
                usage = usage_records.get(rule.action_type)
                free_used = usage.free_actions_used if usage else 0
                
                allowance_status[rule.action_type] = {
                    "display_name": rule.display_name,
                    "free_allowance": rule.free_allowance_per_month,
                    "free_used": free_used,
                    "free_remaining": max(0, rule.free_allowance_per_month - free_used),
                    "cost_per_action": rule.cost_per_action,
                    "paid_actions_used": usage.paid_actions_used if usage else 0,
                    "total_credits_spent": usage.total_credits_spent if usage else 0
                }
            
            status = {
                "month_year": month_year.isoformat(),
                "allowances": allowance_status,
                "summary": {
                    "total_free_actions_available": sum(
                        rule.free_allowance_per_month for rule in rules
                    ),
                    "total_free_actions_used": sum(
                        status["free_used"] for status in allowance_status.values()
                    ),
                    "total_paid_actions": sum(
                        status["paid_actions_used"] for status in allowance_status.values()
                    ),
                    "total_credits_spent": sum(
                        status["total_credits_spent"] for status in allowance_status.values()
                    )
                }
            }
            
            # Cache the status (with graceful Redis fallback)
            try:
                if cache_manager.redis_client:
                    import json
                    await cache_manager.redis_client.setex(
                        cache_key, 
                        self.allowance_cache_ttl, 
                        json.dumps(status, default=str)
                    )
            except Exception as e:
                logger.warning(f"Failed to cache user allowance status for {user_id}: {e}")
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting allowance status for user {user_id}: {e}")
            return {
                "month_year": month_year.isoformat() if month_year else None,
                "allowances": {},
                "summary": {}
            }
    
    # =========================================================================
    # PRICING ANALYTICS
    # =========================================================================
    
    async def get_pricing_analytics(self) -> Dict[str, Any]:
        """Get system-wide pricing analytics"""
        cache_key = f"{self.cache_prefix}:analytics"
        
        # Try cache first (with graceful Redis fallback)
        cached_data = None
        try:
            if cache_manager.redis_client:
                cached_data = await cache_manager.redis_client.get(cache_key)
            else:
                await cache_manager.initialize()
                if cache_manager.redis_client:
                    cached_data = await cache_manager.redis_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache unavailable for pricing analytics: {e}")
            cached_data = None
            
        if cached_data:
            import json
            cached_analytics = json.loads(cached_data)
            return cached_analytics
        
        try:
            current_month = date.today().replace(day=1)
            
            async with get_session() as session:
                # Get usage statistics
                usage_result = await session.execute(
                    text("""
                        SELECT 
                            action_type,
                            COUNT(DISTINCT user_id) as unique_users,
                            SUM(free_actions_used) as total_free_actions,
                            SUM(paid_actions_used) as total_paid_actions,
                            SUM(total_credits_spent) as total_credits_spent,
                            AVG(total_credits_spent) as avg_credits_per_user
                        FROM public.credit_usage_tracking
                        WHERE month_year = :current_month
                        GROUP BY action_type
                        ORDER BY total_credits_spent DESC
                    """),
                    {"current_month": current_month}
                )
                
                usage_data = usage_result.fetchall()
                
                # Get pricing rules for reference
                rules = await self.get_all_pricing_rules()
                rules_dict = {rule.action_type: rule for rule in rules}
                
                action_analytics = []
                total_revenue = 0
                
                for row in usage_data:
                    rule = rules_dict.get(row.action_type)
                    if not rule:
                        continue
                    
                    action_analytics.append({
                        "action_type": row.action_type,
                        "display_name": rule.display_name,
                        "cost_per_action": rule.cost_per_action,
                        "free_allowance": rule.free_allowance_per_month,
                        "unique_users": row.unique_users,
                        "total_free_actions": row.total_free_actions,
                        "total_paid_actions": row.total_paid_actions,
                        "total_credits_spent": row.total_credits_spent,
                        "avg_credits_per_user": float(row.avg_credits_per_user or 0),
                        "conversion_rate": (
                            row.total_paid_actions / (row.total_free_actions + row.total_paid_actions)
                            if (row.total_free_actions + row.total_paid_actions) > 0
                            else 0
                        )
                    })
                    
                    total_revenue += row.total_credits_spent
                
                analytics = {
                    "period": current_month.isoformat(),
                    "total_credits_spent": total_revenue,
                    "total_unique_users": len(set(row.unique_users for row in usage_data)),
                    "action_analytics": action_analytics,
                    "top_revenue_actions": sorted(
                        action_analytics,
                        key=lambda x: x["total_credits_spent"],
                        reverse=True
                    )[:5],
                    "highest_conversion_actions": sorted(
                        action_analytics,
                        key=lambda x: x["conversion_rate"],
                        reverse=True
                    )[:5]
                }
                
                # Cache analytics (with graceful Redis fallback)
                try:
                    if cache_manager.redis_client:
                        import json
                        await cache_manager.redis_client.setex(
                            cache_key, 
                            self.rules_cache_ttl, 
                            json.dumps(analytics, default=str)
                        )
                except Exception as e:
                    logger.warning(f"Failed to cache pricing analytics: {e}")
                
                return analytics
                
        except Exception as e:
            logger.error(f"Error getting pricing analytics: {e}")
            return {
                "period": current_month.isoformat() if current_month else None,
                "total_credits_spent": 0,
                "action_analytics": [],
                "top_revenue_actions": [],
                "highest_conversion_actions": []
            }
    
    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================
    
    async def _clear_pricing_cache(self) -> None:
        """Clear all pricing-related cache"""
        await cache_manager.delete_pattern(f"{self.cache_prefix}:*")
    
    async def clear_user_allowance_cache(self, user_id: UUID) -> None:
        """Clear allowance cache for a specific user"""
        await cache_manager.delete_pattern(f"{self.cache_prefix}:*:{user_id}:*")


# Global service instance
credit_pricing_service = CreditPricingService()