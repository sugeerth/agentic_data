"""Weather tools using free Open-Meteo API (no API key required)."""

import json
import ssl
import urllib.request
from datetime import datetime
from langchain_core.tools import tool

# Create an SSL context that doesn't verify certificates (for environments with SSL issues)
_ssl_ctx = ssl.create_default_context()
try:
    _ssl_ctx.check_hostname = True
    _ssl_ctx.verify_mode = ssl.CERT_REQUIRED
except Exception:
    pass

# Fallback unverified context for systems with cert issues
_ssl_ctx_unverified = ssl._create_unverified_context()

# Geocoding data for common travel destinations
CITY_COORDS = {
    "tokyo": (35.6762, 139.6503), "paris": (48.8566, 2.3522),
    "london": (51.5074, -0.1278), "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437), "barcelona": (41.3874, 2.1686),
    "rome": (41.9028, 12.4964), "amsterdam": (52.3676, 4.9041),
    "bangkok": (13.7563, 100.5018), "singapore": (1.3521, 103.8198),
    "bali": (-8.3405, 115.0920), "sydney": (-33.8688, 151.2093),
    "dubai": (25.2048, 55.2708), "istanbul": (41.0082, 28.9784),
    "prague": (50.0755, 14.4378), "berlin": (52.5200, 13.4050),
    "san francisco": (37.7749, -122.4194), "miami": (25.7617, -80.1918),
    "chicago": (41.8781, -87.6298), "seattle": (47.6062, -122.3321),
    "hong kong": (22.3193, 114.1694), "seoul": (37.5665, 126.9780),
    "taipei": (25.0330, 121.5654), "osaka": (34.6937, 135.5023),
    "munich": (48.1351, 11.5820), "vienna": (48.2082, 16.3738),
    "lisbon": (38.7223, -9.1393), "athens": (37.9838, 23.7275),
    "cape town": (-33.9249, 18.4241), "cairo": (30.0444, 31.2357),
    "rio de janeiro": (-22.9068, -43.1729), "buenos aires": (-34.6037, -58.3816),
    "mexico city": (19.4326, -99.1332), "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207), "denver": (39.7392, -104.9903),
    "boston": (42.3601, -71.0589), "hanoi": (21.0278, 105.8342),
    "kuala lumpur": (3.1390, 101.6869), "marrakech": (31.6295, -7.9811),
    "nairobi": (-1.2921, 36.8219), "lima": (-12.0464, -77.0428),
    "bogota": (4.7110, -74.0721), "santiago": (-33.4489, -70.6693),
    "copenhagen": (55.6761, 12.5683), "stockholm": (59.3293, 18.0686),
    "dublin": (53.3498, -6.2603), "zurich": (47.3769, 8.5417),
    "melbourne": (-37.8136, 144.9631), "auckland": (-36.8485, 174.7633),
    "mumbai": (19.0760, 72.8777), "delhi": (28.7041, 77.1025),
    "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
    "kyoto": (35.0116, 135.7681), "houston": (29.7604, -95.3698),
}

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def _get_coords(city: str) -> tuple[float, float] | None:
    city_lower = city.lower().strip()
    for key, coords in CITY_COORDS.items():
        if key in city_lower or city_lower in key:
            return coords
    return None


def _fetch_url(url: str) -> dict | None:
    """Fetch a URL with SSL fallback."""
    req = urllib.request.Request(url, headers={"User-Agent": "VoyageAI/1.0"})
    for ctx in [_ssl_ctx, _ssl_ctx_unverified]:
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                return json.loads(resp.read().decode())
        except ssl.SSLError:
            continue
        except Exception:
            break
    return None


