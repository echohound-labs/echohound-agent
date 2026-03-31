"""
Rate Limiter for EchoHound
Tiered rate limiting based on user activity and trust.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Literal
from dataclasses import dataclass, asdict

UserTier = Literal["new", "active", "trusted", "premium"]


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting tiers."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    cooldown_seconds: int


TIER_CONFIGS = {
    "new": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=30,
        requests_per_day=100,
        cooldown_seconds=5,
    ),
    "active": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=500,
        cooldown_seconds=2,
    ),
    "trusted": RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=300,
        requests_per_day=2000,
        cooldown_seconds=1,
    ),
    "premium": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        cooldown_seconds=0,
    ),
}


class RateLimiter:
    """
    Tiered rate limiter with user activity tracking.
    Automatically promotes users based on engagement.
    """

    def __init__(self, storage_dir: str = "./memory/rate_limits"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _get_user_file(self, user_id: str) -> str:
        """Get storage path for user rate limit data."""
        safe_id = "".join(c for c in user_id if c.isalnum())[:32]
        return os.path.join(self.storage_dir, f"{safe_id}.json")

    def _load_user_data(self, user_id: str) -> dict:
        """Load user's rate limit tracking data."""
        filepath = self._get_user_file(user_id)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
        return self._init_user_data(user_id)

    def _init_user_data(self, user_id: str) -> dict:
        """Initialize data for a new user."""
        now = datetime.now().isoformat()
        return {
            "user_id": user_id,
            "tier": "new",
            "first_seen": now,
            "total_requests": 0,
            "requests": [],  # List of timestamps
            "strikes": 0,
        }

    def _save_user_data(self, user_id: str, data: dict):
        """Save user's rate limit tracking data."""
        filepath = self._get_user_file(user_id)
        with open(filepath, "w") as f:
            json.dump(data, f)

    def _get_tier(self, user_id: str) -> UserTier:
        """Determine user's current tier based on activity."""
        data = self._load_user_data(user_id)

        # Auto-promotion logic
        total = data.get("total_requests", 0)
        first_seen = datetime.fromisoformat(data["first_seen"])
        days_active = (datetime.now() - first_seen).days

        # Premium: manual assignment only (check if set)
        if data["tier"] == "premium":
            return "premium"

        # Trusted: 7+ days, 200+ requests
        if days_active >= 7 and total >= 200:
            return "trusted"

        # Active: 3+ days, 50+ requests
        if days_active >= 3 and total >= 50:
            return "active"

        return "new"

    def check_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if user can make a request.
        Returns (allowed, error_message).
        """
        data = self._load_user_data(user_id)
        tier = self._get_tier(user_id)
        config = TIER_CONFIGS[tier]
        now = datetime.now()

        # Clean old requests (keep last 24 hours)
        cutoff = now - timedelta(hours=24)
        data["requests"] = [
            ts for ts in data["requests"]
            if datetime.fromisoformat(ts) > cutoff
        ]

        # Check minute limit
        minute_ago = now - timedelta(minutes=1)
        minute_requests = sum(
            1 for ts in data["requests"]
            if datetime.fromisoformat(ts) > minute_ago
        )
        if minute_requests >= config.requests_per_minute:
            return False, f"Rate limit: {config.requests_per_minute}/min exceeded. Wait {config.cooldown_seconds}s."

        # Check hour limit
        hour_ago = now - timedelta(hours=1)
        hour_requests = sum(
            1 for ts in data["requests"]
            if datetime.fromisoformat(ts) > hour_ago
        )
        if hour_requests >= config.requests_per_hour:
            return False, f"Rate limit: {config.requests_per_hour}/hour exceeded. Try again later."

        # Check day limit
        day_ago = now - timedelta(days=1)
        day_requests = sum(
            1 for ts in data["requests"]
            if datetime.fromisoformat(ts) > day_ago
        )
        if day_requests >= config.requests_per_day:
            return False, f"Rate limit: {config.requests_per_day}/day exceeded. Try again tomorrow."

        # Record this request
        data["requests"].append(now.isoformat())
        data["total_requests"] = data.get("total_requests", 0) + 1

        # Update tier if changed
        new_tier = self._get_tier(user_id)
        if new_tier != data["tier"]:
            data["tier"] = new_tier

        self._save_user_data(user_id, data)
        return True, None

    def get_status(self, user_id: str) -> dict:
        """Get current rate limit status for a user."""
        data = self._load_user_data(user_id)
        tier = self._get_tier(user_id)
        config = TIER_CONFIGS[tier]

        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        return {
            "tier": tier,
            "limits": {
                "per_minute": config.requests_per_minute,
                "per_hour": config.requests_per_hour,
                "per_day": config.requests_per_day,
            },
            "usage": {
                "last_minute": sum(1 for ts in data["requests"] if datetime.fromisoformat(ts) > minute_ago),
                "last_hour": sum(1 for ts in data["requests"] if datetime.fromisoformat(ts) > hour_ago),
                "last_day": sum(1 for ts in data["requests"] if datetime.fromisoformat(ts) > day_ago),
            },
            "total_requests": data.get("total_requests", 0),
            "strikes": data.get("strikes", 0),
        }

    def add_strike(self, user_id: str, reason: str = ""):
        """Add a strike against a user (abuse detection)."""
        data = self._load_user_data(user_id)
        data["strikes"] = data.get("strikes", 0) + 1
        data.setdefault("strike_reasons", []).append({
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        })
        self._save_user_data(user_id, data)

    def set_tier(self, user_id: str, tier: UserTier):
        """Manually set a user's tier (admin only)."""
        data = self._load_user_data(user_id)
        data["tier"] = tier
        self._save_user_data(user_id, data)
