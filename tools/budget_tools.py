"""Budget optimization and currency tools."""

import json
import urllib.request
from langchain_core.tools import tool


# Average daily costs by city (in USD) - real data based on travel blogs and budget sites
CITY_COSTS = {
    "tokyo": {"budget": 60, "mid": 150, "luxury": 400, "currency": "JPY", "rate": 149.5},
    "paris": {"budget": 80, "mid": 200, "luxury": 500, "currency": "EUR", "rate": 0.92},
    "london": {"budget": 90, "mid": 220, "luxury": 550, "currency": "GBP", "rate": 0.79},
    "new york": {"budget": 100, "mid": 250, "luxury": 600, "currency": "USD", "rate": 1.0},
    "barcelona": {"budget": 55, "mid": 140, "luxury": 350, "currency": "EUR", "rate": 0.92},
    "rome": {"budget": 60, "mid": 150, "luxury": 400, "currency": "EUR", "rate": 0.92},
    "bangkok": {"budget": 25, "mid": 70, "luxury": 200, "currency": "THB", "rate": 34.5},
    "bali": {"budget": 20, "mid": 60, "luxury": 180, "currency": "IDR", "rate": 15700},
    "amsterdam": {"budget": 75, "mid": 180, "luxury": 450, "currency": "EUR", "rate": 0.92},
    "istanbul": {"budget": 30, "mid": 80, "luxury": 250, "currency": "TRY", "rate": 32.1},
    "singapore": {"budget": 50, "mid": 150, "luxury": 400, "currency": "SGD", "rate": 1.34},
    "hong kong": {"budget": 50, "mid": 140, "luxury": 380, "currency": "HKD", "rate": 7.82},
    "seoul": {"budget": 45, "mid": 120, "luxury": 300, "currency": "KRW", "rate": 1320},
    "dubai": {"budget": 70, "mid": 200, "luxury": 600, "currency": "AED", "rate": 3.67},
    "sydney": {"budget": 80, "mid": 200, "luxury": 500, "currency": "AUD", "rate": 1.53},
    "los angeles": {"budget": 80, "mid": 200, "luxury": 500, "currency": "USD", "rate": 1.0},
    "san francisco": {"budget": 90, "mid": 230, "luxury": 550, "currency": "USD", "rate": 1.0},
    "miami": {"budget": 70, "mid": 180, "luxury": 450, "currency": "USD", "rate": 1.0},
    "prague": {"budget": 35, "mid": 90, "luxury": 250, "currency": "CZK", "rate": 23.1},
    "lisbon": {"budget": 45, "mid": 110, "luxury": 300, "currency": "EUR", "rate": 0.92},
    "berlin": {"budget": 50, "mid": 130, "luxury": 350, "currency": "EUR", "rate": 0.92},
    "cape town": {"budget": 30, "mid": 80, "luxury": 250, "currency": "ZAR", "rate": 18.2},
    "mexico city": {"budget": 25, "mid": 65, "luxury": 200, "currency": "MXN", "rate": 17.1},
    "buenos aires": {"budget": 20, "mid": 55, "luxury": 180, "currency": "ARS", "rate": 870},
    "rio de janeiro": {"budget": 30, "mid": 80, "luxury": 250, "currency": "BRL", "rate": 4.97},
    "hanoi": {"budget": 15, "mid": 45, "luxury": 150, "currency": "VND", "rate": 24500},
    "marrakech": {"budget": 25, "mid": 70, "luxury": 200, "currency": "MAD", "rate": 10.1},
}


def _get_city_costs(destination: str) -> dict | None:
    dest_lower = destination.lower().strip()
    for city_key, costs in CITY_COSTS.items():
        if city_key in dest_lower or dest_lower in city_key:
            return costs
    return None


