"""
Stripe Service - Complete subscription management
Handles product creation, subscription management, and webhook processing
"""
import logging
import os
import stripe
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class StripeService:
    """
    Complete Stripe integration service
    """

    def __init__(self):
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable is required")

        # Configure the stripe module with our API key
        stripe.api_key = self.secret_key

    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """
        Make async request to Stripe API using the native SDK.
        This method is kept for backward compatibility with callers that
        use the raw endpoint style. It routes to the appropriate SDK method.
        """
        try:
            # Route to the appropriate native SDK async method based on endpoint
            if method.upper() == 'GET':
                return await self._handle_get(endpoint, data)
            elif method.upper() == 'POST':
                return await self._handle_post(endpoint, data)
            elif method.upper() == 'DELETE':
                return await self._handle_delete(endpoint)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def _handle_get(self, endpoint: str, params: Dict = None) -> Dict:
        """Handle GET requests by routing to native SDK retrieve/list methods"""
        parts = endpoint.strip('/').split('/')

        # Handle resource/{id} pattern (retrieve)
        if len(parts) == 2:
            resource, resource_id = parts
            return await self._retrieve_resource(resource, resource_id, params)

        # Handle resource listing
        if len(parts) == 1:
            resource = parts[0]
            return await self._list_resource(resource, params)

        raise ValueError(f"Unsupported GET endpoint: {endpoint}")

    async def _handle_post(self, endpoint: str, data: Dict = None) -> Dict:
        """Handle POST requests by routing to native SDK create/modify methods"""
        parts = endpoint.strip('/').split('/')

        # Handle resource/{id} pattern (modify)
        if len(parts) == 2:
            resource, resource_id = parts
            return await self._modify_resource(resource, resource_id, data)

        # Handle resource creation
        if len(parts) == 1:
            resource = parts[0]
            return await self._create_resource(resource, data)

        raise ValueError(f"Unsupported POST endpoint: {endpoint}")

    async def _handle_delete(self, endpoint: str) -> Dict:
        """Handle DELETE requests"""
        parts = endpoint.strip('/').split('/')
        if len(parts) == 2:
            resource, resource_id = parts
            return await self._delete_resource(resource, resource_id)
        raise ValueError(f"Unsupported DELETE endpoint: {endpoint}")

    async def _retrieve_resource(self, resource: str, resource_id: str, params: Dict = None) -> Dict:
        """Retrieve a single resource by ID"""
        resource_map = {
            'customers': stripe.Customer,
            'products': stripe.Product,
            'prices': stripe.Price,
            'subscriptions': stripe.Subscription,
            'payment_links': stripe.PaymentLink,
            'webhook_endpoints': stripe.WebhookEndpoint,
        }
        cls = resource_map.get(resource)
        if not cls:
            raise ValueError(f"Unsupported resource type: {resource}")
        result = await cls.retrieve_async(resource_id, **(params or {}))
        return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

    async def _list_resource(self, resource: str, params: Dict = None) -> Dict:
        """List resources"""
        resource_map = {
            'customers': stripe.Customer,
            'products': stripe.Product,
            'prices': stripe.Price,
            'subscriptions': stripe.Subscription,
            'payment_links': stripe.PaymentLink,
            'webhook_endpoints': stripe.WebhookEndpoint,
        }
        cls = resource_map.get(resource)
        if not cls:
            raise ValueError(f"Unsupported resource type: {resource}")
        result = await cls.list_async(**(params or {}))
        return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

    async def _create_resource(self, resource: str, data: Dict = None) -> Dict:
        """Create a new resource"""
        resource_map = {
            'customers': stripe.Customer,
            'products': stripe.Product,
            'prices': stripe.Price,
            'subscriptions': stripe.Subscription,
            'payment_links': stripe.PaymentLink,
            'webhook_endpoints': stripe.WebhookEndpoint,
        }
        cls = resource_map.get(resource)
        if not cls:
            raise ValueError(f"Unsupported resource type: {resource}")
        result = await cls.create_async(**(data or {}))
        return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

    async def _modify_resource(self, resource: str, resource_id: str, data: Dict = None) -> Dict:
        """Modify an existing resource"""
        resource_map = {
            'customers': stripe.Customer,
            'products': stripe.Product,
            'prices': stripe.Price,
            'subscriptions': stripe.Subscription,
            'payment_links': stripe.PaymentLink,
            'webhook_endpoints': stripe.WebhookEndpoint,
        }
        cls = resource_map.get(resource)
        if not cls:
            raise ValueError(f"Unsupported resource type: {resource}")
        result = await cls.modify_async(resource_id, **(data or {}))
        return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

    async def _delete_resource(self, resource: str, resource_id: str) -> Dict:
        """Delete a resource"""
        resource_map = {
            'customers': stripe.Customer,
            'products': stripe.Product,
            'webhook_endpoints': stripe.WebhookEndpoint,
        }
        cls = resource_map.get(resource)
        if not cls:
            raise ValueError(f"Unsupported resource type: {resource}")
        result = await cls.delete_async(resource_id)
        return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

    # =========================================================================
    # PRODUCT MANAGEMENT
    # =========================================================================

    async def create_product(self, name: str, description: str, metadata: Dict = None) -> Dict:
        """Create a Stripe product"""
        try:
            params = {
                "name": name,
                "description": description,
                "type": "service"
            }

            if metadata:
                params["metadata"] = metadata

            result = await stripe.Product.create_async(**params)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def create_price(self, product_id: str, amount_cents: int, currency: str = "usd",
                    interval: str = "month", interval_count: int = 1) -> Dict:
        """Create a Stripe price for a product"""
        try:
            params = {
                "product": product_id,
                "unit_amount": amount_cents,
                "currency": currency,
                "recurring": {
                    "interval": interval,
                    "interval_count": interval_count
                }
            }

            result = await stripe.Price.create_async(**params)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def list_products(self, limit: int = 10) -> Dict:
        """List all Stripe products"""
        try:
            result = await stripe.Product.list_async(limit=limit)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def list_prices(self, product_id: str = None, limit: int = 10) -> Dict:
        """List prices for a product or all prices"""
        try:
            params = {"limit": limit}
            if product_id:
                params["product"] = product_id

            result = await stripe.Price.list_async(**params)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def create_customer(self, email: str, name: str = None, metadata: Dict = None) -> Dict:
        """Create a Stripe customer"""
        try:
            params = {"email": email}

            if name:
                params["name"] = name

            if metadata:
                params["metadata"] = metadata

            result = await stripe.Customer.create_async(**params)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def create_subscription(self, customer_id: str, price_id: str,
                          trial_period_days: int = None, metadata: Dict = None) -> Dict:
        """Create a subscription for a customer"""
        try:
            params = {
                "customer": customer_id,
                "items": [{"price": price_id}]
            }

            if trial_period_days:
                params["trial_period_days"] = trial_period_days

            if metadata:
                params["metadata"] = metadata

            result = await stripe.Subscription.create_async(**params)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details"""
        try:
            result = await stripe.Subscription.retrieve_async(subscription_id)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def list_customer_subscriptions(self, customer_id: str) -> Dict:
        """List all subscriptions for a customer"""
        try:
            result = await stripe.Subscription.list_async(customer=customer_id)
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Dict:
        """Cancel a subscription"""
        try:
            if at_period_end:
                result = await stripe.Subscription.modify_async(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                result = await stripe.Subscription.cancel_async(subscription_id)

            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

    # =========================================================================
    # SETUP METHODS
    # =========================================================================

    async def setup_analytics_following_products(self) -> Dict[str, str]:
        """
        Set up all Analytics Following subscription products and prices
        Returns a dict with price IDs for each tier
        """
        logger.info("Setting up Analytics Following products and pricing...")

        products_config = [
            {
                "name": "Analytics Following - Free Plan",
                "description": "Basic analytics with limited monthly allowances",
                "price_cents": 0,
                "metadata": {
                    "tier": "free",
                    "profiles_limit": "5",
                    "team_members": "1"
                }
            },
            {
                "name": "Analytics Following - Standard Plan",
                "description": "Full analytics with 500 profile unlocks, 2 team members",
                "price_cents": 19900,  # $199.00
                "metadata": {
                    "tier": "standard",
                    "profiles_limit": "500",
                    "team_members": "2"
                }
            },
            {
                "name": "Analytics Following - Premium Plan",
                "description": "Full analytics with 2,000 profile unlocks, 5 team members, 20% topup discount",
                "price_cents": 49900,  # $499.00
                "metadata": {
                    "tier": "premium",
                    "profiles_limit": "2000",
                    "team_members": "5",
                    "topup_discount": "20"
                }
            }
        ]

        price_ids = {}

        for config in products_config:
            try:
                # Create product
                product = await self.create_product(
                    name=config["name"],
                    description=config["description"],
                    metadata=config["metadata"]
                )

                logger.info(f"Created product: {product['name']} (ID: {product['id']})")

                # Create price
                price = await self.create_price(
                    product_id=product["id"],
                    amount_cents=config["price_cents"],
                    currency="usd",
                    interval="month"
                )

                tier = config["metadata"]["tier"]
                price_ids[f"{tier}_price_id"] = price["id"]

                logger.info(f"Created price for {tier}: {price['id']} (${config['price_cents']/100}/month)")

            except Exception as e:
                logger.error(f"Failed to create product {config['name']}: {e}")
                raise

        logger.info("All Analytics Following products created successfully!")
        logger.info(f"Price IDs: {price_ids}")

        return price_ids

    async def create_webhook_endpoint(self, url: str, events: List[str]) -> Dict:
        """Create a webhook endpoint"""
        try:
            result = await stripe.WebhookEndpoint.create_async(
                url=url,
                enabled_events=events
            )
            return result.to_dict_recursive() if hasattr(result, 'to_dict_recursive') else dict(result)

        except stripe.StripeError as e:
            logger.error(f"Stripe API request failed: {e}")
            raise

# Global stripe service instance
stripe_service = StripeService()
