"""
Carb0 Recommendation Engine

Takes cycling activity data and produces a quarterly sachet recommendation.

Logic:
  1. Analyze 90 days of riding data (one quarter)
  2. Only count rides >= 45 min for fueling
  3. Subtract 30 min glycogen buffer per ride
  4. Calculate calories from kilojoules (1 kJ ≈ 1 kcal)
  5. Build weekly breakdown for trend display
  6. Apply seasonal adjustment
  7. Convert to quarterly sachet count
"""

import math
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────

ANALYSIS_WINDOW_DAYS = 90
MIN_RIDE_DURATION_MINUTES = 45
GLYCOGEN_BUFFER_MINUTES = 30
DEFAULT_CARBS_PER_HOUR = 60

SACHET_SIZES = {
    60: {"grams": 60, "price_eur": 0.80, "label": "60g Standard"},
    90: {"grams": 90, "price_eur": 1.05, "label": "90g High Output"},
}

COMPETITOR_AVG_PRICE = 2.50
MIN_SACHETS_PER_QUARTER = 12
MAX_SACHETS_PER_QUARTER = 120

SEASONAL_FACTORS = {
    1: 0.60, 2: 0.65, 3: 0.80, 4: 0.95, 5: 1.10, 6: 1.15,
    7: 1.15, 8: 1.10, 9: 1.00, 10: 0.85, 11: 0.70, 12: 0.60,
}


# ── Core Logic ─────────────────────────────────────────────

def suggest_sachet_size(activities: list) -> int:
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
    buffer_seconds = GLYCOGEN_BUFFER_MINUTES * 60
    total = 0.0
    for a in activities:
        if a["moving_time_seconds"] < MIN_RIDE_DURATION_MINUTES * 60:
            continue
        fuelable = max(0, a["moving_time_seconds"] - buffer_seconds)
        total += fuelable / 3600
    return total


def calculate_calories(activities: list) -> dict:
    """
    Calculate calorie stats from ride data.
    Strava's kilojoules ≈ kilocalories (due to ~25% human efficiency).
    Rides without power: estimate 500 kcal/hour at moderate intensity.
    """
    total_calories = 0.0
    for a in activities:
        kj = a.get("kilojoules")
        if kj and kj > 0:
            total_calories += kj
        else:
            total_calories += a["moving_time_hours"] * 500

    weeks = ANALYSIS_WINDOW_DAYS / 7
    return {
        "total_calories": round(total_calories),
        "avg_calories_per_week": round(total_calories / weeks) if weeks else 0,
        "avg_calories_per_ride": round(total_calories / len(activities)) if activities else 0,
        "rides_with_power_data": sum(1 for a in activities if a.get("kilojoules") and a["kilojoules"] > 0),
        "total_rides": len(activities),
    }


def build_weekly_breakdown(activities: list) -> list:
    """
    Group activities into ISO weeks, return chronological weekly summaries.
    """
    weekly = defaultdict(lambda: {
        "hours": 0, "km": 0, "rides": 0, "calories": 0, "fuelable_hours": 0,
    })
    buffer_seconds = GLYCOGEN_BUFFER_MINUTES * 60

    for a in activities:
        date_str = a.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime("%Y-%m-%d")

        weekly[week_key]["hours"] += a["moving_time_hours"]
        weekly[week_key]["km"] += a["distance_km"]
        weekly[week_key]["rides"] += 1

        kj = a.get("kilojoules")
        if kj and kj > 0:
            weekly[week_key]["calories"] += kj
        else:
            weekly[week_key]["calories"] += a["moving_time_hours"] * 500

        if a["moving_time_seconds"] >= MIN_RIDE_DURATION_MINUTES * 60:
            fuelable = max(0, a["moving_time_seconds"] - buffer_seconds) / 3600
            weekly[week_key]["fuelable_hours"] += fuelable

    result = []
    for week_key in sorted(weekly.keys()):
        w = weekly[week_key]
        result.append({
            "week_start": week_key,
            "hours": round(w["hours"], 1),
            "km": round(w["km"]),
            "rides": w["rides"],
            "calories": round(w["calories"]),
            "fuelable_hours": round(w["fuelable_hours"], 1),
        })
    return result


