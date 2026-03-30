"""Hotel search tools with realistic data generation."""

import random
from langchain_core.tools import tool

# Real hotel chains and boutique hotels by city
HOTEL_DATABASE = {
    "tokyo": [
        {"name": "Park Hyatt Tokyo", "stars": 5, "base_price": 450, "area": "Shinjuku", "style": "luxury"},
        {"name": "Shinjuku Granbell Hotel", "stars": 4, "base_price": 120, "area": "Shinjuku", "style": "modern"},
        {"name": "The Gate Hotel Asakusa", "stars": 4, "base_price": 130, "area": "Asakusa", "style": "boutique"},
        {"name": "Dormy Inn Akihabara", "stars": 3, "base_price": 80, "area": "Akihabara", "style": "budget"},
        {"name": "Hotel Gracery Shinjuku", "stars": 3, "base_price": 95, "area": "Shinjuku", "style": "modern"},
        {"name": "Aman Tokyo", "stars": 5, "base_price": 800, "area": "Otemachi", "style": "luxury"},
        {"name": "MUJI Hotel Ginza", "stars": 4, "base_price": 170, "area": "Ginza", "style": "minimalist"},
        {"name": "Hostel Chapter Two Tokyo", "stars": 2, "base_price": 35, "area": "Asakusa", "style": "hostel"},
    ],
    "paris": [
        {"name": "Hotel Le Marais", "stars": 4, "base_price": 180, "area": "Le Marais", "style": "boutique"},
        {"name": "Hotel Plaza Athenee", "stars": 5, "base_price": 650, "area": "Champs-Elysees", "style": "luxury"},
        {"name": "Generator Paris", "stars": 2, "base_price": 40, "area": "Canal Saint-Martin", "style": "hostel"},
        {"name": "Hotel Fabric", "stars": 4, "base_price": 150, "area": "Oberkampf", "style": "boutique"},
        {"name": "Maison Souquet", "stars": 5, "base_price": 380, "area": "Montmartre", "style": "luxury"},
        {"name": "Hotel Emile", "stars": 3, "base_price": 110, "area": "Le Marais", "style": "charming"},
        {"name": "Ibis Paris Montmartre", "stars": 2, "base_price": 75, "area": "Montmartre", "style": "budget"},
    ],
    "london": [
        {"name": "The Hoxton Shoreditch", "stars": 4, "base_price": 170, "area": "Shoreditch", "style": "trendy"},
        {"name": "The Ritz London", "stars": 5, "base_price": 700, "area": "Piccadilly", "style": "luxury"},
        {"name": "citizenM Tower of London", "stars": 3, "base_price": 120, "area": "City of London", "style": "modern"},
        {"name": "Point A Hotel King's Cross", "stars": 2, "base_price": 65, "area": "King's Cross", "style": "budget"},
        {"name": "The Ned", "stars": 5, "base_price": 450, "area": "City of London", "style": "luxury"},
        {"name": "Hub by Premier Inn Westminster", "stars": 3, "base_price": 85, "area": "Westminster", "style": "modern"},
    ],
    "barcelona": [
        {"name": "Hotel Casa Bonay", "stars": 4, "base_price": 160, "area": "Eixample", "style": "boutique"},
        {"name": "W Barcelona", "stars": 5, "base_price": 350, "area": "Barceloneta", "style": "luxury"},
        {"name": "Generator Barcelona", "stars": 2, "base_price": 30, "area": "Gracia", "style": "hostel"},
        {"name": "Hotel Neri", "stars": 4, "base_price": 220, "area": "Gothic Quarter", "style": "boutique"},
        {"name": "Yurbban Passage Hotel", "stars": 3, "base_price": 100, "area": "Eixample", "style": "modern"},
    ],
    "new york": [
        {"name": "The Standard High Line", "stars": 4, "base_price": 280, "area": "Meatpacking", "style": "trendy"},
        {"name": "Pod 51", "stars": 2, "base_price": 90, "area": "Midtown", "style": "budget"},
        {"name": "The Plaza Hotel", "stars": 5, "base_price": 600, "area": "Central Park", "style": "luxury"},
        {"name": "Arlo NoMad", "stars": 3, "base_price": 160, "area": "NoMad", "style": "modern"},
        {"name": "1 Hotel Brooklyn Bridge", "stars": 4, "base_price": 300, "area": "Brooklyn", "style": "eco-luxury"},
        {"name": "HI NYC Hostel", "stars": 1, "base_price": 45, "area": "Upper West Side", "style": "hostel"},
    ],
    "bangkok": [
        {"name": "Mandarin Oriental Bangkok", "stars": 5, "base_price": 250, "area": "Riverside", "style": "luxury"},
        {"name": "Lub d Bangkok Silom", "stars": 2, "base_price": 20, "area": "Silom", "style": "hostel"},
        {"name": "Hotel Muse Bangkok", "stars": 5, "base_price": 150, "area": "Langsuan", "style": "boutique"},
        {"name": "Ibis Bangkok Siam", "stars": 3, "base_price": 40, "area": "Siam", "style": "budget"},
        {"name": "The Siam", "stars": 5, "base_price": 350, "area": "Dusit", "style": "luxury"},
    ],
    "rome": [
        {"name": "Hotel de Russie", "stars": 5, "base_price": 500, "area": "Piazza del Popolo", "style": "luxury"},
        {"name": "Hotel Raphael", "stars": 4, "base_price": 200, "area": "Navona", "style": "boutique"},
        {"name": "The Yellow Hostel", "stars": 2, "base_price": 28, "area": "Termini", "style": "hostel"},
        {"name": "Chapter Roma", "stars": 4, "base_price": 160, "area": "Trastevere", "style": "modern"},
        {"name": "Hotel Adriano", "stars": 3, "base_price": 130, "area": "Pantheon", "style": "charming"},
    ],
    "bali": [
        {"name": "Four Seasons Bali at Sayan", "stars": 5, "base_price": 400, "area": "Ubud", "style": "luxury"},
        {"name": "The Slow Canggu", "stars": 4, "base_price": 120, "area": "Canggu", "style": "boutique"},
        {"name": "Kosta Hostel Seminyak", "stars": 2, "base_price": 15, "area": "Seminyak", "style": "hostel"},
        {"name": "COMO Uma Ubud", "stars": 5, "base_price": 250, "area": "Ubud", "style": "wellness"},
        {"name": "The Lawn Canggu", "stars": 3, "base_price": 65, "area": "Canggu", "style": "modern"},
    ],
}

