"""Activity and attraction search tools with curated real data."""

import random
from langchain_core.tools import tool

# Curated real activities by city
ACTIVITIES_DATABASE = {
    "tokyo": [
        {"name": "Tsukiji Outer Market Food Tour", "category": "Food & Drink", "cost": 0, "duration": "2-3 hours", "rating": 4.8, "location": "Tsukiji", "description": "Explore the world's most famous fish market area. Try fresh sushi, tamagoyaki, and street food. Free to walk around, pay for food as you go."},
        {"name": "Meiji Shrine", "category": "Culture & History", "cost": 0, "duration": "1-2 hours", "rating": 4.7, "location": "Harajuku", "description": "Serene Shinto shrine surrounded by a 170-acre forest in the heart of Tokyo. Free entry."},
        {"name": "Senso-ji Temple", "category": "Culture & History", "cost": 0, "duration": "1-2 hours", "rating": 4.6, "location": "Asakusa", "description": "Tokyo's oldest temple with the iconic Kaminarimon gate and Nakamise shopping street."},
        {"name": "TeamLab Borderless", "category": "Art & Museums", "cost": 35, "duration": "2-3 hours", "rating": 4.9, "location": "Azabudai", "description": "Immersive digital art museum with stunning interactive installations."},
        {"name": "Akihabara Electric Town", "category": "Shopping & Entertainment", "cost": 0, "duration": "2-4 hours", "rating": 4.5, "location": "Akihabara", "description": "Electronics, anime, manga, and gaming paradise. Free to explore."},
        {"name": "Shibuya Crossing & Hachiko", "category": "Landmarks", "cost": 0, "duration": "30 min", "rating": 4.4, "location": "Shibuya", "description": "World's busiest pedestrian crossing and the famous loyal dog statue."},
        {"name": "Shinjuku Gyoen National Garden", "category": "Nature", "cost": 5, "duration": "2-3 hours", "rating": 4.7, "location": "Shinjuku", "description": "Beautiful 144-acre garden with Japanese, French, and English landscape sections."},
        {"name": "Robot Restaurant Show", "category": "Entertainment", "cost": 60, "duration": "1.5 hours", "rating": 4.3, "location": "Shinjuku", "description": "Wild neon-lit robot cabaret show - quintessential Tokyo weirdness."},
        {"name": "Ramen Street (Tokyo Station)", "category": "Food & Drink", "cost": 12, "duration": "1 hour", "rating": 4.6, "location": "Tokyo Station", "description": "Eight of Japan's best ramen shops in one underground corridor."},
        {"name": "Golden Gai Bar Hopping", "category": "Nightlife", "cost": 20, "duration": "2-3 hours", "rating": 4.5, "location": "Shinjuku", "description": "Tiny bars packed into narrow alleys - each fits 6-10 people with unique themes."},
    ],
    "paris": [
        {"name": "Louvre Museum", "category": "Art & Museums", "cost": 22, "duration": "3-4 hours", "rating": 4.7, "location": "1st Arrondissement", "description": "World's largest art museum. Home to the Mona Lisa and Venus de Milo. Free first Sunday of the month."},
        {"name": "Eiffel Tower", "category": "Landmarks", "cost": 26, "duration": "2-3 hours", "rating": 4.6, "location": "Champ de Mars", "description": "Iconic iron lattice tower. Book tickets online to skip the queue."},
        {"name": "Montmartre & Sacre-Coeur Walk", "category": "Culture & History", "cost": 0, "duration": "2-3 hours", "rating": 4.8, "location": "Montmartre", "description": "Charming hilltop neighborhood with street artists, cafes, and the white basilica. Free."},
        {"name": "Musee d'Orsay", "category": "Art & Museums", "cost": 16, "duration": "2-3 hours", "rating": 4.8, "location": "7th Arrondissement", "description": "Impressionist masterpieces in a stunning former railway station."},
        {"name": "Seine River Walk", "category": "Nature", "cost": 0, "duration": "1-2 hours", "rating": 4.7, "location": "Central Paris", "description": "Walk along the UNESCO World Heritage riverbanks. Free and beautiful at sunset."},
        {"name": "Le Marais Neighborhood Stroll", "category": "Culture & History", "cost": 0, "duration": "2-3 hours", "rating": 4.6, "location": "Le Marais", "description": "Historic Jewish quarter with trendy boutiques, galleries, and falafel shops."},
        {"name": "Versailles Palace", "category": "Culture & History", "cost": 21, "duration": "4-5 hours", "rating": 4.7, "location": "Versailles", "description": "Opulent royal palace with magnificent gardens. Take the RER C train."},
        {"name": "Latin Quarter Food Tour", "category": "Food & Drink", "cost": 15, "duration": "2 hours", "rating": 4.5, "location": "5th Arrondissement", "description": "Self-guided tour through bakeries, cheese shops, and wine bars."},
    ],
    "london": [
        {"name": "British Museum", "category": "Art & Museums", "cost": 0, "duration": "3-4 hours", "rating": 4.7, "location": "Bloomsbury", "description": "World-class museum with the Rosetta Stone, Egyptian mummies, and more. Free entry."},
        {"name": "Tower of London", "category": "Culture & History", "cost": 33, "duration": "2-3 hours", "rating": 4.6, "location": "City of London", "description": "Historic castle housing the Crown Jewels. Book online for discounts."},
        {"name": "Camden Market", "category": "Shopping & Entertainment", "cost": 0, "duration": "2-3 hours", "rating": 4.5, "location": "Camden", "description": "Eclectic market with street food, vintage clothing, and live music. Free entry."},
        {"name": "Hyde Park & Kensington Gardens", "category": "Nature", "cost": 0, "duration": "2-3 hours", "rating": 4.7, "location": "Westminster", "description": "350 acres of royal parkland in central London. Free."},
        {"name": "Tate Modern", "category": "Art & Museums", "cost": 0, "duration": "2-3 hours", "rating": 4.6, "location": "Bankside", "description": "Modern art in a converted power station on the Thames. Free entry."},
        {"name": "Borough Market", "category": "Food & Drink", "cost": 15, "duration": "1-2 hours", "rating": 4.8, "location": "Southwark", "description": "London's oldest food market with artisan producers and street food."},
        {"name": "Westminster Abbey to Big Ben Walk", "category": "Landmarks", "cost": 0, "duration": "1 hour", "rating": 4.7, "location": "Westminster", "description": "Walk past Parliament, Big Ben, and Westminster Abbey. Free to view from outside."},
    ],
    "barcelona": [
        {"name": "La Sagrada Familia", "category": "Culture & History", "cost": 26, "duration": "1.5-2 hours", "rating": 4.9, "location": "Eixample", "description": "Gaudi's masterpiece basilica - still under construction since 1882. Book tickets in advance."},
        {"name": "Park Guell", "category": "Nature", "cost": 10, "duration": "1.5-2 hours", "rating": 4.7, "location": "Gracia", "description": "Gaudi's whimsical public park with mosaic terraces and city views."},
        {"name": "La Boqueria Market", "category": "Food & Drink", "cost": 0, "duration": "1-2 hours", "rating": 4.6, "location": "Las Ramblas", "description": "Famous food market with fresh produce, tapas bars, and fruit smoothies."},
        {"name": "Gothic Quarter Walking Tour", "category": "Culture & History", "cost": 0, "duration": "2 hours", "rating": 4.7, "location": "Barri Gotic", "description": "Medieval streets with hidden plazas, Roman ruins, and the Cathedral. Free to walk."},
        {"name": "Barceloneta Beach", "category": "Nature", "cost": 0, "duration": "2-4 hours", "rating": 4.4, "location": "Barceloneta", "description": "Sandy city beach with chiringuitos (beach bars) and Mediterranean views."},
        {"name": "Tapas Crawl in El Born", "category": "Food & Drink", "cost": 25, "duration": "2-3 hours", "rating": 4.8, "location": "El Born", "description": "Self-guided tapas tour through trendy bars. Try patatas bravas, jamon, and cava."},
    ],
    "new york": [
        {"name": "Central Park", "category": "Nature", "cost": 0, "duration": "2-4 hours", "rating": 4.8, "location": "Manhattan", "description": "843-acre urban oasis. Free to explore - walk, bike, or row boats."},
        {"name": "Metropolitan Museum of Art", "category": "Art & Museums", "cost": 30, "duration": "3-4 hours", "rating": 4.8, "location": "Upper East Side", "description": "One of the world's greatest art museums. Pay-what-you-wish for NY residents."},
        {"name": "Brooklyn Bridge Walk", "category": "Landmarks", "cost": 0, "duration": "1 hour", "rating": 4.7, "location": "Brooklyn/Manhattan", "description": "Iconic bridge walk with stunning skyline views. Free."},
        {"name": "High Line Park", "category": "Nature", "cost": 0, "duration": "1-2 hours", "rating": 4.7, "location": "Chelsea", "description": "Elevated park on former railway tracks with art installations. Free."},
        {"name": "Chelsea Market", "category": "Food & Drink", "cost": 15, "duration": "1-2 hours", "rating": 4.6, "location": "Chelsea", "description": "Indoor food hall in a former Nabisco factory with diverse cuisines."},
        {"name": "Times Square & Broadway", "category": "Entertainment", "cost": 0, "duration": "1-2 hours", "rating": 4.3, "location": "Midtown", "description": "The neon heart of NYC. Free to walk through - budget extra for a show."},
        {"name": "Statue of Liberty & Ellis Island", "category": "Landmarks", "cost": 24, "duration": "4-5 hours", "rating": 4.7, "location": "Harbor", "description": "Iconic symbol of freedom. Ferry ticket includes both islands."},
        {"name": "DUMBO Brooklyn", "category": "Culture & History", "cost": 0, "duration": "2 hours", "rating": 4.6, "location": "Brooklyn", "description": "Trendy waterfront neighborhood with the famous Manhattan Bridge view. Free."},
    ],
    "bangkok": [
        {"name": "Grand Palace & Wat Phra Kaew", "category": "Culture & History", "cost": 15, "duration": "2-3 hours", "rating": 4.7, "location": "Rattanakosin", "description": "Thailand's most sacred temple complex with the Emerald Buddha."},
        {"name": "Chatuchak Weekend Market", "category": "Shopping & Entertainment", "cost": 0, "duration": "3-4 hours", "rating": 4.6, "location": "Chatuchak", "description": "World's largest outdoor market with 15,000+ stalls. Open weekends."},
        {"name": "Street Food on Yaowarat (Chinatown)", "category": "Food & Drink", "cost": 5, "duration": "2 hours", "rating": 4.8, "location": "Chinatown", "description": "Legendary street food scene. Try pad thai, mango sticky rice, and boat noodles."},
        {"name": "Wat Arun (Temple of Dawn)", "category": "Culture & History", "cost": 3, "duration": "1 hour", "rating": 4.6, "location": "Thonburi", "description": "Stunning riverside temple with intricate porcelain decoration."},
        {"name": "Khao San Road", "category": "Nightlife", "cost": 0, "duration": "2-3 hours", "rating": 4.2, "location": "Banglamphu", "description": "Backpacker hub with bars, street food, and cheap shopping. Free to walk."},
        {"name": "Floating Market Day Trip", "category": "Culture & History", "cost": 10, "duration": "4-5 hours", "rating": 4.5, "location": "Damnoen Saduak", "description": "Traditional market on canals where vendors sell from boats."},
    ],
    "rome": [
        {"name": "Colosseum", "category": "Culture & History", "cost": 18, "duration": "2-3 hours", "rating": 4.8, "location": "Centro Storico", "description": "Ancient amphitheater that held 50,000 spectators. Book skip-the-line tickets."},
        {"name": "Vatican Museums & Sistine Chapel", "category": "Art & Museums", "cost": 17, "duration": "3-4 hours", "rating": 4.7, "location": "Vatican City", "description": "Michelangelo's ceiling and vast art collections. Free last Sunday of the month."},
        {"name": "Trastevere Evening Walk", "category": "Culture & History", "cost": 0, "duration": "2 hours", "rating": 4.7, "location": "Trastevere", "description": "Charming neighborhood with cobblestone streets, trattorias, and nightlife. Free."},
        {"name": "Pantheon", "category": "Culture & History", "cost": 5, "duration": "30 min-1 hour", "rating": 4.8, "location": "Centro Storico", "description": "2000-year-old temple with the world's largest unreinforced concrete dome."},
        {"name": "Trevi Fountain & Spanish Steps", "category": "Landmarks", "cost": 0, "duration": "1 hour", "rating": 4.6, "location": "Centro Storico", "description": "Iconic fountain and monumental stairway. Free - toss a coin for good luck."},
        {"name": "Testaccio Food Tour", "category": "Food & Drink", "cost": 10, "duration": "2 hours", "rating": 4.7, "location": "Testaccio", "description": "Self-guided tour of Rome's foodie neighborhood. Try supplì, carbonara, and gelato."},
    ],
    "bali": [
        {"name": "Tegallalang Rice Terraces", "category": "Nature", "cost": 2, "duration": "2-3 hours", "rating": 4.6, "location": "Ubud", "description": "Stunning cascading rice paddies with swings and walking paths."},
        {"name": "Uluwatu Temple Sunset", "category": "Culture & History", "cost": 5, "duration": "2 hours", "rating": 4.8, "location": "Uluwatu", "description": "Clifftop temple with incredible ocean sunset views and Kecak fire dance."},
        {"name": "Ubud Monkey Forest", "category": "Nature", "cost": 5, "duration": "1-2 hours", "rating": 4.5, "location": "Ubud", "description": "Sacred sanctuary with 700+ monkeys and ancient temple ruins."},
        {"name": "Seminyak Beach Club", "category": "Nightlife", "cost": 15, "duration": "3-4 hours", "rating": 4.4, "location": "Seminyak", "description": "Trendy beach clubs with pools, DJs, and sunset cocktails."},
        {"name": "Mount Batur Sunrise Trek", "category": "Adventure", "cost": 35, "duration": "5-6 hours", "rating": 4.7, "location": "Kintamani", "description": "Trek an active volcano for breathtaking sunrise views. Starts at 2 AM."},
        {"name": "Tirta Empul Water Temple", "category": "Culture & History", "cost": 3, "duration": "1-2 hours", "rating": 4.6, "location": "Tampaksiring", "description": "Sacred spring water temple where Balinese do purification rituals."},
    ],
}


