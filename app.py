"""
Carb0 — Strava-Connected Cycling Nutrition

Run locally:   python app.py
Run tests:     python test_recommender.py
Deploy:        Push to GitHub → connect to Railway
"""

import os
import time
import stripe
from flask import Flask, redirect, request, jsonify, render_template, session, url_for
from dotenv import load_dotenv

from strava_client import StravaClient, filter_cycling_activities
from recommender import recommend, ANALYSIS_WINDOW_DAYS, SACHET_SIZES
from waitlist import add_email, get_count

# ── Load config ─────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

PORT = int(os.getenv("PORT", 3000))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT}")
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"

# ── Stripe ──────────────────────────────────────────────────
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

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


@app.route("/order")
def order_direct():
    """Direct order page — no Strava required."""
    return render_template("order.html")


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
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
        "waitlist": get_count(),
    })


# ═══════════════════════════════════════════════════════════
#  STRIPE CHECKOUT
# ═══════════════════════════════════════════════════════════

@app.route("/api/checkout", methods=["POST"])
def create_checkout():
    """
    Create a Stripe Checkout session for a quarterly box.

    Expects JSON:
        sachet_size:  60 or 90
        quantity:     number of sachets (36-120)
        athlete_id:   Strava athlete ID (optional, for tracking)
    """
    data = request.get_json() or {}

    sachet_size = data.get("sachet_size", 60)
    quantity = data.get("quantity", 36)
    athlete_id = data.get("athlete_id")

    # Validate
    if sachet_size not in SACHET_SIZES:
        return jsonify({"error": "Invalid sachet size."}), 400

    quantity = max(12, min(120, int(quantity)))
    sachet = SACHET_SIZES[sachet_size]

    # Price in cents for Stripe
    unit_price_cents = int(sachet["price_eur"] * 100)
    total_cents = unit_price_cents * quantity

    try:
        session_obj = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": unit_price_cents,
                    "product_data": {
                        "name": f"Carb0 — {sachet['label']}",
                        "description": f"Quarterly box: {quantity} × {sachet_size}g sachets. Maltodextrin:fructose 1:0.8.",
                    },
                },
                "quantity": quantity,
            }],
            metadata={
                "sachet_size": str(sachet_size),
                "quantity": str(quantity),
                "athlete_id": str(athlete_id) if athlete_id else "",
            },
            success_url=f"{BASE_URL}/order/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/dashboard?athlete={athlete_id or ''}",
        )

        return jsonify({"checkout_url": session_obj.url})

    except Exception as e:
        print(f"Stripe error: {e}")
        return jsonify({"error": "Checkout failed. Try again."}), 500


@app.route("/order/success")
def order_success():
    """Post-checkout confirmation page."""
    session_id = request.args.get("session_id")

    order_info = None
    if session_id:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            order_info = {
                "email": checkout.customer_details.email if checkout.customer_details else None,
                "amount": f"€{checkout.amount_total / 100:.2f}",
                "sachet_size": checkout.metadata.get("sachet_size", ""),
                "quantity": checkout.metadata.get("quantity", ""),
            }
        except Exception:
            pass

    return render_template("success.html", order=order_info)


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
