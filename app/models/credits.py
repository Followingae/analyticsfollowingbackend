"""
Credit System Models - Pydantic Models for API Requests/Responses
Comprehensive credits-based monetization layer for the analytics platform
"""
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from decimal import Decimal
import uuid


# =============================================================================
# CREDIT PACKAGE MODELS
# =============================================================================

class CreditPackageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Internal package identifier")
    display_name: str = Field(..., min_length=1, max_length=150, description="User-friendly package name")
    monthly_credits: int = Field(..., ge=0, description="Monthly credit allowance")
    description: Optional[str] = Field(None, description="Package description")
    is_active: bool = Field(True, description="Whether package is available for selection")
    sort_order: int = Field(0, description="Display order in UI")


class CreditPackageCreate(CreditPackageBase):
    pass


class CreditPackageUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=150)
    monthly_credits: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class CreditPackage(CreditPackageBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# =============================================================================
# CREDIT WALLET MODELS
# =============================================================================

class CreditWalletBase(BaseModel):
    package_id: Optional[int] = None
    current_balance: int = Field(0, ge=0, description="Current credit balance")
    rollover_months_allowed: int = Field(0, ge=0, le=2, description="Months to allow credit rollover")
    billing_cycle_start: date = Field(..., description="Billing cycle start date")
    next_reset_date: date = Field(..., description="Next credit reset date")
    is_locked: bool = Field(False, description="Whether wallet is locked")
    subscription_active: bool = Field(True, description="Whether subscription is active")


class CreditWalletCreate(CreditWalletBase):
    user_id: uuid.UUID


class CreditWalletUpdate(BaseModel):
    package_id: Optional[int] = None
    rollover_months_allowed: Optional[int] = Field(None, ge=0, le=2)
    is_locked: Optional[bool] = None
    subscription_active: Optional[bool] = None


class CreditWallet(CreditWalletBase):
    id: int
    user_id: uuid.UUID
    total_earned_this_cycle: int = Field(0, ge=0)
    total_purchased_this_cycle: int = Field(0, ge=0)
    total_spent_this_cycle: int = Field(0, ge=0)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class CreditWalletSummary(BaseModel):
    """Lightweight wallet summary for API responses"""
    current_balance: int
    is_locked: bool
    subscription_active: bool
    next_reset_date: date
    total_spent_this_cycle: int


# =============================================================================
# CREDIT PRICING MODELS
# =============================================================================

class CreditPricingRuleBase(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=50, description="Action type identifier")
    display_name: str = Field(..., min_length=1, max_length=100, description="User-friendly action name")
    cost_per_action: int = Field(..., ge=0, description="Credits required per action")
    free_allowance_per_month: int = Field(0, ge=0, description="Free actions per month")
    description: Optional[str] = None
    is_active: bool = Field(True)


class CreditPricingRuleCreate(CreditPricingRuleBase):
    pass


class CreditPricingRuleUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    cost_per_action: Optional[int] = Field(None, ge=0)
    free_allowance_per_month: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreditPricingRule(CreditPricingRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# =============================================================================
# CREDIT TRANSACTION MODELS
# =============================================================================

TransactionType = Literal[
    "earn", "spend", "purchase", "reset", "expire", "rollover", "manual_adjust", "refund"
]


class CreditTransactionBase(BaseModel):
    transaction_type: TransactionType
    action_type: Optional[str] = Field(None, max_length=50)
    amount: int = Field(..., description="Credit amount (positive for add, negative for spend)")
    description: Optional[str] = None
    reference_id: Optional[str] = Field(None, max_length=255)
    reference_type: Optional[str] = Field(None, max_length=50)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('amount')
    def validate_amount_by_type(cls, v, values):
        transaction_type = values.get('transaction_type')
        if transaction_type == 'spend' and v >= 0:
            raise ValueError('Spend transactions must have negative amounts')
        elif transaction_type != 'spend' and v < 0:
            raise ValueError('Non-spend transactions must have positive amounts')
        return v


class CreditTransactionCreate(CreditTransactionBase):
    wallet_id: int


class CreditTransaction(CreditTransactionBase):
    id: int
    user_id: uuid.UUID
    wallet_id: int
    balance_before: int = Field(..., ge=0)
    balance_after: int = Field(..., ge=0)
    billing_cycle_date: date
    created_at: datetime
    
    class Config:
        orm_mode = True


class CreditTransactionSummary(BaseModel):
    """Lightweight transaction summary for history views"""
    id: int
    transaction_type: TransactionType
    action_type: Optional[str]
    amount: int
    description: Optional[str]
    balance_after: int
    created_at: datetime


# =============================================================================
# UNLOCKED INFLUENCERS MODELS
# =============================================================================

class UnlockedInfluencerBase(BaseModel):
    profile_id: uuid.UUID = Field(..., description="Profile UUID")
    username: str = Field(..., min_length=1, max_length=100)
    credits_spent: int = Field(..., gt=0)


class UnlockedInfluencerCreate(UnlockedInfluencerBase):
    transaction_id: Optional[int] = None


class UnlockedInfluencer(UnlockedInfluencerBase):
    id: int
    user_id: uuid.UUID
    unlocked_at: datetime
    transaction_id: Optional[int] = None
    
    class Config:
        orm_mode = True


# =============================================================================
# CREDIT USAGE TRACKING MODELS
# =============================================================================

class CreditUsageTrackingBase(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=50)
    month_year: date = Field(..., description="First day of the month")
    free_actions_used: int = Field(0, ge=0)
    paid_actions_used: int = Field(0, ge=0)
    total_credits_spent: int = Field(0, ge=0)


class CreditUsageTrackingCreate(CreditUsageTrackingBase):
    user_id: uuid.UUID


class CreditUsageTrackingUpdate(BaseModel):
    free_actions_used: Optional[int] = Field(None, ge=0)
    paid_actions_used: Optional[int] = Field(None, ge=0)
    total_credits_spent: Optional[int] = Field(None, ge=0)


class CreditUsageTracking(CreditUsageTrackingBase):
    id: int
    user_id: uuid.UUID
    last_updated: datetime
    
    class Config:
        orm_mode = True


# =============================================================================
# TOP-UP ORDER MODELS
# =============================================================================

PaymentStatus = Literal[
    "pending", "processing", "completed", "failed", "cancelled", "refunded"
]


class CreditTopUpOrderBase(BaseModel):
    credits_amount: int = Field(..., gt=0, description="Number of credits to purchase")
    price_usd_cents: int = Field(..., gt=0, description="Price in USD cents")
    currency: str = Field("USD", min_length=3, max_length=3)
    payment_method: Optional[str] = Field(None, max_length=50)


class CreditTopUpOrderCreate(CreditTopUpOrderBase):
    pass


class CreditTopUpOrderUpdate(BaseModel):
    stripe_payment_intent_id: Optional[str] = None
    payment_status: Optional[PaymentStatus] = None
    credits_delivered: Optional[bool] = None
    failure_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreditTopUpOrder(CreditTopUpOrderBase):
    id: int
    user_id: uuid.UUID
    wallet_id: int
    order_reference: str
    stripe_payment_intent_id: Optional[str] = None
    payment_status: PaymentStatus
    credits_delivered: bool
    delivered_at: Optional[datetime] = None
    transaction_id: Optional[int] = None
    failure_reason: Optional[str] = None
    retry_count: int
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# =============================================================================
# CREDIT ACTION MODELS
# =============================================================================

class CreditActionRequest(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=50)
    reference_id: Optional[str] = Field(None, max_length=255)
    reference_type: Optional[str] = Field(None, max_length=50)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreditActionResponse(BaseModel):
    success: bool
    credits_spent: int
    new_balance: int
    transaction_id: Optional[int] = None
    message: Optional[str] = None
    used_free_allowance: bool = False


class CanPerformActionResponse(BaseModel):
    can_perform: bool
    reason: str
    credits_required: int = 0
    wallet_balance: int = 0
    free_remaining: int = 0
    credits_needed: int = 0
    message: Optional[str] = None


# =============================================================================
# CREDIT DASHBOARD MODELS
# =============================================================================

class CreditDashboard(BaseModel):
    """Complete credit dashboard data"""
    wallet: CreditWalletSummary
    recent_transactions: List[CreditTransactionSummary]
    monthly_usage: Dict[str, Any]
    pricing_rules: List[CreditPricingRule]
    unlocked_influencers_count: int
    
    class Config:
        orm_mode = True


class MonthlyUsageSummary(BaseModel):
    month_year: date
    total_spent: int
    actions_breakdown: Dict[str, Dict[str, int]]  # action_type -> {free_used, paid_used, credits_spent}
    top_actions: List[Dict[str, Any]]


# =============================================================================
# ADMIN MODELS
# =============================================================================

class AdminCreditAdjustment(BaseModel):
    user_id: uuid.UUID
    amount: int = Field(..., description="Credits to add (positive) or remove (negative)")
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = None


class AdminCreditStats(BaseModel):
    total_users_with_wallets: int
    total_credits_in_circulation: int
    total_credits_spent_today: int
    total_credits_spent_this_month: int
    top_spending_users: List[Dict[str, Any]]
    most_used_actions: List[Dict[str, Any]]


# =============================================================================
# UTILITY MODELS
# =============================================================================

class CreditBalance(BaseModel):
    """Simple balance response"""
    balance: int
    is_locked: bool
    next_reset_date: date