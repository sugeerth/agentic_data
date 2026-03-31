"""Tests for VoyageAI tools and agents."""

import json
import pytest
from tools.flight_tools import search_flights, compare_flight_prices
from tools.hotel_tools import search_hotels, compare_hotel_prices
from tools.activity_tools import search_activities, get_restaurant_recommendations
from tools.weather_tools import get_weather_forecast, get_best_travel_months
from tools.budget_tools import calculate_trip_budget, optimize_budget, get_currency_info


class TestFlightTools:
    def test_search_flights_returns_results(self):
        result = search_flights.invoke({
            "origin": "New York",
            "destination": "Tokyo",
            "departure_date": "2025-06-01",
            "return_date": "2025-06-07",
            "passengers": 1,
        })
        assert "Found" in result
        assert "Option 1" in result
        assert "google.com/travel/flights" in result

    def test_search_flights_domestic(self):
        result = search_flights.invoke({
            "origin": "New York",
            "destination": "Los Angeles",
            "departure_date": "2025-06-01",
            "return_date": "2025-06-05",
        })
        assert "Found" in result
        assert "JFK" in result or "LAX" in result

    def test_compare_prices(self):
        result = compare_flight_prices.invoke({
            "origin": "London",
            "destination": "Paris",
            "date": "2025-06-01",
        })
        assert "Google Flights" in result
        assert "Skyscanner" in result
        assert "Kayak" in result


class TestHotelTools:
    def test_search_hotels_known_city(self):
        result = search_hotels.invoke({
            "destination": "Tokyo",
            "check_in": "2025-06-01",
            "check_out": "2025-06-07",
            "guests": 2,
            "max_price": 300,
        })
        assert "Found" in result
        assert "booking.com" in result

    def test_search_hotels_unknown_city(self):
        result = search_hotels.invoke({
            "destination": "Reykjavik",
            "check_in": "2025-06-01",
            "check_out": "2025-06-05",
        })
        assert "Found" in result or "Reykjavik" in result

    def test_compare_hotel_prices(self):
        result = compare_hotel_prices.invoke({
            "hotel_name": "Park Hyatt Tokyo",
            "destination": "Tokyo",
            "check_in": "2025-06-01",
            "check_out": "2025-06-07",
        })
        assert "Booking.com" in result
        assert "Expedia" in result


class TestActivityTools:
    def test_search_activities_known_city(self):
        result = search_activities.invoke({
            "destination": "Tokyo",
            "categories": "all",
            "max_budget": 100,
        })
        assert "Tokyo" in result
        assert "Tsukiji" in result or "Meiji" in result or "activities" in result.lower()

    def test_search_activities_by_category(self):
        result = search_activities.invoke({
            "destination": "Paris",
            "categories": "Food & Drink",
            "max_budget": 50,
        })
        assert "Paris" in result

    def test_restaurant_recommendations(self):
        result = get_restaurant_recommendations.invoke({
            "destination": "Barcelona",
            "cuisine_type": "local",
            "budget_level": "medium",
        })
        assert "Barcelona" in result
        assert "google.com/maps" in result


class TestWeatherTools:
    def test_get_forecast(self):
        result = get_weather_forecast.invoke({
            "city": "Tokyo",
            "start_date": "2025-06-01",
            "end_date": "2025-06-03",
        })
        # May get real data or error depending on API availability
        assert "Tokyo" in result or "weather" in result.lower() or "Error" in result

    def test_best_travel_months(self):
        result = get_best_travel_months.invoke({"city": "Bangkok"})
        assert "Bangkok" in result
        assert "Best months" in result or "best" in result.lower()


class TestBudgetTools:
    def test_calculate_budget(self):
        result = calculate_trip_budget.invoke({
            "destination": "Tokyo",
            "num_days": 7,
            "num_travelers": 1,
            "flight_cost": 800,
            "hotel_cost_per_night": 120,
            "travel_style": "mid",
        })
        assert "Budget" in result
        assert "Tokyo" in result
        assert "$" in result

    def test_optimize_budget(self):
        result = optimize_budget.invoke({
            "total_budget": 3000,
            "destination": "Paris",
            "num_days": 5,
            "num_travelers": 2,
            "priorities": "food",
        })
        assert "Paris" in result
        assert "Food" in result or "food" in result

    def test_currency_info(self):
        result = get_currency_info.invoke({"destination": "Tokyo"})
        assert "JPY" in result
        assert "Currency" in result or "currency" in result


class TestWorkflow:
    def test_full_workflow_no_llm(self):
        """Test full workflow produces output without any LLM configured."""
        import os
        # Ensure no LLM keys are set for this test
        old_env = {k: os.environ.pop(k, None) for k in ["GROQ_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"]}
        try:
            from graph.workflow import run_travel_planner
            result = run_travel_planner(
                destination="Tokyo",
                origin="New York",
                start_date="2026-05-01",
                end_date="2026-05-08",
                budget=3000,
                travelers=1,
            )
            assert len(result) > 1000, "Itinerary should be substantial"
            assert "Tokyo" in result
            assert "Flight" in result or "flight" in result
            assert "Hotel" in result or "hotel" in result
        finally:
            for k, v in old_env.items():
                if v is not None:
                    os.environ[k] = v

    def test_workflow_callback(self):
        """Test that workflow fires callbacks for each agent."""
        from graph.workflow import run_travel_planner
        agents_seen = []

        def cb(name, status, msg):
            agents_seen.append(name)

        run_travel_planner(
            destination="Paris",
            origin="London",
            start_date="2026-06-01",
            end_date="2026-06-05",
            budget=2000,
            callback=cb,
        )
        assert len(agents_seen) >= 6, f"Should see 6 agents, got {len(agents_seen)}: {agents_seen}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
