"""
Waitlist storage — saves emails to a JSON file.
Simple and sufficient for early validation (0-500 signups).
Replace with a database when it matters.
"""

import json
import os
from datetime import datetime, timezone

WAITLIST_FILE = os.path.join(os.path.dirname(__file__), "waitlist.json")


def _load() -> list:
    if not os.path.exists(WAITLIST_FILE):
        return []
    try:
        with open(WAITLIST_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save(entries: list):
    with open(WAITLIST_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def add_email(email: str, sachet_size: int = None,
              weekly_hours: float = None, source: str = "landing") -> dict:
    """
    Add an email to the waitlist.
    Returns the entry if new, or None if already exists.
    """
    email = email.strip().lower()
    entries = _load()

    # Check for duplicates
    for entry in entries:
        if entry["email"] == email:
            return None  # already on list

    entry = {
        "email": email,
        "sachet_size": sachet_size,
        "weekly_hours": weekly_hours,
        "source": source,
        "signed_up": datetime.now(timezone.utc).isoformat(),
    }

    entries.append(entry)
    _save(entries)
    return entry


def get_count() -> int:
    return len(_load())


def get_all() -> list:
    return _load()
