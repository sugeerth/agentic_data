"""Evaluation framework for VoyageAI travel agent quality.

Runs each agent tool independently (no LLM needed) and scores outputs
on completeness, accuracy, actionability, and data quality.
"""

import json
import time
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from tools.flight_tools import search_flights, compare_flight_prices
from tools.hotel_tools import search_hotels, compare_hotel_prices
from tools.activity_tools import search_activities, get_restaurant_recommendations
from tools.weather_tools import get_weather_forecast, get_best_travel_months
from tools.budget_tools import calculate_trip_budget, optimize_budget, get_currency_info


@dataclass
class ToolEvalResult:
    """Result of evaluating a single tool call."""
    tool_name: str
    agent: str
    input_params: dict
    output: str
    latency_ms: float
    scores: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    passed: bool = True


@dataclass
class AgentEvalResult:
    """Aggregated evaluation for one agent."""
    agent_name: str
    tool_results: list[ToolEvalResult] = field(default_factory=list)
    overall_score: float = 0.0
    latency_avg_ms: float = 0.0
    pass_rate: float = 0.0


@dataclass
class EvalReport:
    """Full evaluation report across all agents."""
    timestamp: str = ""
    destination: str = ""
    total_score: float = 0.0
    agent_results: list[AgentEvalResult] = field(default_factory=list)
    summary: str = ""


def _score_output(output: str, checks: dict) -> tuple[dict, list]:
    """Score an output string against a set of checks.

    checks: dict of check_name -> (check_fn, weight, description)
    Returns: (scores_dict, issues_list)
    """
    scores = {}
    issues = []
    for name, (check_fn, weight, desc) in checks.items():
        try:
            passed = check_fn(output)
            scores[name] = weight if passed else 0.0
            if not passed:
                issues.append(f"FAIL: {desc}")
        except Exception as e:
            scores[name] = 0.0
            issues.append(f"ERROR in {name}: {str(e)}")
    return scores, issues


def _run_tool(tool, params: dict) -> tuple[str, float]:
    """Run a tool and measure latency."""
    start = time.time()
    result = tool.invoke(params)
    latency = (time.time() - start) * 1000
    return result, latency


def evaluate_flight_agent(destination: str, origin: str, start_date: str, end_date: str) -> AgentEvalResult:
    """Evaluate the flight agent tools."""
    agent_result = AgentEvalResult(agent_name="Flight Agent")

    # Test 1: search_flights
    params = {
        "origin": origin, "destination": destination,
        "departure_date": start_date, "return_date": end_date, "passengers": 1,
    }
    output, latency = _run_tool(search_flights, params)

    checks = {
        "has_results": (lambda o: "Found" in o and "Option 1" in o, 20, "Should return flight results"),
        "has_prices": (lambda o: "$" in o, 20, "Should include prices"),
        "has_airlines": (lambda o: "Airlines" in o or "Air" in o or "airline" in o.lower(), 15, "Should mention airline names"),
        "has_booking_link": (lambda o: "google.com/travel" in o or "booking" in o.lower(), 20, "Should include booking links"),
        "has_duration": (lambda o: "h " in o and "m" in o, 15, "Should show flight duration"),
        "has_stops": (lambda o: "stop" in o.lower() or "nonstop" in o.lower(), 10, "Should indicate stops"),
    }
    scores, issues = _score_output(output, checks)
    tool_result = ToolEvalResult(
        tool_name="search_flights", agent="Flight Agent", input_params=params,
        output=output[:500], latency_ms=latency, scores=scores, issues=issues,
        passed=sum(scores.values()) >= 60,
    )
    agent_result.tool_results.append(tool_result)

    # Test 2: compare_flight_prices
    params2 = {"origin": origin, "destination": destination, "date": start_date}
    output2, latency2 = _run_tool(compare_flight_prices, params2)

    checks2 = {
        "has_platforms": (lambda o: "Google Flights" in o and "Skyscanner" in o, 40, "Should list booking platforms"),
        "has_urls": (lambda o: "https://" in o, 30, "Should include URLs"),
        "has_kayak": (lambda o: "Kayak" in o or "kayak" in o, 15, "Should include Kayak"),
        "has_tip": (lambda o: "tip" in o.lower() or "Tip" in o, 15, "Should include comparison tip"),
    }
    scores2, issues2 = _score_output(output2, checks2)
    tool_result2 = ToolEvalResult(
        tool_name="compare_flight_prices", agent="Flight Agent", input_params=params2,
        output=output2[:500], latency_ms=latency2, scores=scores2, issues=issues2,
        passed=sum(scores2.values()) >= 60,
    )
    agent_result.tool_results.append(tool_result2)

    # Aggregate
    all_scores = [sum(tr.scores.values()) for tr in agent_result.tool_results]
    agent_result.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
    agent_result.latency_avg_ms = sum(tr.latency_ms for tr in agent_result.tool_results) / len(agent_result.tool_results)
    agent_result.pass_rate = sum(1 for tr in agent_result.tool_results if tr.passed) / len(agent_result.tool_results) * 100

    return agent_result


