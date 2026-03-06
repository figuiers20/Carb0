"""
Carb0 — Strava-Connected Cycling Nutrition

Run locally:   python app.py
Run tests:     python test_recommender.py
Deploy:        Push to GitHub → connect to Railway
"""

import os
import time
from flask import Flask, redirect, request, jsonify, render_template, session, url_for
from dotenv import load_dotenv

from strava_client import StravaClient, filter_cycling_activities
from recommender import recommend, ANALYSIS_WINDOW_DAYS
from waitlist import add_email, get_count

# ── Load config ─────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

PORT = int(os.getenv("PORT", 3000))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT}")
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"

# ── Strava client ───────────────────────────────────────────
strava = StravaClient(
    client_id=os.getenv("STRAVA_CLIENT_ID", ""),
    client_secret=os.getenv("STRAVA_CLIENT_SECRET", ""),
    redirect_uri=f"{BASE_URL}/auth/strava/callback",
)

# ── Token storage (in-memory — resets on redeploy) ──────────
tokens = {}


# ═══════════════════════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def landing():
    """Marketing landing page."""
    return render_template("landing.html", waitlist_count=get_count())


@app.route("/dashboard")
def dashboard():
    """Strava dashboard — shows personalized recommendation."""
    athlete_id = request.args.get("athlete") or session.get("athlete_id")
    if not athlete_id or int(athlete_id) not in tokens:
        return redirect("/?error=not_connected")
    return render_template("dashboard.html", athlete_id=athlete_id)


# ═══════════════════════════════════════════════════════════
#  WAITLIST
# ═══════════════════════════════════════════════════════════

@app.route("/api/waitlist", methods=["POST"])
def api_waitlist():
    """Add email to waitlist."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Valid email required."}), 400

    entry = add_email(
        email=email,
        sachet_size=data.get("sachet_size"),
        weekly_hours=data.get("weekly_hours"),
        source=data.get("source", "landing"),
    )

    if entry is None:
        return jsonify({"status": "already_registered", "count": get_count()})

    return jsonify({"status": "ok", "count": get_count()})


# ═══════════════════════════════════════════════════════════
#  STRAVA AUTH
# ═══════════════════════════════════════════════════════════

@app.route("/auth/strava")
def auth_strava():
    """Redirect to Strava OAuth."""
    return redirect(strava.get_authorization_url())


@app.route("/auth/strava/callback")
def auth_callback():
    """Handle Strava OAuth callback."""
    error = request.args.get("error")
    if error:
        return redirect(f"/?error={error}")

    code = request.args.get("code")
    if not code:
        return redirect("/?error=no_code")

    try:
        token_data = strava.exchange_token(code)
        athlete = token_data["athlete"]
        athlete_id = athlete["id"]

        tokens[athlete_id] = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_at": token_data["expires_at"],
            "athlete": {
                "id": athlete_id,
                "firstname": athlete.get("firstname", ""),
                "lastname": athlete.get("lastname", ""),
                "profile": athlete.get("profile", ""),
            },
        }

        session["athlete_id"] = athlete_id
        return redirect(f"/dashboard?athlete={athlete_id}")

    except Exception as e:
        print(f"Auth failed: {e}")
        return redirect("/?error=auth_failed")


# ═══════════════════════════════════════════════════════════
#  RECOMMENDATION API
# ═══════════════════════════════════════════════════════════

@app.route("/api/recommendation")
def api_recommendation():
    """Fetch rides from Strava → return sachet recommendation."""
    athlete_id = request.args.get("athlete", type=int)

    if not athlete_id or athlete_id not in tokens:
        return jsonify({"error": "Not connected."}), 401

    try:
        token_data = strava.ensure_valid_token(tokens[athlete_id])
        tokens[athlete_id] = token_data

        now = int(time.time())
        window_start = now - (ANALYSIS_WINDOW_DAYS * 24 * 3600)

        raw = strava.get_activities(token_data["access_token"], window_start, now)
        cycling = filter_cycling_activities(raw)

        result = recommend(
            cycling,
            sachet_size=request.args.get("sachet_size", type=int),
            carbs_per_hour=request.args.get("carbs_per_hour", type=int),
        )

        result["athlete"] = token_data["athlete"]
        result["activities"] = [
            {"name": a["name"], "date": a["date"], "hours": a["moving_time_hours"],
             "km": a["distance_km"], "watts": a.get("average_watts"), "type": a["type"]}
            for a in cycling
        ]

        return jsonify(result)

    except Exception as e:
        print(f"Recommendation error: {e}")
        return jsonify({"error": "Failed to load."}), 500


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "strava_configured": bool(os.getenv("STRAVA_CLIENT_ID")),
        "waitlist": get_count(),
    })


# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("  ┌──────────────────────────────────────┐")
    print("  │         CARB0 — Strava Service        │")
    print("  ├──────────────────────────────────────┤")
    print(f"  │  Open: {BASE_URL}")
    print(f"  │  Strava: {os.getenv('STRAVA_CLIENT_ID', 'NOT SET')}")
    print("  │  Ctrl+C to stop                      │")
    print("  └──────────────────────────────────────┘")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=True)
