"""
Run: Right-click → Run 'test_recommender'
"""

from recommender import (
    recommend, suggest_sachet_size, calculate_fuelable_hours,
    calculate_calories, build_weekly_breakdown, ANALYSIS_WINDOW_DAYS,
    MIN_SACHETS_PER_QUARTER, MAX_SACHETS_PER_QUARTER,
)
from datetime import datetime, timedelta


def make_ride(hours, watts=None, days_ago=0, kj=None):
    dt = datetime.now() - timedelta(days=days_ago)
    if kj is None and watts:
        kj = watts * hours * 3.6
    return {
        "id": 1,
        "name": f"Ride {hours}h",
        "type": "Ride",
        "date": dt.isoformat(),
        "moving_time_seconds": int(hours * 3600),
        "moving_time_hours": hours,
        "distance_km": round(hours * 28, 1),
        "average_watts": watts,
        "kilojoules": kj,
    }


def test_config():
    print("\n── Config ──\n")
    assert ANALYSIS_WINDOW_DAYS == 90, "Window should be 90 days"
    print(f"  ✓ Analysis window = {ANALYSIS_WINDOW_DAYS} days")
    assert MIN_SACHETS_PER_QUARTER == 36
    print(f"  ✓ Min sachets/quarter = {MIN_SACHETS_PER_QUARTER}")


def test_sachet_size():
    print("\n── Sachet Size ──\n")
    assert suggest_sachet_size([]) == 60
    print("  ✓ Empty → 60g")
    assert suggest_sachet_size([make_ride(1.5), make_ride(2.0)]) == 60
    print("  ✓ Moderate rides → 60g")
    assert suggest_sachet_size([make_ride(3.0), make_ride(3.5)]) == 90
    print("  ✓ Long rides → 90g")
    assert suggest_sachet_size([make_ride(1.5, 220), make_ride(2.0, 210)]) == 90
    print("  ✓ High power → 90g")


def test_fuelable_hours():
    print("\n── Fuelable Hours ──\n")
    assert calculate_fuelable_hours([make_ride(0.5)]) == 0
    print("  ✓ 30min ride → 0h")
    result = calculate_fuelable_hours([make_ride(1.5)])
    assert abs(result - 1.0) < 0.01
    print("  ✓ 1.5h ride → 1.0h")
    result = calculate_fuelable_hours([make_ride(3.0)])
    assert abs(result - 2.5) < 0.01
    print("  ✓ 3h ride → 2.5h")


def test_calories():
    print("\n── Calories ──\n")
    rides = [make_ride(2.0, watts=200, kj=1440)]
    cal = calculate_calories(rides)
    assert cal["total_calories"] == 1440
    print(f"  ✓ Power ride: {cal['total_calories']} kcal from kJ")
    assert cal["rides_with_power_data"] == 1
    print("  ✓ Correctly counts power data rides")

    rides_no_power = [make_ride(2.0)]
    cal2 = calculate_calories(rides_no_power)
    assert cal2["total_calories"] == 1000  # 2h * 500
    print(f"  ✓ Estimated ride: {cal2['total_calories']} kcal (500/h)")

    assert cal["avg_calories_per_ride"] == 1440
    print(f"  ✓ Avg per ride calculated")
    assert cal["avg_calories_per_week"] > 0
    print(f"  ✓ Avg per week calculated")


def test_weekly_breakdown():
    print("\n── Weekly Breakdown ──\n")
    rides = [make_ride(2.0, days_ago=i * 2) for i in range(10)]
    weeks = build_weekly_breakdown(rides)
    assert len(weeks) > 0
    print(f"  ✓ Generated {len(weeks)} weeks of data")
    assert all(w["hours"] > 0 for w in weeks)
    print("  ✓ All weeks have hours > 0")
    assert weeks[0]["week_start"] <= weeks[-1]["week_start"]
    print("  ✓ Sorted chronologically")


def test_quarterly_recommendation():
    print("\n── Quarterly Recommendation ──\n")

    # 4 rides/week for 12 weeks = ~48 rides at 1.5h each
    rides = [make_ride(1.5, days_ago=i * 2) for i in range(48)]
    result = recommend(rides, sachet_size=60, apply_seasonal=False)

    r = result["recommendation"]
    s = result["savings"]
    p = result["profile"]

    assert p["window_days"] == 90
    print(f"  ✓ Window = 90 days")

    assert r["sachet_size"] == 60
    print(f"  ✓ Uses 60g sachet")

    assert MIN_SACHETS_PER_QUARTER <= r["recommended_sachets"] <= MAX_SACHETS_PER_QUARTER
    print(f"  ✓ Recommends {r['recommended_sachets']} sachets/quarter (within bounds)")

    assert r["monthly_equivalent"] > 0
    print(f"  ✓ Monthly equivalent = {r['monthly_equivalent']}")

    assert s["quarterly_cost_carb0"] > 0
    print(f"  ✓ Quarterly cost = €{s['quarterly_cost_carb0']}")

    assert s["annual_savings"] > 0
    print(f"  ✓ Annual savings = €{s['annual_savings']}")

    assert "calories" in result
    print(f"  ✓ Calorie data included ({result['calories']['total_calories']} kcal)")

    assert "weekly_breakdown" in result
    print(f"  ✓ Weekly breakdown included ({len(result['weekly_breakdown'])} weeks)")

    assert p["avg_watts"] is None  # no power data in test rides
    print("  ✓ Avg watts = None (no power data)")

    print(f"\n  → Rider: {p['weekly_hours']}h/week, {p['total_rides']} rides")
    print(f"  → Box: {r['recommended_sachets']} × 60g sachets/quarter")
    print(f"  → Cost: €{s['quarterly_cost_carb0']}/quarter, saves €{s['annual_savings']}/year")


def test_zero_activity():
    print("\n── Zero Activity ──\n")
    result = recommend([], sachet_size=60, apply_seasonal=False)
    assert result["recommendation"]["recommended_sachets"] == MIN_SACHETS_PER_QUARTER
    print(f"  ✓ Zero rides → minimum box ({MIN_SACHETS_PER_QUARTER} sachets)")


def test_prices():
    print("\n── Prices ──\n")
    r60 = recommend([], sachet_size=60)
    assert r60["savings"]["price_per_sachet"] == 0.80
    print("  ✓ 60g = €0.80")
    r90 = recommend([], sachet_size=90)
    assert r90["savings"]["price_per_sachet"] == 1.05
    print("  ✓ 90g = €1.05")
    assert r60["savings"]["competitor_price"] == 2.50
    print("  ✓ Competitor avg = €2.50")


if __name__ == "__main__":
    test_config()
    test_sachet_size()
    test_fuelable_hours()
    test_calories()
    test_weekly_breakdown()
    test_quarterly_recommendation()
    test_zero_activity()
    test_prices()

    print("\n" + "═" * 40)
    print("  All tests passed ✓")
    print("═" * 40 + "\n")
