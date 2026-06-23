"""Regression tests for flight tool internals (pure logic, no network)."""

import random

from tools import flight_tools
from tools.flight_tools import search_flights, _calculate_base_price


def test_search_flights_does_not_mutate_airlines_constant():
    """search_flights must not shuffle the module-level AIRLINES pool in place.

    The domestic branch used to assign a direct reference to
    AIRLINES["domestic_us"] and then random.shuffle it, corrupting the shared
    constant for every later call. Calling the tool should leave the constant
    untouched.
    """
    before = [a["code"] for a in flight_tools.AIRLINES["domestic_us"]]
    random.seed(1)  # a seed that previously reordered the list
    search_flights.invoke({
        "origin": "New York",
        "destination": "Los Angeles",
        "departure_date": "2025-06-01",
        "return_date": "2025-06-05",
    })
    after = [a["code"] for a in flight_tools.AIRLINES["domestic_us"]]
    assert before == after, "AIRLINES['domestic_us'] was mutated in place"


def test_base_price_has_minimum_floor():
    """Base price is floored at $120 regardless of route randomness."""
    random.seed(0)
    for _ in range(50):
        price = _calculate_base_price("New York", "Los Angeles")
        assert price >= 120
