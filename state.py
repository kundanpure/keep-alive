"""
state.py — Persistent user pool for the Travyn Phantom Agent.
Reads/writes users.json so simulated users can "come back" in future sessions.
"""
import json
import random
import logging
from pathlib import Path

log = logging.getLogger(__name__)

USERS_FILE = Path(__file__).parent / "users.json"


def load_users() -> list:
    """Load all simulated users from disk."""
    if not USERS_FILE.exists():
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"❌ Could not read users.json: {e}")
        return []


def _save_users(users: list):
    """Write the full users list back to disk."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def save_user(user_data: dict):
    """Add a new simulated user to the pool."""
    users = load_users()
    # Avoid duplicates
    if any(u["email"] == user_data["email"] for u in users):
        log.debug(f"User {user_data['email']} already in pool, skipping.")
        return
    users.append(user_data)
    _save_users(users)
    log.info(f"💾 Saved user to pool. Total pool size: {len(users)}")


def get_random_user() -> dict | None:
    """Return a random user from the pool, or None if pool is empty."""
    users = load_users()
    if not users:
        return None
    return random.choice(users)


def get_users_with_trips() -> list:
    """Return only users who have created at least one trip."""
    users = load_users()
    return [u for u in users if u.get("tripIds")]


def add_trip_to_user(email: str, trip_id: str):
    """Attach a trip ID to an existing user in the pool."""
    users = load_users()
    for user in users:
        if user["email"] == email:
            user.setdefault("tripIds", []).append(trip_id)
            _save_users(users)
            log.debug(f"Trip {trip_id} attached to user {email}")
            return
    log.warning(f"⚠️  User {email} not found in pool when adding trip.")