def evaluate_hotel_agent(destination: str, start_date: str, end_date: str) -> AgentEvalResult:
    """Evaluate the hotel agent tools."""
    agent_result = AgentEvalResult(agent_name="Hotel Agent")

    params = {
        "destination": destination, "check_in": start_date,
        "check_out": end_date, "guests": 2, "max_price": 300,
    }
    output, latency = _run_tool(search_hotels, params)

    checks = {
        "has_results": (lambda o: "Found" in o, 20, "Should return hotel results"),
        "has_prices": (lambda o: "$" in o and "/night" in o, 20, "Should show nightly prices"),
        "has_ratings": (lambda o: "/5.0" in o or "reviews" in o, 15, "Should show ratings"),
        "has_amenities": (lambda o: "amenities" in o.lower() or "WiFi" in o, 15, "Should list amenities"),
        "has_booking_link": (lambda o: "booking.com" in o, 15, "Should include Booking.com link"),
        "has_area": (lambda o: "Area:" in o or "area" in o.lower(), 15, "Should show hotel area/location"),
    }
    scores, issues = _score_output(output, checks)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="search_hotels", agent="Hotel Agent", input_params=params,
        output=output[:500], latency_ms=latency, scores=scores, issues=issues,
        passed=sum(scores.values()) >= 60,
    ))

    # compare_hotel_prices
    params2 = {
        "hotel_name": "Test Hotel", "destination": destination,
        "check_in": start_date, "check_out": end_date,
    }
    output2, latency2 = _run_tool(compare_hotel_prices, params2)
    checks2 = {
        "has_platforms": (lambda o: "Booking.com" in o and "Expedia" in o, 50, "Should list platforms"),
        "has_urls": (lambda o: "https://" in o, 30, "Should include URLs"),
        "has_google": (lambda o: "Google" in o, 20, "Should include Google Hotels"),
    }
    scores2, issues2 = _score_output(output2, checks2)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="compare_hotel_prices", agent="Hotel Agent", input_params=params2,
        output=output2[:500], latency_ms=latency2, scores=scores2, issues=issues2,
        passed=sum(scores2.values()) >= 60,
    ))

    all_scores = [sum(tr.scores.values()) for tr in agent_result.tool_results]
    agent_result.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
    agent_result.latency_avg_ms = sum(tr.latency_ms for tr in agent_result.tool_results) / len(agent_result.tool_results)
    agent_result.pass_rate = sum(1 for tr in agent_result.tool_results if tr.passed) / len(agent_result.tool_results) * 100

    return agent_result


