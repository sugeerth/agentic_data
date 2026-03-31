"""LangGraph workflow for the multi-agent travel planning system.

Key design: Tools are called DIRECTLY (no LLM needed) for 5/6 agents.
Only the final itinerary compilation uses an LLM call.
This makes the system fast, reliable, and mostly free.
"""

from __future__ import annotations

import functools
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, END

from graph.state import AgentState
from tools.flight_tools import search_flights, compare_flight_prices
from tools.hotel_tools import search_hotels, compare_hotel_prices
from tools.activity_tools import search_activities, get_restaurant_recommendations
from tools.weather_tools import get_weather_forecast, get_best_travel_months
from tools.budget_tools import calculate_trip_budget, optimize_budget, get_currency_info
from agents.itinerary_agent import ITINERARY_SYSTEM_PROMPT
from config.settings import SUPERVISOR_RECURSION_LIMIT


def _calc_nights(req: dict) -> int:
    try:
        d1 = datetime.strptime(req["start_date"], "%Y-%m-%d")
        d2 = datetime.strptime(req["end_date"], "%Y-%m-%d")
        return max((d2 - d1).days, 1)
    except (ValueError, KeyError):
        return 3


# ---------------------------------------------------------------------------
# Direct tool-calling nodes (no LLM required)
# ---------------------------------------------------------------------------

def weather_node(state: AgentState) -> dict:
    """Get weather forecast by calling tools directly."""
    req = state["travel_request"]
    parts = []
    try:
        forecast = get_weather_forecast.invoke({
            "city": req["destination"],
            "start_date": req["start_date"],
            "end_date": req["end_date"],
        })
        parts.append(forecast)
    except Exception as e:
        parts.append(f"Weather forecast unavailable: {e}")

    try:
        best_months = get_best_travel_months.invoke({"city": req["destination"]})
        parts.append(best_months)
    except Exception as e:
        parts.append(f"Best travel months unavailable: {e}")

    output = "\n\n".join(parts)
    return {
        "messages": [AIMessage(content=f"[WEATHER AGENT]:\n{output}")],
        "agent_logs": ["[weather] Completed successfully"],
        "current_agent": "weather",
    }


def flight_node(state: AgentState) -> dict:
    """Search flights by calling tools directly."""
    req = state["travel_request"]
    parts = []
    try:
        flights = search_flights.invoke({
            "origin": req["origin"],
            "destination": req["destination"],
            "departure_date": req["start_date"],
            "return_date": req["end_date"],
            "passengers": req["travelers"],
        })
        parts.append(flights)
    except Exception as e:
        parts.append(f"Flight search error: {e}")

    try:
        comparison = compare_flight_prices.invoke({
            "origin": req["origin"],
            "destination": req["destination"],
            "date": req["start_date"],
        })
        parts.append(comparison)
    except Exception as e:
        parts.append(f"Price comparison unavailable: {e}")

    output = "\n\n".join(parts)
    return {
        "messages": [AIMessage(content=f"[FLIGHT AGENT]:\n{output}")],
        "agent_logs": ["[flight] Completed successfully"],
        "current_agent": "flight",
    }


def hotel_node(state: AgentState) -> dict:
    """Search hotels by calling tools directly."""
    req = state["travel_request"]
    nights = _calc_nights(req)
    max_hotel_price = req["budget"] * 0.3 / max(nights, 1)

    parts = []
    try:
        hotels = search_hotels.invoke({
            "destination": req["destination"],
            "check_in": req["start_date"],
            "check_out": req["end_date"],
            "guests": req["travelers"],
            "max_price": max_hotel_price,
        })
        parts.append(hotels)
    except Exception as e:
        parts.append(f"Hotel search error: {e}")

    output = "\n\n".join(parts)
    return {
        "messages": [AIMessage(content=f"[HOTEL AGENT]:\n{output}")],
        "agent_logs": ["[hotel] Completed successfully"],
        "current_agent": "hotel",
    }


def activity_node(state: AgentState) -> dict:
    """Search activities by calling tools directly."""
    req = state["travel_request"]
    parts = []
    try:
        activities = search_activities.invoke({
            "destination": req["destination"],
            "categories": "all",
            "max_budget": req["budget"] * 0.15,
        })
        parts.append(activities)
    except Exception as e:
        parts.append(f"Activity search error: {e}")

    try:
        restaurants = get_restaurant_recommendations.invoke({
            "destination": req["destination"],
            "cuisine_type": "local",
            "budget_level": "medium",
        })
        parts.append(restaurants)
    except Exception as e:
        parts.append(f"Restaurant recommendations unavailable: {e}")

    output = "\n\n".join(parts)
    return {
        "messages": [AIMessage(content=f"[ACTIVITY AGENT]:\n{output}")],
        "agent_logs": ["[activity] Completed successfully"],
        "current_agent": "activity",
    }


