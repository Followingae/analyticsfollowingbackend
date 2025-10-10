"""
Stripe Service - Complete subscription management
Handles product creation, subscription management, and webhook processing
"""
import logging
import os
import requests
import json
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

        self.base_url = "https://api.stripe.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Stripe API"""
        url = f"{self.base_url}/{endpoint}"

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, data=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, data=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Stripe API request failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise

    # =========================================================================
    # PRODUCT MANAGEMENT
    # =========================================================================

    def create_product(self, name: str, description: str, metadata: Dict = None) -> Dict:
        """Create a Stripe product"""
        data = {
            "name": name,
            "description": description,
            "type": "service"
        }

        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "products", data)

    def create_price(self, product_id: str, amount_cents: int, currency: str = "usd",
                    interval: str = "month", interval_count: int = 1) -> Dict:
        """Create a Stripe price for a product"""
        data = {
            "product": product_id,
            "unit_amount": amount_cents,
            "currency": currency,
            "recurring[interval]": interval,
            "recurring[interval_count]": interval_count
        }

        return self._make_request("POST", "prices", data)

    def list_products(self, limit: int = 10) -> Dict:
        """List all Stripe products"""
        return self._make_request("GET", "products", {"limit": limit})

    def list_prices(self, product_id: str = None, limit: int = 10) -> Dict:
        """List prices for a product or all prices"""
        params = {"limit": limit}
        if product_id:
            params["product"] = product_id

        return self._make_request("GET", "prices", params)

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    def create_customer(self, email: str, name: str = None, metadata: Dict = None) -> Dict:
        """Create a Stripe customer"""
        data = {"email": email}

        if name:
            data["name"] = name

        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "customers", data)

    def create_subscription(self, customer_id: str, price_id: str,
                          trial_period_days: int = None, metadata: Dict = None) -> Dict:
        """Create a subscription for a customer"""
        data = {
            "customer": customer_id,
            "items[0][price]": price_id
        }

        if trial_period_days:
            data["trial_period_days"] = trial_period_days

        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "subscriptions", data)

    def get_subscription(self, subscription_id: str) -> Dict:
        """Get subscription details"""
        return self._make_request("GET", f"subscriptions/{subscription_id}")

    def list_customer_subscriptions(self, customer_id: str) -> Dict:
        """List all subscriptions for a customer"""
        return self._make_request("GET", "subscriptions", {"customer": customer_id})

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Dict:
        """Cancel a subscription"""
        data = {"cancel_at_period_end": str(at_period_end).lower()}
        return self._make_request("POST", f"subscriptions/{subscription_id}", data)

    # =========================================================================
    # SETUP METHODS
    # =========================================================================

    def setup_analytics_following_products(self) -> Dict[str, str]:
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
                product = self.create_product(
                    name=config["name"],
                    description=config["description"],
                    metadata=config["metadata"]
                )

                logger.info(f"Created product: {product['name']} (ID: {product['id']})")

                # Create price
                price = self.create_price(
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

        logger.info("✅ All Analytics Following products created successfully!")
        logger.info(f"Price IDs: {price_ids}")

        return price_ids

    def create_webhook_endpoint(self, url: str, events: List[str]) -> Dict:
        """Create a webhook endpoint"""
        data = {
            "url": url,
            "enabled_events": events
        }

        return self._make_request("POST", "webhook_endpoints", data)

# Global stripe service instance
stripe_service = StripeService()