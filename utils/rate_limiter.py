"""
EchoHound Rate Limiter
======================
Sophisticated rate limiting to prevent spam and abuse.

Tiers:
- WHITELISTED: No limits (admins, trusted users)
- NORMAL: 10 messages/minute, 50/hour
- NEW_USER: 5 messages/minute, 20/hour (first 24 hours)
- RATE_LIMITED: Temporary cooldown after exceeding limits
"""

import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from enum import Enum

RATE_LIMIT_DB = Path(__file__).parent.parent / "memory" / "rate_limits.json"

class RateTier(Enum):
    WHITELISTED = "whitelisted"  # No limits
    ADMIN = "admin"              # No limits
    NORMAL = "normal"            # Standard limits
    NEW_USER = "new_user"        # Stricter limits (first day)
    RATE_LIMITED = "rate_limited"  # Temporary cooldown


# Limit configuration: (messages, window_seconds)
LIMITS = {
    RateTier.WHITELISTED: [(999999, 60)],  # Practically unlimited
    RateTier.ADMIN: [(999999, 60)],
    RateTier.NORMAL: [(10, 60), (50, 3600)],  # 10/min, 50/hour
    RateTier.NEW_USER: [(5, 60), (20, 3600)],  # 5/min, 20/hour (first 24h)
    RateTier.RATE_LIMITED: [(1, 300)],  # 1 per 5 minutes during cooldown
}