def budget_node(state: AgentState) -> dict:
    """Calculate budget by calling tools directly."""
    req = state["travel_request"]
    nights = _calc_nights(req)

    # Extract estimated costs from prior agent results if available
    flight_cost = 500
    hotel_cost = 100
    messages = state.get("messages", [])
    for msg in messages:
        if isinstance(msg, AIMessage) and "[FLIGHT AGENT]" in msg.content:
            # Try to extract the cheapest flight price
            for line in msg.content.split("\n"):
                if "Price: $" in line:
                    try:
                        price_str = line.split("Price: $")[1].split(" ")[0].replace(",", "")
                        flight_cost = float(price_str)
                        break
                    except (ValueError, IndexError):
                        pass
        if isinstance(msg, AIMessage) and "[HOTEL AGENT]" in msg.content:
            for line in msg.content.split("\n"):
                if "/night" in line and "$" in line:
                    try:
                        price_str = line.split("$")[1].split("/night")[0].replace(",", "")
                        hotel_cost = float(price_str)
                        break
                    except (ValueError, IndexError):
                        pass

    parts = []
    try:
        budget = calculate_trip_budget.invoke({
            "destination": req["destination"],
            "num_days": nights,
            "num_travelers": req["travelers"],
            "flight_cost": flight_cost,
            "hotel_cost_per_night": hotel_cost,
            "travel_style": "mid",
        })
        parts.append(budget)
    except Exception as e:
        parts.append(f"Budget calculation error: {e}")

    try:
        optimization = optimize_budget.invoke({
            "total_budget": req["budget"],
            "destination": req["destination"],
            "num_days": nights,
            "num_travelers": req["travelers"],
            "priorities": "balanced",
        })
        parts.append(optimization)
    except Exception as e:
        parts.append(f"Budget optimization unavailable: {e}")

    try:
        currency = get_currency_info.invoke({"destination": req["destination"]})
        parts.append(currency)
    except Exception as e:
        parts.append(f"Currency info unavailable: {e}")

    output = "\n\n".join(parts)
    return {
        "messages": [AIMessage(content=f"[BUDGET AGENT]:\n{output}")],
        "agent_logs": ["[budget] Completed successfully"],
        "current_agent": "budget",
    }


# ---------------------------------------------------------------------------
# Itinerary compilation (uses LLM)
# ---------------------------------------------------------------------------

def _compile_fallback_itinerary(state: AgentState) -> str:
    """Compile a basic itinerary from raw tool outputs (no LLM needed)."""
    req = state["travel_request"]
    nights = _calc_nights(req)

    sections = []
    sections.append(f"# Trip to {req['destination']}")
    sections.append(f"**From:** {req['origin']} | **Dates:** {req['start_date']} to {req['end_date']} "
                     f"({nights} nights) | **Budget:** ${req['budget']:,.0f} | **Travelers:** {req['travelers']}")
    sections.append("---")

    for msg in state.get("messages", []):
        if isinstance(msg, AIMessage):
            # Clean up agent headers
            content = msg.content
            for tag in ["[WEATHER AGENT]:", "[FLIGHT AGENT]:", "[HOTEL AGENT]:",
                        "[ACTIVITY AGENT]:", "[BUDGET AGENT]:"]:
                if content.startswith(tag):
                    agent_name = tag.replace("[", "").replace("]:", "").strip()
                    content = f"## {agent_name}\n{content[len(tag):].strip()}"
                    break
            sections.append(content)

    sections.append("---")
    sections.append("*Generated by VoyageAI - Multi-Agent Travel Planner*")
    return "\n\n".join(sections)