def _get_city_activities(destination: str) -> list[dict]:
    dest_lower = destination.lower().strip()
    for city_key, activities in ACTIVITIES_DATABASE.items():
        if city_key in dest_lower or dest_lower in city_key:
            return activities
    return []


@tool
def search_activities(destination: str, categories: str = "all", max_budget: float = 100) -> str:
    """Search for activities and attractions in a destination.

    Args:
        destination: City to search activities in
        categories: Filter by category (e.g., "Food & Drink, Culture & History") or "all"
        max_budget: Maximum budget per activity in USD
    """
    activities = _get_city_activities(destination)

    if not activities:
        # Generate some generic activities
        result = f"Specific curated activities not available for {destination}. "
        result += f"Here are some recommendations:\n\n"
        result += f"1. Visit the main historical district (free walking tour)\n"
        result += f"2. Try local street food markets ($5-15)\n"
        result += f"3. Visit the top-rated museum ($10-25)\n"
        result += f"4. Explore local parks and nature areas (free)\n"
        result += f"5. Experience the nightlife district\n\n"
        result += f"Search on TripAdvisor: https://www.tripadvisor.com/Search?q={destination.replace(' ', '+')}\n"
        result += f"Google Things To Do: https://www.google.com/travel/things-to-do?q={destination.replace(' ', '+')}"
        return result

    # Filter by category
    if categories.lower() != "all":
        cat_list = [c.strip().lower() for c in categories.split(",")]
        filtered = [a for a in activities if any(c in a["category"].lower() for c in cat_list)]
        if filtered:
            activities = filtered

    # Filter by budget
    activities = [a for a in activities if a["cost"] <= max_budget]

    # Sort: free activities first, then by rating
    activities.sort(key=lambda x: (-x["rating"], x["cost"]))

    result = f"Top activities in **{destination}** ({len(activities)} found):\n\n"

    free_activities = [a for a in activities if a["cost"] == 0]
    paid_activities = [a for a in activities if a["cost"] > 0]

    if free_activities:
        result += "**FREE Activities:**\n"
        for a in free_activities:
            result += f"  - **{a['name']}** ({a['category']}) - {a['rating']}/5.0\n"
            result += f"    {a['description']}\n"
            result += f"    Duration: {a['duration']} | Location: {a['location']}\n\n"

    if paid_activities:
        result += "**Paid Activities:**\n"
        for a in paid_activities:
            result += f"  - **{a['name']}** ({a['category']}) - ${a['cost']} - {a['rating']}/5.0\n"
            result += f"    {a['description']}\n"
            result += f"    Duration: {a['duration']} | Location: {a['location']}\n\n"

    total_if_all = sum(a["cost"] for a in activities)
    result += f"\n**Total cost if doing all activities: ${total_if_all}**\n"
    result += f"\nMore ideas: https://www.google.com/travel/things-to-do?q={destination.replace(' ', '+')}"

    return result


