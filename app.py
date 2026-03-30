"""VoyageAI - Multi-Agent Travel Planner Streamlit UI."""

import streamlit as st
import time
from datetime import datetime, timedelta

st.set_page_config(
    page_title="VoyageAI - AI Travel Planner",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for sleek UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 3rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }

    .main-header h1 {
        font-size: 2.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.02em;
    }

    .main-header p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }

    .agent-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
    }

    .agent-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        transform: translateY(-1px);
    }

    .agent-card.active {
        border-color: #667eea;
        border-width: 2px;
        background: #f7f8ff;
    }

    .agent-card.completed {
        border-color: #48bb78;
        background: #f0fff4;
    }

    .agent-icon {
        font-size: 1.8rem;
        margin-right: 0.5rem;
    }

    .agent-name {
        font-weight: 600;
        font-size: 1rem;
        color: #2d3748;
    }

    .agent-status {
        font-size: 0.85rem;
        color: #718096;
        margin-top: 0.3rem;
    }

    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .status-waiting { background: #edf2f7; color: #718096; }
    .status-running { background: #ebf8ff; color: #3182ce; }
    .status-done { background: #f0fff4; color: #38a169; }

    .itinerary-section {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 2rem;
        margin-top: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

    .trip-stat {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.2rem;
        color: white;
        text-align: center;
    }

    .trip-stat h3 {
        font-size: 1.8rem;
        margin: 0;
        font-weight: 700;
    }

    .trip-stat p {
        font-size: 0.85rem;
        opacity: 0.85;
        margin: 0;
    }

    div[data-testid="stSidebar"] {
        background: #f8f9fc;
    }

    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.7rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        width: 100%;
        transition: all 0.3s;
    }

    .stButton button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }

    .workflow-arrow {
        text-align: center;
        font-size: 1.5rem;
        color: #a0aec0;
        margin: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>VoyageAI</h1>
    <p>Multi-Agent AI Travel Planner powered by LangGraph, LangChain & Langfuse</p>
</div>
""", unsafe_allow_html=True)

# Sidebar - Trip Configuration
with st.sidebar:
    st.markdown("### Configure Your Trip")

    destination = st.text_input("Destination", value="Tokyo", placeholder="e.g., Paris, Tokyo, Bali...")
    origin = st.text_input("Departing From", value="New York", placeholder="e.g., New York, London...")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() + timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now() + timedelta(days=37))

    budget = st.slider("Total Budget (USD)", min_value=500, max_value=20000, value=3000, step=100)
    travelers = st.number_input("Travelers", min_value=1, max_value=10, value=1)

    preferences = st.text_area(
        "Travel Preferences",
        value="Balanced mix of culture, food, and adventure. Prefer authentic local experiences.",
        height=80,
    )

    st.markdown("---")

    travel_style = st.select_slider(
        "Travel Style",
        options=["Budget", "Comfortable", "Luxury"],
        value="Comfortable",
    )

    st.markdown("---")
    st.markdown("### Agent Architecture")
    st.markdown("""
    ```
    Supervisor
       |
    Weather --> Flight
       |         |
    Hotel --> Activity
       |
    Budget
       |
    Itinerary
    ```
    """)

    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; font-size: 0.8rem; color: #a0aec0;">
        Built by <strong>Sugeerth</strong><br/>
        Powered by LangGraph + LangChain + Langfuse
    </div>
    """, unsafe_allow_html=True)

# Main Content
num_days = max((end_date - start_date).days, 1)

# Trip overview stats
cols = st.columns(4)
with cols[0]:
    st.markdown(f"""
    <div class="trip-stat">
        <h3>{destination}</h3>
        <p>Destination</p>
    </div>
    """, unsafe_allow_html=True)
with cols[1]:
    st.markdown(f"""
    <div class="trip-stat">
        <h3>{num_days} days</h3>
        <p>{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}</p>
    </div>
    """, unsafe_allow_html=True)
with cols[2]:
    st.markdown(f"""
    <div class="trip-stat">
        <h3>${budget:,}</h3>
        <p>${budget // num_days}/day budget</p>
    </div>
    """, unsafe_allow_html=True)
with cols[3]:
    st.markdown(f"""
    <div class="trip-stat">
        <h3>{travelers}</h3>
        <p>Traveler(s)</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# Plan button
if st.button("Plan My Trip", use_container_width=True):
    # Agent status tracking
    agents_config = [
        {"name": "Weather Agent", "icon": "🌤️", "key": "weather", "desc": "Fetching weather forecast..."},
        {"name": "Flight Agent", "icon": "✈️", "key": "flight", "desc": "Searching for best flights..."},
        {"name": "Hotel Agent", "icon": "🏨", "key": "hotel", "desc": "Finding accommodations..."},
        {"name": "Activity Agent", "icon": "🎯", "key": "activity", "desc": "Discovering activities..."},
        {"name": "Budget Agent", "icon": "💰", "key": "budget", "desc": "Optimizing your budget..."},
        {"name": "Itinerary Agent", "icon": "📋", "key": "itinerary", "desc": "Compiling your itinerary..."},
    ]

    # Show agent status panel
    status_container = st.container()
    with status_container:
        st.markdown("### Agent Workflow")
        agent_status_cols = st.columns(6)

        status_placeholders = {}
        for i, agent in enumerate(agents_config):
            with agent_status_cols[i]:
                status_placeholders[agent["key"]] = st.empty()
                status_placeholders[agent["key"]].markdown(f"""
                <div class="agent-card">
                    <span class="agent-icon">{agent['icon']}</span>
                    <div class="agent-name">{agent['name']}</div>
                    <div class="agent-status">
                        <span class="status-badge status-waiting">Waiting</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Run the workflow
    result_container = st.container()

    try:
        from graph.workflow import run_travel_planner

        agent_results = {}

        def update_callback(agent_name, status, message):
            """Update the UI as agents complete."""
            agent_results[agent_name] = {"status": status, "message": message}

            for agent in agents_config:
                key = agent["key"]
                if key in agent_results:
                    status_placeholders[key].markdown(f"""
                    <div class="agent-card completed">
                        <span class="agent-icon">{agent['icon']}</span>
                        <div class="agent-name">{agent['name']}</div>
                        <div class="agent-status">
                            <span class="status-badge status-done">Done</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif key == agent_name:
                    status_placeholders[key].markdown(f"""
                    <div class="agent-card active">
                        <span class="agent-icon">{agent['icon']}</span>
                        <div class="agent-name">{agent['name']}</div>
                        <div class="agent-status">
                            <span class="status-badge status-running">Running...</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with st.spinner("🌍 Planning your perfect trip..."):
            itinerary = run_travel_planner(
                destination=destination,
                origin=origin,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                budget=budget,
                travelers=travelers,
                preferences=preferences,
                callback=update_callback,
            )

        # Mark all agents as done
        for agent in agents_config:
            key = agent["key"]
            status_placeholders[key].markdown(f"""
            <div class="agent-card completed">
                <span class="agent-icon">{agent['icon']}</span>
                <div class="agent-name">{agent['name']}</div>
                <div class="agent-status">
                    <span class="status-badge status-done">Done</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Display the itinerary
        with result_container:
            st.markdown("---")
            st.markdown("### Your Travel Itinerary")
            st.markdown(f"""
            <div class="itinerary-section">
            """, unsafe_allow_html=True)
            st.markdown(itinerary)
            st.markdown("</div>", unsafe_allow_html=True)

            # Download button
            st.download_button(
                label="Download Itinerary",
                data=itinerary,
                file_name=f"voyageai_{destination.lower().replace(' ', '_')}_itinerary.md",
                mime="text/markdown",
            )

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.info("Make sure your OPENAI_API_KEY is set in the .env file. Run: `cp .env.example .env` and add your key.")

else:
    # Show the demo/placeholder
    st.markdown("### How It Works")

    cols = st.columns(3)
    with cols[0]:
        st.markdown("""
        #### 1. Configure
        Set your destination, dates, budget, and preferences in the sidebar.
        """)
    with cols[1]:
        st.markdown("""
        #### 2. Plan
        Click "Plan My Trip" and watch 6 specialized AI agents collaborate in real-time.
        """)
    with cols[2]:
        st.markdown("""
        #### 3. Travel
        Get a complete day-by-day itinerary with booking links, weather forecasts, and budget tracking.
        """)

    st.markdown("---")
    st.markdown("### Agent Architecture")

    agent_cols = st.columns(6)
    agents_info = [
        ("🌤️", "Weather", "Real forecasts via Open-Meteo API"),
        ("✈️", "Flights", "Route pricing & booking links"),
        ("🏨", "Hotels", "Real hotels with platform comparison"),
        ("🎯", "Activities", "Curated local experiences"),
        ("💰", "Budget", "Smart allocation & currency info"),
        ("📋", "Itinerary", "Day-by-day compiled plan"),
    ]

    for i, (icon, name, desc) in enumerate(agents_info):
        with agent_cols[i]:
            st.markdown(f"""
            <div class="agent-card">
                <span class="agent-icon">{icon}</span>
                <div class="agent-name">{name} Agent</div>
                <div class="agent-status">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #a0aec0; padding: 2rem;">
        <p>VoyageAI uses <strong>LangGraph</strong> for multi-agent orchestration,
        <strong>LangChain</strong> for tool integration, and <strong>Langfuse</strong> for observability.</p>
        <p>Weather data from <strong>Open-Meteo</strong> (free, no API key). Booking links to
        <strong>Google Flights</strong>, <strong>Booking.com</strong>, <strong>Skyscanner</strong>, and more.</p>
    </div>
    """, unsafe_allow_html=True)
