"""Shared state for the multi-agent travel planning workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class TravelRequest(TypedDict):
    """User's travel request."""
    destination: str
    origin: str
    start_date: str
    end_date: str
    budget: float
    travelers: int
    preferences: str


class FlightResult(TypedDict):
    """Flight search results."""
    airline: str
    departure: str
    arrival: str
    price: float
    duration: str
    stops: int
    booking_link: str


class HotelResult(TypedDict):
    """Hotel search results."""
    name: str
    rating: float
    price_per_night: float
    location: str
    amenities: list[str]
    booking_link: str


class ActivityResult(TypedDict):
    """Activity recommendation."""
    name: str
    category: str
    description: str
    estimated_cost: float
    duration: str
    rating: float
    location: str


class WeatherForecast(TypedDict):
    """Weather forecast data."""
    date: str
    condition: str
    temp_high: float
    temp_low: float
    precipitation_chance: int
    recommendation: str


class BudgetBreakdown(TypedDict):
    """Budget allocation."""
    flights: float
    hotels: float
    activities: float
    food: float
    transport: float
    misc: float
    total: float
    remaining: float


class AgentState(TypedDict):
    """Shared state across all agents in the graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    travel_request: TravelRequest
    flights: list[FlightResult]
    hotels: list[HotelResult]
    activities: list[ActivityResult]
    weather: list[WeatherForecast]
    budget: BudgetBreakdown
    itinerary: str
    current_agent: str
    agent_logs: Annotated[list[str], operator.add]
    completed_agents: list[str]
    error: str
