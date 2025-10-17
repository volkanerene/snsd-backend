"""
Subscription and Tier-based Access Control Middleware

This module provides utilities to check subscription limits and feature access
based on tenant's subscription tier.
"""

from fastapi import HTTPException, Depends
from typing import Optional, Literal
from datetime import datetime

from app.db.supabase_client import supabase
from app.utils.auth import get_current_user


# Feature flags per tier
TIER_FEATURES = {
    "free": {
        "max_users": 3,
        "max_contractors": 5,
        "max_evaluations_per_month": 10,
        "max_storage_gb": 1,
        "custom_roles": False,
        "api_access": False,
        "advanced_analytics": False,
        "white_label": False,
        "priority_support": False,
        "sla": False,
    },
    "starter": {
        "max_users": 10,
        "max_contractors": 25,
        "max_evaluations_per_month": 50,
        "max_storage_gb": 10,
        "custom_roles": False,
        "api_access": False,
        "advanced_analytics": False,
        "white_label": False,
        "priority_support": False,
        "sla": False,
    },
    "professional": {
        "max_users": 50,
        "max_contractors": 100,
        "max_evaluations_per_month": 200,
        "max_storage_gb": 50,
        "custom_roles": True,
        "api_access": True,
        "advanced_analytics": True,
        "white_label": False,
        "priority_support": True,
        "sla": False,
    },
    "enterprise": {
        "max_users": None,  # Unlimited
        "max_contractors": None,  # Unlimited
        "max_evaluations_per_month": None,  # Unlimited
        "max_storage_gb": 500,
        "custom_roles": True,
        "api_access": True,
        "advanced_analytics": True,
        "white_label": True,
        "priority_support": True,
        "sla": True,
    },
}


class SubscriptionService:
    """Service for checking subscription limits and features"""

    @staticmethod
    async def get_tenant_subscription(tenant_id: str) -> Optional[dict]:
        """Get active subscription for a tenant"""
        try:
            res = (
                supabase.table("tenant_subscriptions")
                .select(
                    """
                    *,
                    tier:tier_id(*)
                    """
                )
                .eq("tenant_id", tenant_id)
                .eq("status", "active")
                .order("starts_at", desc=True)
                .limit(1)
                .execute()
            )

            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception:
            return None

    @staticmethod
    async def get_tier_name(tenant_id: str) -> str:
        """Get tier name for tenant (defaults to 'free')"""
        subscription = await SubscriptionService.get_tenant_subscription(tenant_id)
        if not subscription or not subscription.get("tier"):
            return "free"

        return subscription["tier"].get("name", "free")

    @staticmethod
    async def check_feature_access(tenant_id: str, feature: str) -> bool:
        """Check if tenant has access to a feature"""
        tier_name = await SubscriptionService.get_tier_name(tenant_id)
        tier_features = TIER_FEATURES.get(tier_name, TIER_FEATURES["free"])

        return tier_features.get(feature, False)

    @staticmethod
    async def get_usage_count(
        tenant_id: str, usage_type: Literal["users", "contractors", "evaluations"]
    ) -> int:
        """Get current usage count for a tenant"""
        try:
            if usage_type == "users":
                res = (
                    supabase.table("tenant_users")
                    .select("id", count="exact")
                    .eq("tenant_id", tenant_id)
                    .eq("status", "active")
                    .execute()
                )
                return res.count or 0

            elif usage_type == "contractors":
                res = (
                    supabase.table("contractors")
                    .select("id", count="exact")
                    .eq("tenant_id", tenant_id)
                    .eq("status", "active")
                    .execute()
                )
                return res.count or 0

            elif usage_type == "evaluations":
                # Count evaluations created this month
                from datetime import datetime, timedelta

                start_of_month = datetime.now().replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )

                res = (
                    supabase.table("frm32_submissions")
                    .select("id", count="exact")
                    .eq("tenant_id", tenant_id)
                    .gte("created_at", start_of_month.isoformat())
                    .execute()
                )
                return res.count or 0

            return 0
        except Exception:
            return 0

    @staticmethod
    async def check_limit(
        tenant_id: str,
        usage_type: Literal["users", "contractors", "evaluations"],
        increment: int = 1,
    ) -> dict:
        """
        Check if tenant can perform an action without exceeding limits

        Returns:
            {
                "allowed": bool,
                "current_usage": int,
                "limit": int | None,
                "remaining": int | None,
                "tier": str
            }
        """
        tier_name = await SubscriptionService.get_tier_name(tenant_id)
        tier_features = TIER_FEATURES.get(tier_name, TIER_FEATURES["free"])

        # Get limit based on usage type
        limit_key = f"max_{usage_type}" if usage_type != "evaluations" else "max_evaluations_per_month"
        limit = tier_features.get(limit_key)

        # Get current usage
        current_usage = await SubscriptionService.get_usage_count(tenant_id, usage_type)

        # If limit is None (unlimited), always allow
        if limit is None:
            return {
                "allowed": True,
                "current_usage": current_usage,
                "limit": None,
                "remaining": None,
                "tier": tier_name,
            }

        # Check if adding increment would exceed limit
        new_usage = current_usage + increment
        allowed = new_usage <= limit

        return {
            "allowed": allowed,
            "current_usage": current_usage,
            "limit": limit,
            "remaining": max(0, limit - current_usage),
            "tier": tier_name,
        }