@tool
def get_restaurant_recommendations(destination: str, cuisine_type: str = "local", budget_level: str = "medium") -> str:
    """Get restaurant recommendations for a destination.

    Args:
        destination: City name
        cuisine_type: Type of cuisine (local, international, street food, fine dining)
        budget_level: Budget level (budget, medium, splurge)
    """
    search_query = f"{cuisine_type}+restaurants+in+{destination.replace(' ', '+')}"
    google_url = f"https://www.google.com/maps/search/{search_query}"
    tripadvisor_url = f"https://www.tripadvisor.com/Search?q={search_query}"

    budget_tips = {
        "budget": "Look for street food stalls, local markets, and lunch specials. Eat where locals eat.",
        "medium": "Mix of casual restaurants and one or two nicer spots. Look for prix fixe lunch menus.",
        "splurge": "Reserve fine dining spots in advance. Check for tasting menus and Michelin-starred restaurants.",
    }

    result = f"Restaurant recommendations for **{destination}** ({cuisine_type}, {budget_level} budget):\n\n"
    result += f"**Tip:** {budget_tips.get(budget_level, budget_tips['medium'])}\n\n"
    result += f"**Find restaurants:**\n"
    result += f"- Google Maps: {google_url}\n"
    result += f"- TripAdvisor: {tripadvisor_url}\n"
    result += f"- Google Search: https://www.google.com/search?q=best+{search_query}\n"

    return result