def evaluate_activity_agent(destination: str) -> AgentEvalResult:
    """Evaluate the activity agent tools."""
    agent_result = AgentEvalResult(agent_name="Activity Agent")

    params = {"destination": destination, "categories": "all", "max_budget": 100}
    output, latency = _run_tool(search_activities, params)

    checks = {
        "has_activities": (lambda o: "activities" in o.lower() or "found" in o.lower(), 15, "Should return activities"),
        "has_free": (lambda o: "FREE" in o or "free" in o or "$0" in o, 20, "Should include free activities"),
        "has_costs": (lambda o: "$" in o, 15, "Should show costs"),
        "has_ratings": (lambda o: "/5.0" in o or "rating" in o.lower(), 15, "Should show ratings"),
        "has_descriptions": (lambda o: len(o) > 200, 15, "Should have detailed descriptions"),
        "has_locations": (lambda o: "Location:" in o or "location" in o.lower(), 10, "Should show locations"),
        "has_total": (lambda o: "Total cost" in o or "total" in o.lower(), 10, "Should show total cost"),
    }
    scores, issues = _score_output(output, checks)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="search_activities", agent="Activity Agent", input_params=params,
        output=output[:500], latency_ms=latency, scores=scores, issues=issues,
        passed=sum(scores.values()) >= 60,
    ))

    params2 = {"destination": destination, "cuisine_type": "local", "budget_level": "medium"}
    output2, latency2 = _run_tool(get_restaurant_recommendations, params2)
    checks2 = {
        "has_destination": (lambda o: destination.lower() in o.lower(), 30, "Should reference destination"),
        "has_links": (lambda o: "google.com" in o, 35, "Should include search links"),
        "has_tips": (lambda o: "Tip" in o or "tip" in o.lower(), 35, "Should include tips"),
    }
    scores2, issues2 = _score_output(output2, checks2)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="get_restaurant_recommendations", agent="Activity Agent", input_params=params2,
        output=output2[:500], latency_ms=latency2, scores=scores2, issues=issues2,
        passed=sum(scores2.values()) >= 60,
    ))

    all_scores = [sum(tr.scores.values()) for tr in agent_result.tool_results]
    agent_result.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
    agent_result.latency_avg_ms = sum(tr.latency_ms for tr in agent_result.tool_results) / len(agent_result.tool_results)
    agent_result.pass_rate = sum(1 for tr in agent_result.tool_results if tr.passed) / len(agent_result.tool_results) * 100

    return agent_result


def evaluate_weather_agent(destination: str, start_date: str, end_date: str) -> AgentEvalResult:
    """Evaluate the weather agent tools."""
    agent_result = AgentEvalResult(agent_name="Weather Agent")

    params = {"city": destination, "start_date": start_date, "end_date": end_date}
    output, latency = _run_tool(get_weather_forecast, params)

    checks = {
        "has_city": (lambda o: destination.lower() in o.lower(), 15, "Should reference the city"),
        "has_temps": (lambda o: "C" in o and ("F" in o or "°" in o or "temp" in o.lower()), 20, "Should show temperatures"),
        "has_conditions": (lambda o: any(w in o.lower() for w in ["clear", "cloud", "rain", "sun", "fog", "snow"]), 20, "Should describe weather conditions"),
        "has_rain_pct": (lambda o: "%" in o, 15, "Should show precipitation probability"),
        "has_recommendation": (lambda o: "recommend" in o.lower() or "indoor" in o.lower() or "outdoor" in o.lower() or "umbrella" in o.lower(), 15, "Should give recommendations"),
        "has_data_source": (lambda o: "Open-Meteo" in o or "open-meteo" in o.lower() or "Error" in o or "API" in o, 15, "Should cite data source or indicate API call"),
    }
    scores, issues = _score_output(output, checks)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="get_weather_forecast", agent="Weather Agent", input_params=params,
        output=output[:500], latency_ms=latency, scores=scores, issues=issues,
        passed=sum(scores.values()) >= 50,
    ))

    params2 = {"city": destination}
    output2, latency2 = _run_tool(get_best_travel_months, params2)
    checks2 = {
        "has_city": (lambda o: destination.lower() in o.lower(), 25, "Should reference the city"),
        "has_best": (lambda o: "Best" in o or "best" in o, 25, "Should recommend best months"),
        "has_avoid": (lambda o: "avoid" in o.lower() or "Avoid" in o, 25, "Should mention months to avoid"),
        "has_note": (lambda o: "Note" in o or "climate" in o.lower() or "season" in o.lower(), 25, "Should provide climate context"),
    }
    scores2, issues2 = _score_output(output2, checks2)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="get_best_travel_months", agent="Weather Agent", input_params=params2,
        output=output2[:500], latency_ms=latency2, scores=scores2, issues=issues2,
        passed=sum(scores2.values()) >= 60,
    ))

    all_scores = [sum(tr.scores.values()) for tr in agent_result.tool_results]
    agent_result.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
    agent_result.latency_avg_ms = sum(tr.latency_ms for tr in agent_result.tool_results) / len(agent_result.tool_results)
    agent_result.pass_rate = sum(1 for tr in agent_result.tool_results if tr.passed) / len(agent_result.tool_results) * 100

    return agent_result


