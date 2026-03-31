"""
User Manager for EchoHound
Manages per-user memory files with session tracking.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List


class UserManager:
    """
    Manages user-specific memory and session state.
    Creates isolated memory files per user.
    """

    def __init__(self, base_dir: str = "./memory/users"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _get_user_path(self, user_id: str) -> str:
        """Get the file path for a user's memory file."""
        # Sanitize user_id for filesystem safety
        safe_id = hashlib.md5(user_id.encode()).hexdigest()[:16]
        return os.path.join(self.base_dir, f"{safe_id}.json")

    def _load_user(self, user_id: str) -> dict:
        """Load a user's memory data."""
        path = self._get_user_path(user_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return self._create_user(user_id)

    def _create_user(self, user_id: str) -> dict:
        """Create a new user record."""
        return {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "message_count": 0,
            "sessions": [],
            "preferences": {},
            "context": {},
        }

    def _save_user(self, user_id: str, data: dict):
        """Save a user's memory data."""
        path = self._get_user_path(user_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_user_context(self, user_id: str) -> dict:
        """Get the full context for a user."""
        return self._load_user(user_id)

    def update_activity(self, user_id: str):
        """Update last active timestamp."""
        data = self._load_user(user_id)
        data["last_active"] = datetime.now().isoformat()
        data["message_count"] += 1
        self._save_user(user_id, data)

    def add_session(self, user_id: str, session_id: str):
        """Record a new session for the user."""
        data = self._load_user(user_id)
        if session_id not in data["sessions"]:
            data["sessions"].append(session_id)
        self._save_user(user_id, data)

    def set_preference(self, user_id: str, key: str, value: any):
        """Set a user preference."""
        data = self._load_user(user_id)
        data["preferences"][key] = value
        self._save_user(user_id, data)

    def get_preference(self, user_id: str, key: str, default: any = None) -> any:
        """Get a user preference."""
        data = self._load_user(user_id)
        return data["preferences"].get(key, default)

    def add_context(self, user_id: str, key: str, value: any):
        """Add context information about the user."""
        data = self._load_user(user_id)
        data["context"][key] = value
        self._save_user(user_id, data)

    def get_context(self, user_id: str, key: str) -> any:
        """Get context information about the user."""
        data = self._load_user(user_id)
        return data["context"].get(key)

    def get_active_users(self, minutes: int = 60) -> List[str]:
        """Get users active in the last N minutes."""
        active = []
        cutoff = datetime.now().timestamp() - (minutes * 60)

        for filename in os.listdir(self.base_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.base_dir, filename)
                with open(path, "r") as f:
                    data = json.load(f)
                    last_active = datetime.fromisoformat(data["last_active"]).timestamp()
                    if last_active > cutoff:
                        active.append(data["user_id"])

        return active

    def clear_user(self, user_id: str):
        """Clear all data for a user (GDPR-style)."""
        path = self._get_user_path(user_id)
        if os.path.exists(path):
            os.remove(path)