@tool
def calculate_trip_budget(
    destination: str,
    num_days: int,
    num_travelers: int,
    flight_cost: float,
    hotel_cost_per_night: float,
    travel_style: str = "mid"
) -> str:
    """Calculate a detailed trip budget breakdown.

    Args:
        destination: Travel destination city
        num_days: Number of days for the trip
        num_travelers: Number of travelers
        flight_cost: Total flight cost for all travelers
        hotel_cost_per_night: Hotel cost per night
        travel_style: Travel style - "budget", "mid", or "luxury"
    """
    city_costs = _get_city_costs(destination)

    if city_costs:
        daily_cost = city_costs.get(travel_style, city_costs["mid"])
        currency = city_costs["currency"]
        rate = city_costs["rate"]
    else:
        daily_cost = {"budget": 50, "mid": 120, "luxury": 350}.get(travel_style, 120)
        currency = "USD"
        rate = 1.0

    hotel_total = hotel_cost_per_night * num_days
    food_daily = daily_cost * 0.35 * num_travelers
    food_total = food_daily * num_days
    activities_daily = daily_cost * 0.25 * num_travelers
    activities_total = activities_daily * num_days
    transport_daily = daily_cost * 0.15 * num_travelers
    transport_total = transport_daily * num_days
    misc_daily = daily_cost * 0.1 * num_travelers
    misc_total = misc_daily * num_days

    grand_total = flight_cost + hotel_total + food_total + activities_total + transport_total + misc_total

    result = f"**Trip Budget for {destination}** ({num_days} days, {num_travelers} traveler(s), {travel_style} style)\n\n"
    result += f"| Category | Daily | Total |\n"
    result += f"|----------|-------|-------|\n"
    result += f"| Flights | - | ${flight_cost:,.2f} |\n"
    result += f"| Hotel | ${hotel_cost_per_night:,.2f}/night | ${hotel_total:,.2f} |\n"
    result += f"| Food & Dining | ${food_daily:,.2f}/day | ${food_total:,.2f} |\n"
    result += f"| Activities | ${activities_daily:,.2f}/day | ${activities_total:,.2f} |\n"
    result += f"| Local Transport | ${transport_daily:,.2f}/day | ${transport_total:,.2f} |\n"
    result += f"| Miscellaneous | ${misc_daily:,.2f}/day | ${misc_total:,.2f} |\n"
    result += f"| **TOTAL** | **${grand_total / num_days:,.2f}/day** | **${grand_total:,.2f}** |\n\n"

    if currency != "USD":
        local_total = grand_total * rate
        result += f"In local currency: {local_total:,.0f} {currency} (rate: 1 USD = {rate} {currency})\n\n"

    result += "**Money-saving tips:**\n"
    result += "- Book flights 6-8 weeks in advance for best prices\n"
    result += "- Use Google Flights price alerts for fare drops\n"
    result += "- Eat at local spots instead of tourist areas (30-50% cheaper)\n"
    result += "- Get a city transit pass for unlimited local transport\n"
    result += "- Many museums have free entry days\n"
    result += "- Use Wise or Revolut for the best currency exchange rates\n"

    return result


@tool
def optimize_budget(total_budget: float, destination: str, num_days: int, num_travelers: int, priorities: str = "balanced") -> str:
    """Optimize budget allocation based on priorities.

    Args:
        total_budget: Total budget in USD
        destination: Travel destination
        num_days: Number of days
        num_travelers: Number of travelers
        priorities: Priority style - "flights", "hotels", "activities", "food", or "balanced"
    """
    allocations = {
        "balanced": {"flights": 0.30, "hotels": 0.30, "food": 0.18, "activities": 0.12, "transport": 0.07, "misc": 0.03},
        "flights": {"flights": 0.40, "hotels": 0.25, "food": 0.15, "activities": 0.10, "transport": 0.07, "misc": 0.03},
        "hotels": {"flights": 0.25, "hotels": 0.40, "food": 0.15, "activities": 0.10, "transport": 0.07, "misc": 0.03},
        "activities": {"flights": 0.25, "hotels": 0.25, "food": 0.15, "activities": 0.25, "transport": 0.07, "misc": 0.03},
        "food": {"flights": 0.25, "hotels": 0.25, "food": 0.28, "activities": 0.12, "transport": 0.07, "misc": 0.03},
    }

    alloc = allocations.get(priorities, allocations["balanced"])

    result = f"**Optimized Budget for {destination}** (${total_budget:,.2f} total, {priorities} priority)\n\n"
    result += f"| Category | Allocation | Amount | Per Day |\n"
    result += f"|----------|-----------|--------|--------|\n"

    for category, pct in alloc.items():
        amount = total_budget * pct
        per_day = amount / num_days if category != "flights" else amount
        result += f"| {category.title()} | {pct*100:.0f}% | ${amount:,.2f} | ${per_day:,.2f} |\n"

    result += f"\n**Budget per person:** ${total_budget / num_travelers:,.2f}\n"
    result += f"**Budget per person per day:** ${total_budget / num_travelers / num_days:,.2f}\n"

    city_costs = _get_city_costs(destination)
    if city_costs:
        daily_per_person = total_budget / num_travelers / num_days
        if daily_per_person >= city_costs["luxury"]:
            style = "luxury"
        elif daily_per_person >= city_costs["mid"]:
            style = "comfortable mid-range"
        elif daily_per_person >= city_costs["budget"]:
            style = "budget-friendly"
        else:
            style = "very tight - consider extending budget or shortening trip"
        result += f"\nFor {destination}, this budget supports a **{style}** travel style.\n"

    return result


@tool
def get_currency_info(destination: str) -> str:
    """Get currency information and exchange tips for a destination.

    Args:
        destination: Travel destination city
    """
    city_costs = _get_city_costs(destination)

    if city_costs:
        currency = city_costs["currency"]
        rate = city_costs["rate"]
    else:
        currency = "Local currency"
        rate = None

    result = f"**Currency Info for {destination}**\n\n"
    if rate:
        result += f"Currency: {currency}\n"
        result += f"Approximate rate: 1 USD = {rate} {currency}\n\n"
        result += f"| USD | {currency} |\n|-----|-----|\n"
        for usd in [1, 5, 10, 20, 50, 100]:
            result += f"| ${usd} | {usd * rate:,.1f} {currency} |\n"
    else:
        result += f"Currency data not available for {destination}.\n"

    result += f"\n**Exchange tips:**\n"
    result += f"- Use Wise (formerly TransferWise) for the best rates\n"
    result += f"- Avoid airport exchange counters (worst rates)\n"
    result += f"- Use ATMs from major banks for cash withdrawals\n"
    result += f"- Always pay in local currency when given the choice\n"
    result += f"- Notify your bank before traveling to avoid card blocks\n"

    return result