class RateLimiter:
    def __init__(self):
        self._data: Dict[str, dict] = {}
        self._load()
    
    def _load(self):
        """Load rate limit state from disk."""
        if RATE_LIMIT_DB.exists():
            try:
                self._data = json.loads(RATE_LIMIT_DB.read_text())
            except:
                self._data = {}
    
    def _save(self):
        """Save rate limit state to disk."""
        RATE_LIMIT_DB.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_DB.write_text(json.dumps(self._data, indent=2))
    
    def _get_user_key(self, user_id: int, chat_id: int) -> str:
        """Create unique key for user in specific chat."""
        return f"{chat_id}:{user_id}"
    
    def get_tier(self, user_id: int, chat_id: int, 
                 admin_ids: Optional[list] = None) -> RateTier:
        """
        Determine rate limit tier for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID (for per-chat isolation)
            admin_ids: List of admin user IDs (bypass all limits)
        """
        key = self._get_user_key(user_id, chat_id)
        
        # Check if user is admin
        if admin_ids and user_id in admin_ids:
            return RateTier.ADMIN
        
        # Check if explicitly whitelisted
        user_data = self._data.get(key, {})
        if user_data.get("tier") == RateTier.WHITELISTED.value:
            return RateTier.WHITELISTED
        
        # Check if currently rate limited
        cooldown_until = user_data.get("cooldown_until", 0)
        if time.time() < cooldown_until:
            return RateTier.RATE_LIMITED
        
        # Check if new user (first 24 hours)
        first_seen = user_data.get("first_seen")
        if first_seen:
            try:
                first_dt = datetime.fromisoformat(first_seen)
                if datetime.now() - first_dt < timedelta(hours=24):
                    return RateTier.NEW_USER
            except:
                pass
        
        return RateTier.NORMAL
    
    def check_rate_limit(self, user_id: int, chat_id: int, 
                         admin_ids: Optional[list] = None) -> Tuple[bool, str]:
        """
        Check if user is allowed to send a message.
        
        Returns:
            (allowed: bool, message: str) - message explains why if not allowed
        """
        key = self._get_user_key(user_id, chat_id)
        now = time.time()
        
        tier = self.get_tier(user_id, chat_id, admin_ids)
        limits = LIMITS[tier]
        
        # Get or create user entry
        if key not in self._data:
            self._data[key] = {
                "first_seen": datetime.now().isoformat(),
                "message_times": [],
                "tier": tier.value,
                "violation_count": 0,
                "cooldown_until": 0
            }
        
        user_entry = self._data[key]
        message_times = user_entry.get("message_times", [])
        
        # Clean old messages
        for limit_count, window in limits:
            cutoff = now - window
            message_times = [t for t in message_times if t > cutoff]
        
        # Check each limit
        for limit_count, window in limits:
            window_messages = [t for t in message_times if t > now - window]
            if len(window_messages) >= limit_count:
                # Rate limit hit
                user_entry["violation_count"] = user_entry.get("violation_count", 0) + 1
                
                # Progressive cooldown: 1min, 5min, 15min, 30min, 60min
                violations = user_entry["violation_count"]
                cooldown_minutes = [1, 5, 15, 30, 60][min(violations - 1, 4)]
                cooldown_until = now + (cooldown_minutes * 60)
                user_entry["cooldown_until"] = cooldown_until
                user_entry["tier"] = RateTier.RATE_LIMITED.value
                
                self._data[key] = user_entry
                self._save()
                
                return False, (
                    f"⏳ Rate limit exceeded. Please wait {cooldown_minutes} minute(s) "
                    f"before sending more messages."
                )
        
        # Record this message
        message_times.append(now)
        user_entry["message_times"] = message_times
        self._data[key] = user_entry
        self._save()
        
        return True, ""
    
    def record_message(self, user_id: int, chat_id: int):
        """Record that a message was sent (for stats)."""
        key = self._get_user_key(user_id, chat_id)
        if key in self._data:
            self._data[key]["message_times"] = self._data[key].get("message_times", [])
            self._data[key]["message_times"].append(time.time())
            self._save()
    
    def whitelist_user(self, user_id: int, chat_id: int):
        """Whitelist a user (no rate limits)."""
        key = self._get_user_key(user_id, chat_id)
        if key not in self._data:
            self._data[key] = {}
        self._data[key]["tier"] = RateTier.WHITELISTED.value
        self._data[key]["cooldown_until"] = 0
        self._save()
    
    def unwhitelist_user(self, user_id: int, chat_id: int):
        """Remove user from whitelist."""
        key = self._get_user_key(user_id, chat_id)
        if key in self._data:
            self._data[key]["tier"] = RateTier.NORMAL.value
            self._save()
    
    def get_stats(self, user_id: int, chat_id: int) -> dict:
        """Get rate limit stats for a user."""
        key = self._get_user_key(user_id, chat_id)
        user_entry = self._data.get(key, {})
        
        now = time.time()
        message_times = user_entry.get("message_times", [])
        
        # Messages in last minute, hour, day
        min_1 = len([t for t in message_times if t > now - 60])
        hour_1 = len([t for t in message_times if t > now - 3600])
        day_1 = len([t for t in message_times if t > now - 86400])
        
        return {
            "tier": user_entry.get("tier", RateTier.NORMAL.value),
            "messages_last_minute": min_1,
            "messages_last_hour": hour_1,
            "messages_last_day": day_1,
            "violation_count": user_entry.get("violation_count", 0),
            "first_seen": user_entry.get("first_seen", "Unknown"),
        }
    
    def reset_user(self, user_id: int, chat_id: int):
        """Reset rate limit data for a user."""
        key = self._get_user_key(user_id, chat_id)
        if key in self._data:
            del self._data[key]
            self._save()


# Global instance
_rate_limiter = RateLimiter()


def check_rate_limit(user_id: int, chat_id: int, admin_ids: Optional[list] = None) -> Tuple[bool, str]:
    """Convenience function for global rate limiter."""
    return _rate_limiter.check_rate_limit(user_id, chat_id, admin_ids)


def get_user_tier(user_id: int, chat_id: int, admin_ids: Optional[list] = None) -> RateTier:
    """Convenience function to get tier."""
    return _rate_limiter.get_tier(user_id, chat_id, admin_ids)


def get_user_stats(user_id: int, chat_id: int) -> dict:
    """Convenience function to get stats."""
    return _rate_limiter.get_stats(user_id, chat_id)


def whitelist_user(user_id: int, chat_id: int):
    """Convenience function to whitelist."""
    _rate_limiter.whitelist_user(user_id, chat_id)


def unwhitelist_user(user_id: int, chat_id: int):
    """Convenience function to unwhitelist."""
    _rate_limiter.unwhitelist_user(user_id, chat_id)


def reset_user(user_id: int, chat_id: int):
    """Convenience function to reset user."""
    _rate_limiter.reset_user(user_id, chat_id)