def get_next_ship_date() -> str:
    now = datetime.now()
    quarter_months = [1, 4, 7, 10]
    for m in quarter_months:
        ship = datetime(now.year, m, 1)
        if ship > now + timedelta(days=5):
            return ship.strftime("%Y-%m-%d")
    return datetime(now.year + 1, 1, 1).strftime("%Y-%m-%d")


def get_modify_deadline() -> str:
    ship = datetime.strptime(get_next_ship_date(), "%Y-%m-%d")
    return (ship - timedelta(days=7)).strftime("%Y-%m-%d")


def recommend(activities: list, sachet_size: int = None,
              carbs_per_hour: int = None, apply_seasonal: bool = True) -> dict:

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
    weekly_km = round(total_km / weeks, 1) if weeks else 0

    # ── Calories ──
    calorie_stats = calculate_calories(activities)

    # ── Weekly breakdown ──
    weekly_breakdown = build_weekly_breakdown(activities)

    # ── Quarterly extrapolation ──
    quarterly_fuelable = (fuelable_hours / ANALYSIS_WINDOW_DAYS) * 90

    # ── Seasonal adjustment ──
    current_month = datetime.now().month
    seasonal_factor = SEASONAL_FACTORS[current_month] if apply_seasonal else 1.0
    adjusted_quarterly = quarterly_fuelable * seasonal_factor

    # ── Sachet count (quarterly) ──
    total_grams = adjusted_quarterly * carbs_per_hour
    raw_sachets = total_grams / sachet["grams"]

    recommended = math.ceil(raw_sachets)
    recommended = max(recommended, MIN_SACHETS_PER_QUARTER)
    recommended = min(recommended, MAX_SACHETS_PER_QUARTER)

    if fuelable_hours == 0:
        recommended = MIN_SACHETS_PER_QUARTER

    monthly_sachets = round(recommended / 3, 1)

    # ── Savings (quarterly) ──
    quarterly_carb0 = round(recommended * sachet["price_eur"], 2)
    quarterly_competitor = round(recommended * COMPETITOR_AVG_PRICE, 2)
    quarterly_savings = round(quarterly_competitor - quarterly_carb0, 2)
    annual_savings = round(quarterly_savings * 4)
    savings_pct = round((quarterly_savings / quarterly_competitor) * 100) if quarterly_competitor else 0

    # ── Average watts ──
    rides_with_power = [a for a in activities if a.get("average_watts")]
    avg_watts = (
        round(sum(a["average_watts"] for a in rides_with_power) / len(rides_with_power))
        if rides_with_power else None
    )

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
            "weekly_km": weekly_km,
            "avg_watts": avg_watts,
        },
        "calories": calorie_stats,
        "weekly_breakdown": weekly_breakdown,
        "recommendation": {
            "sachet_size": sachet_size,
            "sachet_label": sachet["label"],
            "carbs_per_hour": carbs_per_hour,
            "quarterly_fuelable_hours": round(quarterly_fuelable, 1),
            "seasonal_factor": seasonal_factor,
            "adjusted_quarterly_hours": round(adjusted_quarterly, 1),
            "total_grams_needed": round(total_grams),
            "raw_sachets": round(raw_sachets, 1),
            "recommended_sachets": recommended,
            "monthly_equivalent": monthly_sachets,
        },
        "savings": {
            "price_per_sachet": sachet["price_eur"],
            "competitor_price": COMPETITOR_AVG_PRICE,
            "quarterly_cost_carb0": quarterly_carb0,
            "quarterly_cost_competitor": quarterly_competitor,
            "quarterly_savings": quarterly_savings,
            "annual_savings": annual_savings,
            "savings_percent": savings_pct,
        },
        "delivery": {
            "next_ship_date": get_next_ship_date(),
            "modify_until": get_modify_deadline(),
        },
    }
