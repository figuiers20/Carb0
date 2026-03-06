"""
Run this to test the recommendation engine:
    Right-click → Run 'test_recommender'
"""

from recommender import recommend, suggest_sachet_size, calculate_fuelable_hours


def make_ride(hours, watts=None):
    """Create a fake ride activity for testing."""
    return {
        "id": 1,
        "name": f"Test Ride {hours}h",
        "type": "Ride",
        "date": "2026-03-01T08:00:00Z",
        "moving_time_seconds": int(hours * 3600),
        "moving_time_hours": hours,
        "distance_km": round(hours * 28, 1),
        "average_watts": watts,
        "kilojoules": watts * hours * 3.6 if watts else None,
    }


def test_sachet_size_suggestion():
    print("\n── Sachet Size Suggestion ──\n")

    assert suggest_sachet_size([]) == 60, "Empty → 60g"
    print("  ✓ Empty activities → 60g")

    assert suggest_sachet_size([make_ride(0.5)]) == 60, "Short rides → 60g"
    print("  ✓ Short rides → 60g")

    assert suggest_sachet_size([make_ride(1.5), make_ride(2.0)]) == 60
    print("  ✓ Moderate rides → 60g")

    assert suggest_sachet_size([make_ride(3.0), make_ride(3.5)]) == 90
    print("  ✓ Long rides (avg >2.5h) → 90g")

    assert suggest_sachet_size([make_ride(1.5, 220), make_ride(2.0, 210)]) == 90
    print("  ✓ High power (avg >200W) → 90g")


def test_fuelable_hours():
    print("\n── Fuelable Hours ──\n")

    assert calculate_fuelable_hours([]) == 0
    print("  ✓ No activities → 0h")

    assert calculate_fuelable_hours([make_ride(0.5)]) == 0
    print("  ✓ 30min ride → 0h (below 45min threshold)")

    result = calculate_fuelable_hours([make_ride(1.5)])
    assert abs(result - 1.0) < 0.01
    print("  ✓ 1.5h ride → 1.0h (minus 30min glycogen buffer)")

    result = calculate_fuelable_hours([make_ride(3.0)])
    assert abs(result - 2.5) < 0.01
    print("  ✓ 3h ride → 2.5h")


def test_full_recommendation():
    print("\n── Full Recommendation ──\n")

    # 8h/week rider: 16 rides × 2h over 28 days
    rides = [make_ride(2.0) for _ in range(16)]
    result = recommend(rides, sachet_size=60, apply_seasonal=False)

    r = result["recommendation"]
    s = result["savings"]
    p = result["profile"]

    assert p["total_rides"] == 16
    print("  ✓ Counts all 16 rides")

    assert p["total_hours"] == 32.0
    print("  ✓ Total hours = 32")

    assert r["sachet_size"] == 60
    print("  ✓ Uses specified 60g sachet")

    assert 12 <= r["recommended_sachets"] <= 40
    print(f"  ✓ Recommends {r['recommended_sachets']} sachets (within box limits)")

    assert s["annual_savings"] > 0
    print(f"  ✓ Annual savings = €{s['annual_savings']}")

    assert s["savings_percent"] > 50
    print(f"  ✓ Savings = {s['savings_percent']}% vs competitors")

    print(f"\n  → 8h/week rider: {r['recommended_sachets']} × 60g sachets")
    print(f"  → €{s['monthly_cost_carb0']}/month, saves €{s['annual_savings']}/year")


def test_zero_activity():
    print("\n── Zero Activity ──\n")

    result = recommend([], sachet_size=60, apply_seasonal=False)
    assert result["recommendation"]["recommended_sachets"] == 12
    print("  ✓ Zero rides → minimum box (12 sachets)")


def test_prices():
    print("\n── Prices ──\n")

    r60 = recommend([], sachet_size=60)
    assert r60["savings"]["price_per_sachet"] == 0.85
    print("  ✓ 60g = €0.85")

    r90 = recommend([], sachet_size=90)
    assert r90["savings"]["price_per_sachet"] == 1.10
    print("  ✓ 90g = €1.10")

    assert r60["savings"]["competitor_price"] == 2.50
    print("  ✓ Competitor avg = €2.50")


if __name__ == "__main__":
    test_sachet_size_suggestion()
    test_fuelable_hours()
    test_full_recommendation()
    test_zero_activity()
    test_prices()

    print("\n" + "═" * 40)
    print("  All tests passed ✓")
    print("═" * 40 + "\n")
