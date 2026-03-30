"""LangGraph workflow for the multi-agent travel planning system."""

from __future__ import annotations

import functools
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from graph.state import AgentState
from agents.flight_agent import create_flight_agent
from agents.hotel_agent import create_hotel_agent
from agents.activity_agent import create_activity_agent
from agents.weather_agent import create_weather_agent
from agents.budget_agent import create_budget_agent
from agents.itinerary_agent import create_itinerary_agent, ITINERARY_SYSTEM_PROMPT
from config.settings import LLM_MODEL, LLM_TEMPERATURE, SUPERVISOR_RECURSION_LIMIT


def _build_agent_input(state: AgentState, agent_type: str) -> str:
    """Build the input prompt for a specific agent based on current state."""
    req = state["travel_request"]
    base = (
        f"Destination: {req['destination']}\n"
        f"Origin: {req['origin']}\n"
        f"Dates: {req['start_date']} to {req['end_date']}\n"
        f"Budget: ${req['budget']}\n"
        f"Travelers: {req['travelers']}\n"
        f"Preferences: {req['preferences']}\n"
    )

    if agent_type == "flight":
        return (
            f"Search for the best flights for this trip:\n{base}\n"
            f"Find round-trip flights from {req['origin']} to {req['destination']}, "
            f"departing {req['start_date']} and returning {req['end_date']} "
            f"for {req['travelers']} passenger(s). Also compare prices across platforms."
        )
    elif agent_type == "hotel":
        return (
            f"Search for hotels for this trip:\n{base}\n"
            f"Find hotels in {req['destination']} from {req['start_date']} to {req['end_date']} "
            f"for {req['travelers']} guests. Max budget per night: ${req['budget'] * 0.3 / max(1, _calc_nights(req))}."
        )
    elif agent_type == "activity":
        return (
            f"Find activities and attractions for this trip:\n{base}\n"
            f"Search for things to do in {req['destination']}. "
            f"Include a mix of free and paid activities. Also find restaurant recommendations."
        )
    elif agent_type == "weather":
        return (
            f"Get the weather forecast for this trip:\n{base}\n"
            f"Get the forecast for {req['destination']} from {req['start_date']} to {req['end_date']}. "
            f"Also check the best months to visit."
        )
    elif agent_type == "budget":
        flight_cost = 500  # default
        hotel_cost = 100  # default
        if state.get("flights"):
            flight_cost = state["flights"][0].get("total_price", 500) if state["flights"] else 500
        if state.get("hotels"):
            hotel_cost = state["hotels"][0].get("price_per_night", 100) if state["hotels"] else 100

        return (
            f"Optimize the budget for this trip:\n{base}\n"
            f"Calculate a detailed budget breakdown. Estimated flight cost: ${flight_cost}. "
            f"Estimated hotel cost per night: ${hotel_cost}. "
            f"Also get currency information for {req['destination']}."
        )
    return base


def _calc_nights(req: dict) -> int:
    from datetime import datetime
    try:
        d1 = datetime.strptime(req["start_date"], "%Y-%m-%d")
        d2 = datetime.strptime(req["end_date"], "%Y-%m-%d")
        return max((d2 - d1).days, 1)
    except (ValueError, KeyError):
        return 3


def run_agent_node(state: AgentState, agent_type: str, agent_executor) -> dict:
    """Run a specialist agent and update state."""
    try:
        agent_input = _build_agent_input(state, agent_type)
        result = agent_executor.invoke({"input": agent_input})
        output = result.get("output", "No output")

        return {
            "messages": [AIMessage(content=f"[{agent_type.upper()} AGENT]: {output}")],
            "agent_logs": [f"[{agent_type}] Completed successfully"],
            "current_agent": agent_type,
        }
    except Exception as e:
        return {
            "messages": [AIMessage(content=f"[{agent_type.upper()} AGENT]: Error - {str(e)}")],
            "agent_logs": [f"[{agent_type}] Error: {str(e)}"],
            "error": str(e),
        }


def compile_itinerary_node(state: AgentState) -> dict:
    """Compile all agent results into a final itinerary."""
    llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    req = state["travel_request"]

    # Gather all agent outputs
    all_outputs = "\n\n".join([msg.content for msg in state["messages"] if isinstance(msg, AIMessage)])

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

    return {
        "messages": [AIMessage(content=f"[ITINERARY AGENT]: {response.content}")],
        "itinerary": response.content,
        "agent_logs": [f"[itinerary] Final itinerary compiled"],
        "current_agent": "itinerary",
    }


def should_continue(state: AgentState) -> str:
    """Decide what to do next based on completed agents."""
    logs = state.get("agent_logs", [])
    completed = set()
    for log in logs:
        if "Completed" in log or "compiled" in log:
            for agent in ["weather", "flight", "hotel", "activity", "budget", "itinerary"]:
                if agent in log:
                    completed.add(agent)

    # Execution order logic
    if "weather" not in completed:
        return "weather"
    if "flight" not in completed:
        return "flight"
    if "hotel" not in completed:
        return "hotel"
    if "activity" not in completed:
        return "activity"
    if "budget" not in completed:
        return "budget"
    if "itinerary" not in completed:
        return "itinerary"
    return "end"


def create_travel_workflow(llm: ChatOpenAI | None = None) -> StateGraph:
    """Create the full multi-agent travel planning workflow."""
    if llm is None:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    # Create all agent executors
    flight_agent = create_flight_agent(llm)
    hotel_agent = create_hotel_agent(llm)
    activity_agent = create_activity_agent(llm)
    weather_agent = create_weather_agent(llm)
    budget_agent = create_budget_agent(llm)

    # Build the graph
    workflow = StateGraph(AgentState)

    # Add agent nodes
    workflow.add_node("weather", functools.partial(run_agent_node, agent_type="weather", agent_executor=weather_agent))
    workflow.add_node("flight", functools.partial(run_agent_node, agent_type="flight", agent_executor=flight_agent))
    workflow.add_node("hotel", functools.partial(run_agent_node, agent_type="hotel", agent_executor=hotel_agent))
    workflow.add_node("activity", functools.partial(run_agent_node, agent_type="activity", agent_executor=activity_agent))
    workflow.add_node("budget", functools.partial(run_agent_node, agent_type="budget", agent_executor=budget_agent))
    workflow.add_node("itinerary", compile_itinerary_node)

    # Add conditional routing
    workflow.add_conditional_edges(
        "__start__",
        should_continue,
        {
            "weather": "weather",
            "flight": "flight",
            "hotel": "hotel",
            "activity": "activity",
            "budget": "budget",
            "itinerary": "itinerary",
            "end": END,
        },
    )

    for node in ["weather", "flight", "hotel", "activity", "budget", "itinerary"]:
        workflow.add_conditional_edges(
            node,
            should_continue,
            {
                "weather": "weather",
                "flight": "flight",
                "hotel": "hotel",
                "activity": "activity",
                "budget": "budget",
                "itinerary": "itinerary",
                "end": END,
            },
        )

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

    return "Unable to generate itinerary. Please check your API key and try again."