# Dependency functions for FastAPI endpoints


async def require_feature(
    feature: str, tenant_id: Optional[str] = None, user: dict = Depends(get_current_user)
):
    """
    Dependency to check if tenant has access to a feature

    Usage:
        @router.get("/advanced-analytics")
        async def get_analytics(
            _=Depends(lambda: require_feature("advanced_analytics")),
            user=Depends(get_current_user)
        ):
            ...
    """
    # Get tenant_id from user if not provided
    if not tenant_id:
        tenant_id = user.get("tenant_id")

    if not tenant_id:
        raise HTTPException(400, "Tenant ID required")

    has_access = await SubscriptionService.check_feature_access(tenant_id, feature)

    if not has_access:
        tier_name = await SubscriptionService.get_tier_name(tenant_id)
        raise HTTPException(
            403,
            f"Feature '{feature}' is not available in your current plan ({tier_name}). "
            "Please upgrade to access this feature.",
        )


async def check_usage_limit(
    tenant_id: str,
    usage_type: Literal["users", "contractors", "evaluations"],
    increment: int = 1,
):
    """
    Check if tenant can perform an action without exceeding limits
    Raises HTTPException if limit would be exceeded
    """
    result = await SubscriptionService.check_limit(tenant_id, usage_type, increment)

    if not result["allowed"]:
        limit = result["limit"]
        current = result["current_usage"]
        tier = result["tier"]

        raise HTTPException(
            403,
            f"Subscription limit reached. You have reached the maximum number of {usage_type} "
            f"({current}/{limit}) for your {tier} plan. Please upgrade to add more.",
        )

    return result


# Helper function to get full usage stats


async def get_tenant_usage_stats(tenant_id: str) -> dict:
    """Get complete usage statistics for a tenant"""
    tier_name = await SubscriptionService.get_tier_name(tenant_id)
    tier_features = TIER_FEATURES.get(tier_name, TIER_FEATURES["free"])

    users_count = await SubscriptionService.get_usage_count(tenant_id, "users")
    contractors_count = await SubscriptionService.get_usage_count(tenant_id, "contractors")
    evaluations_count = await SubscriptionService.get_usage_count(tenant_id, "evaluations")

    return {
        "tier": tier_name,
        "usage": {
            "users": {
                "current": users_count,
                "limit": tier_features.get("max_users"),
                "percentage": (
                    (users_count / tier_features["max_users"] * 100)
                    if tier_features.get("max_users")
                    else 0
                ),
            },
            "contractors": {
                "current": contractors_count,
                "limit": tier_features.get("max_contractors"),
                "percentage": (
                    (contractors_count / tier_features["max_contractors"] * 100)
                    if tier_features.get("max_contractors")
                    else 0
                ),
            },
            "evaluations": {
                "current": evaluations_count,
                "limit": tier_features.get("max_evaluations_per_month"),
                "percentage": (
                    (evaluations_count / tier_features["max_evaluations_per_month"] * 100)
                    if tier_features.get("max_evaluations_per_month")
                    else 0
                ),
            },
            "storage": {
                "current": 0,  # TODO: Implement storage tracking
                "limit": tier_features.get("max_storage_gb"),
                "percentage": 0,
            },
        },
        "features": {
            "custom_roles": tier_features.get("custom_roles", False),
            "api_access": tier_features.get("api_access", False),
            "advanced_analytics": tier_features.get("advanced_analytics", False),
            "white_label": tier_features.get("white_label", False),
            "priority_support": tier_features.get("priority_support", False),
            "sla": tier_features.get("sla", False),
        },
    }
