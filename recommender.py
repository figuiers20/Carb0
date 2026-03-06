"""
Carb0 Recommendation Engine

Takes cycling activity data and produces a monthly sachet recommendation.

Logic:
  1. Sum cycling hours over last 28 days
  2. Only count rides >= 45 min (short rides don't need fueling)
  3. Subtract 30 min glycogen buffer per ride
  4. Extrapolate to monthly rate
  5. Apply seasonal adjustment
  6. Convert to sachet count
"""

import math
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────

ANALYSIS_WINDOW_DAYS = 28
MIN_RIDE_DURATION_MINUTES = 45
GLYCOGEN_BUFFER_MINUTES = 30
DEFAULT_CARBS_PER_HOUR = 60

SACHET_SIZES = {
    60: {"grams": 60, "price_eur": 0.85, "label": "60g Standard"},
    90: {"grams": 90, "price_eur": 1.10, "label": "90g High Output"},
}

COMPETITOR_AVG_PRICE = 2.50
MIN_SACHETS_PER_BOX = 12
MAX_SACHETS_PER_BOX = 40

# European cycling volume patterns
SEASONAL_FACTORS = {
    1: 0.60, 2: 0.65, 3: 0.80, 4: 0.95, 5: 1.10, 6: 1.15,
    7: 1.15, 8: 1.10, 9: 1.00, 10: 0.85, 11: 0.70, 12: 0.60,
}


# ── Core Logic ─────────────────────────────────────────────

def suggest_sachet_size(activities: list) -> int:
    """
    Auto-detect sachet size based on riding profile.
    - Avg ride >= 2.5h OR avg power >= 200W → 90g
    - Otherwise → 60g
    """
    fuelable = [a for a in activities
                if a["moving_time_seconds"] >= MIN_RIDE_DURATION_MINUTES * 60]

    if not fuelable:
        return 60

    avg_duration = sum(a["moving_time_hours"] for a in fuelable) / len(fuelable)

    rides_with_power = [a for a in fuelable if a.get("average_watts")]
    avg_watts = (
        sum(a["average_watts"] for a in rides_with_power) / len(rides_with_power)
        if rides_with_power else None
    )

    if avg_duration >= 2.5 or (avg_watts and avg_watts >= 200):
        return 90

    return 60


def calculate_fuelable_hours(activities: list) -> float:
    """
    Total hours that need external fueling.
    Only rides >= 45 min, minus 30 min glycogen buffer each.
    """
    buffer_seconds = GLYCOGEN_BUFFER_MINUTES * 60
    total = 0.0

    for a in activities:
        if a["moving_time_seconds"] < MIN_RIDE_DURATION_MINUTES * 60:
            continue
        fuelable = max(0, a["moving_time_seconds"] - buffer_seconds)
        total += fuelable / 3600

    return total


def get_next_ship_date() -> str:
    """Ship on the 1st of next month if past the 25th."""
    now = datetime.now()
    if now.day > 25:
        if now.month == 12:
            return datetime(now.year + 1, 1, 1).strftime("%Y-%m-%d")
        return datetime(now.year, now.month + 1, 1).strftime("%Y-%m-%d")
    return datetime(now.year, now.month, 1).strftime("%Y-%m-%d")


def get_modify_deadline() -> str:
    """5 days before ship date."""
    ship = datetime.strptime(get_next_ship_date(), "%Y-%m-%d")
    deadline = ship - timedelta(days=5)
    return deadline.strftime("%Y-%m-%d")


def recommend(activities: list, sachet_size: int = None,
              carbs_per_hour: int = None, apply_seasonal: bool = True) -> dict:
    """
    Build the full monthly recommendation.

    Parameters:
        activities:     list of filtered cycling activities
        sachet_size:    60 or 90 (None = auto-detect)
        carbs_per_hour: override carb rate (default 60)
        apply_seasonal: apply seasonal volume adjustment

    Returns:
        dict with profile, recommendation, savings, delivery
    """

    # ── Defaults ──
    if sachet_size is None:
        sachet_size = suggest_sachet_size(activities)
    if carbs_per_hour is None:
        carbs_per_hour = DEFAULT_CARBS_PER_HOUR

    sachet = SACHET_SIZES[sachet_size]

    # ── Ride analysis ──
    fuelable_rides = [a for a in activities
                      if a["moving_time_seconds"] >= MIN_RIDE_DURATION_MINUTES * 60]

    total_hours = sum(a["moving_time_hours"] for a in activities)
    fuelable_hours = calculate_fuelable_hours(activities)
    total_km = sum(a["distance_km"] for a in activities)

    weeks = ANALYSIS_WINDOW_DAYS / 7
    weekly_hours = round(total_hours / weeks, 1) if weeks else 0
    weekly_rides = round(len(activities) / weeks, 1) if weeks else 0

    # ── Monthly extrapolation ──
    monthly_fuelable = (fuelable_hours / ANALYSIS_WINDOW_DAYS) * 30

    # ── Seasonal adjustment ──
    current_month = datetime.now().month
    seasonal_factor = SEASONAL_FACTORS[current_month] if apply_seasonal else 1.0
    adjusted_monthly = monthly_fuelable * seasonal_factor

    # ── Sachet count ──
    total_grams = adjusted_monthly * carbs_per_hour
    raw_sachets = total_grams / sachet["grams"]

    recommended = math.ceil(raw_sachets)
    recommended = max(recommended, MIN_SACHETS_PER_BOX)
    recommended = min(recommended, MAX_SACHETS_PER_BOX)

    if fuelable_hours == 0:
        recommended = MIN_SACHETS_PER_BOX

    # ── Savings ──
    monthly_carb0 = round(recommended * sachet["price_eur"], 2)
    monthly_competitor = round(recommended * COMPETITOR_AVG_PRICE, 2)
    monthly_savings = round(monthly_competitor - monthly_carb0, 2)
    annual_savings = round(monthly_savings * 12)
    savings_pct = round((monthly_savings / monthly_competitor) * 100) if monthly_competitor else 0

    return {
        "profile": {
            "window_days": ANALYSIS_WINDOW_DAYS,
            "total_rides": len(activities),
            "fuelable_rides": len(fuelable_rides),
            "total_hours": round(total_hours, 1),
            "fuelable_hours": round(fuelable_hours, 1),
            "total_km": round(total_km),
            "weekly_hours": weekly_hours,
            "weekly_rides": weekly_rides,
        },
        "recommendation": {
            "sachet_size": sachet_size,
            "sachet_label": sachet["label"],
            "carbs_per_hour": carbs_per_hour,
            "monthly_fuelable_hours": round(monthly_fuelable, 1),
            "seasonal_factor": seasonal_factor,
            "adjusted_monthly_hours": round(adjusted_monthly, 1),
            "total_grams_needed": round(total_grams),
            "raw_sachets": round(raw_sachets, 1),
            "recommended_sachets": recommended,
        },
        "savings": {
            "price_per_sachet": sachet["price_eur"],
            "competitor_price": COMPETITOR_AVG_PRICE,
            "monthly_cost_carb0": monthly_carb0,
            "monthly_cost_competitor": monthly_competitor,
            "monthly_savings": monthly_savings,
            "annual_savings": annual_savings,
            "savings_percent": savings_pct,
        },
        "delivery": {
            "next_ship_date": get_next_ship_date(),
            "modify_until": get_modify_deadline(),
        },
    }