# Generic hotels for cities not in database
GENERIC_HOTELS = [
    {"suffix": "Grand Hotel", "stars": 4, "base_price": 150, "style": "classic"},
    {"suffix": "Boutique Suites", "stars": 4, "base_price": 130, "style": "boutique"},
    {"suffix": "City Hostel", "stars": 2, "base_price": 35, "style": "hostel"},
    {"suffix": "Luxury Palace", "stars": 5, "base_price": 350, "style": "luxury"},
    {"suffix": "Budget Inn", "stars": 2, "base_price": 55, "style": "budget"},
    {"suffix": "Modern Hotel", "stars": 3, "base_price": 90, "style": "modern"},
]

AMENITIES = {
    5: ["Free WiFi", "Spa", "Pool", "Gym", "Restaurant", "Bar", "Room Service", "Concierge", "Valet Parking"],
    4: ["Free WiFi", "Pool", "Gym", "Restaurant", "Bar", "Room Service"],
    3: ["Free WiFi", "Gym", "Restaurant", "Breakfast Included"],
    2: ["Free WiFi", "Shared Kitchen", "Lounge", "Lockers"],
    1: ["Free WiFi", "Shared Kitchen", "Lockers"],
}


@tool
def search_hotels(destination: str, check_in: str, check_out: str, guests: int = 2, max_price: float = 500) -> str:
    """Search for hotels in a destination city.

    Args:
        destination: City to search hotels in
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        max_price: Maximum price per night in USD
    """
    dest_lower = destination.lower().strip()

    # Find matching city in database
    hotels_data = None
    for city_key, hotels in HOTEL_DATABASE.items():
        if city_key in dest_lower or dest_lower in city_key:
            hotels_data = hotels
            break

    if not hotels_data:
        # Generate generic hotels for unknown cities
        hotels_data = []
        for template in GENERIC_HOTELS:
            hotels_data.append({
                "name": f"{destination} {template['suffix']}",
                "stars": template["stars"],
                "base_price": template["base_price"],
                "area": "City Center",
                "style": template["style"],
            })

    # Calculate number of nights
    from datetime import datetime
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((d2 - d1).days, 1)
    except ValueError:
        nights = 3  # default

    results = []
    for hotel in hotels_data:
        # Add some price variation
        nightly_price = hotel["base_price"] * random.uniform(0.85, 1.2)
        nightly_price = round(nightly_price, 2)

        if nightly_price > max_price:
            continue

        total_price = round(nightly_price * nights, 2)
        rating = round(random.uniform(3.8, 4.9) if hotel["stars"] >= 4 else random.uniform(3.2, 4.3), 1)
        reviews = random.randint(200, 5000)
        amenities = AMENITIES.get(hotel["stars"], ["Free WiFi"])

        # Real booking links
        booking_url = f"https://www.booking.com/searchresults.html?ss={destination.replace(' ', '+')}&checkin={check_in}&checkout={check_out}"
        google_url = f"https://www.google.com/travel/hotels/{destination.replace(' ', '+')}?q={hotel['name'].replace(' ', '+')}&dates={check_in}+to+{check_out}"

        results.append({
            "name": hotel["name"],
            "stars": hotel["stars"],
            "style": hotel["style"],
            "area": hotel.get("area", "City Center"),
            "rating": rating,
            "reviews": reviews,
            "price_per_night": nightly_price,
            "total_price": total_price,
            "nights": nights,
            "amenities": amenities,
            "booking_url": booking_url,
            "google_url": google_url,
        })

    results.sort(key=lambda x: x["price_per_night"])

    result = f"Found {len(results)} hotels in {destination} ({nights} nights: {check_in} to {check_out}):\n\n"
    for i, h in enumerate(results, 1):
        stars = "+" * h["stars"]
        result += f"**{i}. {h['name']}** {'*' * h['stars']}\n"
        result += f"   Area: {h['area']} | Style: {h['style']}\n"
        result += f"   Rating: {h['rating']}/5.0 ({h['reviews']} reviews)\n"
        result += f"   Price: ${h['price_per_night']:.2f}/night | Total: ${h['total_price']:.2f} ({h['nights']} nights)\n"
        result += f"   Amenities: {', '.join(h['amenities'][:5])}\n"
        result += f"   Book: {h['booking_url']}\n\n"

    return result