def evaluate_budget_agent(destination: str) -> AgentEvalResult:
    """Evaluate the budget agent tools."""
    agent_result = AgentEvalResult(agent_name="Budget Agent")

    params = {
        "destination": destination, "num_days": 7, "num_travelers": 1,
        "flight_cost": 700, "hotel_cost_per_night": 120, "travel_style": "mid",
    }
    output, latency = _run_tool(calculate_trip_budget, params)

    checks = {
        "has_breakdown": (lambda o: "Flights" in o and "Hotel" in o and "Food" in o, 25, "Should show category breakdown"),
        "has_total": (lambda o: "TOTAL" in o or "Total" in o, 20, "Should show total"),
        "has_prices": (lambda o: "$" in o, 15, "Should include dollar amounts"),
        "has_tips": (lambda o: "tip" in o.lower() or "saving" in o.lower(), 20, "Should include money-saving tips"),
        "has_per_day": (lambda o: "/day" in o or "per day" in o.lower(), 20, "Should show per-day costs"),
    }
    scores, issues = _score_output(output, checks)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="calculate_trip_budget", agent="Budget Agent", input_params=params,
        output=output[:500], latency_ms=latency, scores=scores, issues=issues,
        passed=sum(scores.values()) >= 60,
    ))

    params2 = {
        "total_budget": 3000, "destination": destination,
        "num_days": 7, "num_travelers": 1, "priorities": "balanced",
    }
    output2, latency2 = _run_tool(optimize_budget, params2)
    checks2 = {
        "has_allocation": (lambda o: "%" in o, 25, "Should show percentage allocations"),
        "has_amounts": (lambda o: "$" in o, 25, "Should show dollar amounts"),
        "has_style": (lambda o: "budget" in o.lower() or "mid-range" in o.lower() or "luxury" in o.lower() or "comfortable" in o.lower(), 25, "Should indicate travel style"),
        "has_per_person": (lambda o: "per person" in o.lower(), 25, "Should show per-person breakdown"),
    }
    scores2, issues2 = _score_output(output2, checks2)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="optimize_budget", agent="Budget Agent", input_params=params2,
        output=output2[:500], latency_ms=latency2, scores=scores2, issues=issues2,
        passed=sum(scores2.values()) >= 60,
    ))

    params3 = {"destination": destination}
    output3, latency3 = _run_tool(get_currency_info, params3)
    checks3 = {
        "has_currency": (lambda o: "Currency" in o or "currency" in o, 25, "Should show currency name"),
        "has_rate": (lambda o: "rate" in o.lower() or "Rate" in o, 25, "Should show exchange rate"),
        "has_conversion": (lambda o: "$" in o, 25, "Should show conversion table"),
        "has_tips": (lambda o: "tip" in o.lower() or "Wise" in o, 25, "Should include exchange tips"),
    }
    scores3, issues3 = _score_output(output3, checks3)
    agent_result.tool_results.append(ToolEvalResult(
        tool_name="get_currency_info", agent="Budget Agent", input_params=params3,
        output=output3[:500], latency_ms=latency3, scores=scores3, issues=issues3,
        passed=sum(scores3.values()) >= 60,
    ))

    all_scores = [sum(tr.scores.values()) for tr in agent_result.tool_results]
    agent_result.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
    agent_result.latency_avg_ms = sum(tr.latency_ms for tr in agent_result.tool_results) / len(agent_result.tool_results)
    agent_result.pass_rate = sum(1 for tr in agent_result.tool_results if tr.passed) / len(agent_result.tool_results) * 100

    return agent_result