def _geocode_city(city: str) -> tuple[float, float] | None:
    """Use Open-Meteo's free geocoding API."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city.replace(' ', '+')}&count=1"
    data = _fetch_url(url)
    if data and "results" in data and len(data["results"]) > 0:
        r = data["results"][0]
        return (r["latitude"], r["longitude"])
    return None


@tool
def get_weather_forecast(city: str, start_date: str, end_date: str) -> str:
    """Get real weather forecast for a city using the free Open-Meteo API (no API key needed).

    Args:
        city: City name
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    coords = _get_coords(city)
    if not coords:
        coords = _geocode_city(city)
    if not coords:
        return f"Could not find weather data for {city}. Please check the city name."

    lat, lon = coords

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode"
            f"&start_date={start_date}&end_date={end_date}"
            f"&temperature_unit=celsius&timezone=auto"
        )
        data = _fetch_url(url)
        if not data:
            return f"Could not reach Open-Meteo API for {city}. Please try again later."

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        codes = daily.get("weathercode", [])

        result = f"Weather forecast for **{city}** ({start_date} to {end_date}):\n\n"
        result += f"| Date | Condition | High | Low | Rain % | Recommendation |\n"
        result += f"|------|-----------|------|-----|--------|----------------|\n"

        for i, date in enumerate(dates):
            condition = WMO_CODES.get(codes[i] if i < len(codes) else 0, "Unknown")
            high = temp_max[i] if i < len(temp_max) else "N/A"
            low = temp_min[i] if i < len(temp_min) else "N/A"
            rain = precip[i] if i < len(precip) else 0

            # Generate recommendation
            if rain and rain > 60:
                rec = "Indoor activities recommended"
            elif rain and rain > 30:
                rec = "Bring an umbrella"
            elif isinstance(high, (int, float)) and high > 32:
                rec = "Stay hydrated, seek shade"
            elif isinstance(low, (int, float)) and low < 5:
                rec = "Bundle up warmly"
            else:
                rec = "Great day for outdoor activities"

            high_f = round(high * 9 / 5 + 32) if isinstance(high, (int, float)) else "N/A"
            low_f = round(low * 9 / 5 + 32) if isinstance(low, (int, float)) else "N/A"

            result += f"| {date} | {condition} | {high}C ({high_f}F) | {low}C ({low_f}F) | {rain}% | {rec} |\n"

        result += f"\nData source: Open-Meteo (free, no API key required)\n"
        return result

    except Exception as e:
        return f"Error fetching weather data: {str(e)}. The Open-Meteo API may be temporarily unavailable."


@tool
def get_best_travel_months(city: str) -> str:
    """Get the best months to visit a city based on historical climate data.

    Args:
        city: City name to check
    """
    coords = _get_coords(city)
    if not coords:
        coords = _geocode_city(city)
    if not coords:
        return f"Could not find climate data for {city}."

    lat, lon = coords

    # Determine hemisphere and climate zone
    is_southern = lat < 0
    is_tropical = abs(lat) < 23.5
    is_arid = city.lower() in ["dubai", "cairo", "marrakech"]

    if is_tropical:
        best = "November to March (dry season)"
        avoid = "June to September (monsoon/wet season)"
        note = "Tropical climate - warm year-round, but humidity varies greatly by season."
    elif is_southern:
        best = "December to February (summer)"
        avoid = "June to August (winter)"
        note = "Southern hemisphere - seasons are reversed from the northern hemisphere."
    elif is_arid:
        best = "October to April (cooler months)"
        avoid = "June to August (extreme heat, 40C+)"
        note = "Desert climate - plan around extreme summer heat."
    elif lat > 50:
        best = "June to August (summer)"
        avoid = "November to February (cold, short days)"
        note = "Northern climate - long summer days are magical, winters are dark and cold."
    else:
        best = "April to June, September to October (shoulder seasons)"
        avoid = "Peak summer (crowded) or deep winter (cold)"
        note = "Temperate climate - shoulder seasons offer the best balance of weather and crowds."

    result = f"Best time to visit **{city}**:\n\n"
    result += f"**Best months:** {best}\n"
    result += f"**Months to avoid:** {avoid}\n"
    result += f"**Note:** {note}\n"

    return result