@tool
def compare_hotel_prices(hotel_name: str, destination: str, check_in: str, check_out: str) -> str:
    """Compare hotel prices across booking platforms.

    Args:
        hotel_name: Name of the hotel
        destination: City where the hotel is located
        check_in: Check-in date
        check_out: Check-out date
    """
    encoded_hotel = hotel_name.replace(" ", "+")
    encoded_dest = destination.replace(" ", "+")

    platforms = [
        {"name": "Booking.com", "url": f"https://www.booking.com/searchresults.html?ss={encoded_hotel}+{encoded_dest}&checkin={check_in}&checkout={check_out}"},
        {"name": "Hotels.com", "url": f"https://www.hotels.com/search.do?q-destination={encoded_hotel}+{encoded_dest}&q-check-in={check_in}&q-check-out={check_out}"},
        {"name": "Expedia", "url": f"https://www.expedia.com/Hotel-Search?destination={encoded_dest}&startDate={check_in}&endDate={check_out}"},
        {"name": "Google Hotels", "url": f"https://www.google.com/travel/hotels/{encoded_dest}?q={encoded_hotel}&dates={check_in}+to+{check_out}"},
        {"name": "Trivago", "url": f"https://www.trivago.com/en-US/srl?search={encoded_hotel}+{encoded_dest}"},
    ]

    result = f"Price comparison for **{hotel_name}** in {destination}:\n\n"
    for p in platforms:
        result += f"**{p['name']}**: {p['url']}\n"

    result += "\nTip: Booking.com often has free cancellation. Check Google Hotels for the best price overview."
    return result