def compile_itinerary_node(state: AgentState) -> dict:
    """Compile all agent results into a final itinerary using LLM."""
    req = state["travel_request"]

    # Gather all agent outputs
    all_outputs = "\n\n".join([
        msg.content for msg in state["messages"]
        if isinstance(msg, AIMessage)
    ])

    # Try LLM compilation first
    try:
        from config.llm_factory import create_llm
        llm = create_llm()

        prompt = (
            f"{ITINERARY_SYSTEM_PROMPT}\n\n"
            f"Trip Details:\n"
            f"- Destination: {req['destination']}\n"
            f"- Origin: {req['origin']}\n"
            f"- Dates: {req['start_date']} to {req['end_date']}\n"
            f"- Budget: ${req['budget']}\n"
            f"- Travelers: {req['travelers']}\n"
            f"- Preferences: {req['preferences']}\n\n"
            f"Agent Reports:\n{all_outputs}\n\n"
            f"Now compile a comprehensive, beautifully formatted day-by-day itinerary. "
            f"Include all booking links, budget tracking, and practical tips."
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        itinerary = response.content

    except Exception as e:
        # Fallback: compile without LLM
        itinerary = _compile_fallback_itinerary(state)
        itinerary += f"\n\n> *Note: LLM compilation unavailable ({e}). Showing raw agent data above. " \
                     f"Set up a free LLM provider (Groq or Google Gemini) for a polished day-by-day itinerary.*"

    return {
        "messages": [AIMessage(content=f"[ITINERARY AGENT]: {itinerary}")],
        "itinerary": itinerary,
        "agent_logs": ["[itinerary] Final itinerary compiled"],
        "current_agent": "itinerary",
    }


# ---------------------------------------------------------------------------
# Workflow graph
# ---------------------------------------------------------------------------

def create_travel_workflow() -> StateGraph:
    """Create the multi-agent travel planning workflow.

    Uses direct tool calls for data-gathering agents (fast, free, reliable)
    and LLM only for final itinerary compilation.
    """
    workflow = StateGraph(AgentState)

    # Add nodes - these call tools directly (no LLM)
    # Node names use _agent suffix to avoid collision with state keys
    workflow.add_node("weather_agent", weather_node)
    workflow.add_node("flight_agent", flight_node)
    workflow.add_node("hotel_agent", hotel_node)
    workflow.add_node("activity_agent", activity_node)
    workflow.add_node("budget_agent", budget_node)
    workflow.add_node("itinerary_agent", compile_itinerary_node)

    # Sequential flow
    workflow.add_edge("__start__", "weather_agent")
    workflow.add_edge("weather_agent", "flight_agent")
    workflow.add_edge("flight_agent", "hotel_agent")
    workflow.add_edge("hotel_agent", "activity_agent")
    workflow.add_edge("activity_agent", "budget_agent")
    workflow.add_edge("budget_agent", "itinerary_agent")
    workflow.add_edge("itinerary_agent", END)

    return workflow.compile()


def run_travel_planner(
    destination: str,
    origin: str = "New York",
    start_date: str = "2025-06-01",
    end_date: str = "2025-06-07",
    budget: float = 3000,
    travelers: int = 1,
    preferences: str = "balanced mix of culture, food, and adventure",
    callback=None,
) -> str:
    """Run the full travel planning workflow.

    Args:
        destination: Where to travel
        origin: Starting city
        start_date: Trip start date
        end_date: Trip end date
        budget: Total budget in USD
        travelers: Number of travelers
        preferences: Travel style preferences
        callback: Optional callback function(agent_name, status, message)

    Returns:
        The compiled itinerary as a string
    """
    workflow = create_travel_workflow()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=f"Plan a trip to {destination}")],
        "travel_request": {
            "destination": destination,
            "origin": origin,
            "start_date": start_date,
            "end_date": end_date,
            "budget": budget,
            "travelers": travelers,
            "preferences": preferences,
        },
        "flights": [],
        "hotels": [],
        "activities": [],
        "weather": [],
        "budget": {},
        "itinerary": "",
        "current_agent": "",
        "agent_logs": [],
        "completed_agents": [],
        "error": "",
    }

    # Run the workflow
    final_state = None
    for step in workflow.stream(initial_state, {"recursion_limit": SUPERVISOR_RECURSION_LIMIT}):
        for node_name, node_state in step.items():
            if callback:
                agent_name = node_state.get("current_agent", node_name)
                logs = node_state.get("agent_logs", [])
                last_log = logs[-1] if logs else ""
                messages = node_state.get("messages", [])
                last_msg = messages[-1].content if messages else ""
                callback(agent_name, last_log, last_msg)
            final_state = node_state

    if final_state and final_state.get("itinerary"):
        return final_state["itinerary"]

    # Fallback: return all messages
    if final_state and final_state.get("messages"):
        return "\n\n".join([m.content for m in final_state["messages"] if isinstance(m, AIMessage)])

    return "Unable to generate itinerary. Please check your configuration and try again."