def run_full_evaluation(
    destinations: list[str] | None = None,
    origin: str = "New York",
) -> EvalReport:
    """Run a comprehensive evaluation across multiple destinations.

    Args:
        destinations: List of cities to evaluate against
        origin: Departure city for flights

    Returns:
        Complete evaluation report
    """
    if destinations is None:
        destinations = ["Tokyo", "Paris", "Bangkok", "New York", "Bali"]

    # Use dates 30 days from now
    start = datetime.now() + timedelta(days=30)
    start_date = start.strftime("%Y-%m-%d")
    end_date = (start + timedelta(days=7)).strftime("%Y-%m-%d")

    report = EvalReport(
        timestamp=datetime.now().isoformat(),
        destination=", ".join(destinations),
    )

    all_agent_scores = []

    for dest in destinations:
        print(f"\nEvaluating agents for: {dest}")
        print("-" * 40)

        # Evaluate each agent
        flight_eval = evaluate_flight_agent(dest, origin, start_date, end_date)
        print(f"  Flight Agent:   {flight_eval.overall_score:.0f}/100 ({flight_eval.latency_avg_ms:.0f}ms)")

        hotel_eval = evaluate_hotel_agent(dest, start_date, end_date)
        print(f"  Hotel Agent:    {hotel_eval.overall_score:.0f}/100 ({hotel_eval.latency_avg_ms:.0f}ms)")

        activity_eval = evaluate_activity_agent(dest)
        print(f"  Activity Agent: {activity_eval.overall_score:.0f}/100 ({activity_eval.latency_avg_ms:.0f}ms)")

        weather_eval = evaluate_weather_agent(dest, start_date, end_date)
        print(f"  Weather Agent:  {weather_eval.overall_score:.0f}/100 ({weather_eval.latency_avg_ms:.0f}ms)")

        budget_eval = evaluate_budget_agent(dest)
        print(f"  Budget Agent:   {budget_eval.overall_score:.0f}/100 ({budget_eval.latency_avg_ms:.0f}ms)")

        for eval_result in [flight_eval, hotel_eval, activity_eval, weather_eval, budget_eval]:
            report.agent_results.append(eval_result)
            all_agent_scores.append(eval_result.overall_score)

    report.total_score = sum(all_agent_scores) / len(all_agent_scores) if all_agent_scores else 0

    # Generate summary
    report.summary = (
        f"Evaluated {len(destinations)} destinations across 5 agent types.\n"
        f"Overall Score: {report.total_score:.1f}/100\n"
        f"Total tool calls: {sum(len(ar.tool_results) for ar in report.agent_results)}\n"
        f"Pass rate: {sum(1 for ar in report.agent_results if ar.pass_rate == 100) / len(report.agent_results) * 100:.0f}%\n"
    )

    return report


def report_to_dict(report: EvalReport) -> dict:
    """Convert evaluation report to a serializable dictionary."""
    return {
        "timestamp": report.timestamp,
        "destination": report.destination,
        "total_score": report.total_score,
        "summary": report.summary,
        "agent_results": [
            {
                "agent_name": ar.agent_name,
                "overall_score": ar.overall_score,
                "latency_avg_ms": ar.latency_avg_ms,
                "pass_rate": ar.pass_rate,
                "tool_results": [
                    {
                        "tool_name": tr.tool_name,
                        "latency_ms": tr.latency_ms,
                        "scores": tr.scores,
                        "issues": tr.issues,
                        "passed": tr.passed,
                    }
                    for tr in ar.tool_results
                ],
            }
            for ar in ar_list
        ] if (ar_list := report.agent_results) else [],
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  VoyageAI Agent Evaluation")
    print("=" * 60)

    report = run_full_evaluation()

    print("\n" + "=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(report.summary)

    # Save report
    report_dict = report_to_dict(report)
    with open("evaluation/eval_results.json", "w") as f:
        json.dump(report_dict, f, indent=2)
    print("Report saved to evaluation/eval_results.json")
