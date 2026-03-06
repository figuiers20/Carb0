"""
Strava API client — handles OAuth and activity fetching.
"""

import requests
from urllib.parse import urlencode

STRAVA_API = "https://www.strava.com/api/v3"
STRAVA_OAUTH = "https://www.strava.com/oauth"

# Cycling activity types where athletes would use carb fuel
CYCLING_TYPES = {
    "Ride", "VirtualRide", "GravelRide",
    "MountainBikeRide", "EBikeRide", "Velomobile", "Handcycle",
}


class StravaClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    # ── OAuth ────────────────────────────────────────────

    def get_authorization_url(self) -> str:
        """Build the URL to send the user to Strava's consent page."""
        params = urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read",
        })
        return f"{STRAVA_OAUTH}/authorize?{params}"

    def exchange_token(self, code: str) -> dict:
        """Exchange an authorization code for access + refresh tokens."""
        response = requests.post(f"{STRAVA_OAUTH}/token", data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        response.raise_for_status()
        return response.json()

    def refresh_token(self, refresh_token: str) -> dict:
        """Get a new access token using a refresh token."""
        response = requests.post(f"{STRAVA_OAUTH}/token", data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        response.raise_for_status()
        return response.json()

    def ensure_valid_token(self, token_data: dict) -> dict:
        """Check if token is expired, refresh if needed."""
        import time
        now = int(time.time())
        if token_data["expires_at"] > now + 60:
            return token_data  # still valid

        refreshed = self.refresh_token(token_data["refresh_token"])
        token_data["access_token"] = refreshed["access_token"]
        token_data["refresh_token"] = refreshed["refresh_token"]
        token_data["expires_at"] = refreshed["expires_at"]
        return token_data

    # ── Activities ───────────────────────────────────────

    def get_activities(self, access_token: str, after: int, before: int) -> list:
        """
        Fetch athlete activities within a date range.
        Automatically paginates (Strava max 200 per page).
        """
        activities = []
        page = 1

        while page <= 5:  # safety limit
            response = requests.get(
                f"{STRAVA_API}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "after": after,
                    "before": before,
                    "page": page,
                    "per_page": 100,
                },
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            activities.extend(data)

            if len(data) < 100:
                break
            page += 1

        return activities


def filter_cycling_activities(activities: list) -> list:
    """Filter to cycling only and extract relevant fields."""
    result = []
    for a in activities:
        sport = a.get("sport_type") or a.get("type", "")
        if sport not in CYCLING_TYPES:
            continue

        moving_time = a.get("moving_time", 0)
        distance = a.get("distance", 0)

        result.append({
            "id": a["id"],
            "name": a.get("name", "Ride"),
            "type": sport,
            "date": a.get("start_date_local", ""),
            "moving_time_seconds": moving_time,
            "moving_time_hours": round(moving_time / 3600, 2),
            "distance_km": round(distance / 1000, 1),
            "average_watts": a.get("average_watts"),
            "kilojoules": a.get("kilojoules"),
        })

    return result
