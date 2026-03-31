"""Agent Internals Visualizer - Streamlit page for exploring agent architecture."""

import json
import time
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(
    page_title="VoyageAI - Agent Internals",
    page_icon="🔬",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    .viz-header {
        background: linear-gradient(135deg, #1a1a3e 0%, #2d1b69 100%);
        padding: 2rem 3rem; border-radius: 16px; color: white;
        margin-bottom: 2rem; text-align: center;
        border: 1px solid rgba(102, 126, 234, 0.3);
    }
    .viz-header h1 { font-size: 2.2rem; font-weight: 700; margin: 0; }
    .viz-header p { opacity: 0.8; margin-top: 0.3rem; }

    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px; padding: 1.2rem; color: white; text-align: center;
    }
    .metric-card h2 { font-size: 2rem; margin: 0; font-weight: 800; }
    .metric-card p { font-size: 0.85rem; margin: 0; opacity: 0.85; }

    .agent-trace {
        background: #1a1a2e; border: 1px solid #2d2d5e;
        border-radius: 12px; padding: 1.5rem; margin: 0.5rem 0;
        font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
    }

    .trace-step {
        padding: 0.5rem 1rem; margin: 0.3rem 0;
        border-left: 3px solid #667eea; background: rgba(102, 126, 234, 0.05);
        border-radius: 0 8px 8px 0;
    }

    .trace-tool { border-left-color: #f093fb; background: rgba(240, 147, 251, 0.05); }
    .trace-result { border-left-color: #48bb78; background: rgba(72, 187, 120, 0.05); }
    .trace-error { border-left-color: #f56565; background: rgba(245, 101, 101, 0.05); }

    .score-bar {
        height: 8px; border-radius: 4px; background: #2d2d5e;
        overflow: hidden; margin-top: 0.3rem;
    }
    .score-fill { height: 100%; border-radius: 4px; transition: width 1s ease; }
    .score-excellent { background: linear-gradient(90deg, #48bb78, #38a169); }
    .score-good { background: linear-gradient(90deg, #ecc94b, #d69e2e); }
    .score-poor { background: linear-gradient(90deg, #f56565, #e53e3e); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="viz-header">
    <h1>Agent Internals Visualizer</h1>
    <p>Deep dive into agent execution, tool calls, traces, and evaluation scores</p>
</div>
""", unsafe_allow_html=True)

# Load evaluation data
try:
    with open("evaluation/eval_results.json") as f:
        eval_data = json.load(f)
except FileNotFoundError:
    eval_data = None
    st.warning("No evaluation data found. Run: `python3 -m evaluation.evaluator` first.")

# Tab layout
tab1, tab2, tab3, tab4 = st.tabs([
    "Evaluation Dashboard", "Agent Traces", "Tool Inspector", "Architecture Deep Dive"
])

# ============ TAB 1: Evaluation Dashboard ============
with tab1:
    if eval_data:
        # Top metrics
        cols = st.columns(4)
        total_score = eval_data.get("total_score", 0)
        total_tools = sum(len(ar["tool_results"]) for ar in eval_data.get("agent_results", []))
        pass_count = sum(1 for ar in eval_data.get("agent_results", []) if ar["pass_rate"] == 100)
        total_agents = len(eval_data.get("agent_results", []))

        with cols[0]:
            color = "#48bb78" if total_score >= 80 else "#ecc94b" if total_score >= 60 else "#f56565"
            st.markdown(f'<div class="metric-card"><h2 style="color:{color}">{total_score:.1f}</h2><p>Overall Score /100</p></div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<div class="metric-card"><h2>{total_tools}</h2><p>Tool Calls Evaluated</p></div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<div class="metric-card"><h2>{pass_count}/{total_agents}</h2><p>Agents Passed</p></div>', unsafe_allow_html=True)
        with cols[3]:
            avg_latency = sum(ar["latency_avg_ms"] for ar in eval_data.get("agent_results", [])) / max(total_agents, 1)
            st.markdown(f'<div class="metric-card"><h2>{avg_latency:.0f}ms</h2><p>Avg Latency</p></div>', unsafe_allow_html=True)

        st.markdown("---")

        # Agent scores breakdown
        st.markdown("### Agent Scores by Destination")

        # Group by agent type
        agent_types = {}
        for ar in eval_data.get("agent_results", []):
            name = ar["agent_name"]
            if name not in agent_types:
                agent_types[name] = []
            agent_types[name].append(ar)

        for agent_name, results in agent_types.items():
            avg_score = sum(r["overall_score"] for r in results) / len(results)
            avg_latency = sum(r["latency_avg_ms"] for r in results) / len(results)
            pass_rate = sum(1 for r in results if r["pass_rate"] == 100) / len(results) * 100

            score_class = "score-excellent" if avg_score >= 90 else "score-good" if avg_score >= 70 else "score-poor"

            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                icon = {"Flight": "✈️", "Hotel": "🏨", "Activity": "🎯", "Weather": "🌤️", "Budget": "💰"}.get(agent_name.split()[0], "🤖")
                st.markdown(f"**{icon} {agent_name}**")
                st.markdown(f'<div class="score-bar"><div class="score-fill {score_class}" style="width:{avg_score}%"></div></div>', unsafe_allow_html=True)
            with col2:
                st.metric("Score", f"{avg_score:.0f}/100")
            with col3:
                st.metric("Latency", f"{avg_latency:.0f}ms")
            with col4:
                st.metric("Pass Rate", f"{pass_rate:.0f}%")

        st.markdown("---")

        # Detailed tool results
        st.markdown("### Detailed Tool Results")

        for ar in eval_data.get("agent_results", []):
            with st.expander(f"{ar['agent_name']} — Score: {ar['overall_score']:.0f}/100"):
                for tr in ar["tool_results"]:
                    status = "PASS" if tr["passed"] else "FAIL"
                    status_color = "#48bb78" if tr["passed"] else "#f56565"

                    st.markdown(f"""
                    **`{tr['tool_name']}`** <span style="color:{status_color};font-weight:bold">[{status}]</span> — {tr['latency_ms']:.1f}ms
                    """, unsafe_allow_html=True)

                    # Score breakdown
                    score_cols = st.columns(len(tr["scores"]))
                    for i, (check, score) in enumerate(tr["scores"].items()):
                        with score_cols[i]:
                            color = "#48bb78" if score > 0 else "#f56565"
                            st.markdown(f"<small style='color:{color}'>{check}: {score:.0f}</small>", unsafe_allow_html=True)

                    if tr["issues"]:
                        for issue in tr["issues"]:
                            st.caption(f"⚠️ {issue}")
    else:
        st.info("Run the evaluation first: `python3 -m evaluation.evaluator`")


# ============ TAB 2: Agent Traces ============
with tab2:
    st.markdown("### Live Agent Execution Trace")
    st.markdown("Watch how agents process a request step by step.")

    dest_input = st.selectbox("Select destination for trace:", ["Tokyo", "Paris", "Bangkok", "Barcelona", "New York", "Bali"])

    if st.button("Run Agent Trace", key="trace_btn"):
        trace_container = st.container()

        with trace_container:
            # Simulate agent execution trace
            agents_trace = [
                {
                    "agent": "Supervisor",
                    "icon": "🎯",
                    "steps": [
                        ("think", f"Received request: Plan trip to {dest_input}"),
                        ("decide", "Execution order: Weather → Flight → Hotel → Activity → Budget → Itinerary"),
                        ("route", "Dispatching to Weather Agent first..."),
                    ]
                },
                {
                    "agent": "Weather Agent",
                    "icon": "🌤️",
                    "steps": [
                        ("think", f"Need forecast for {dest_input}. Looking up coordinates..."),
                        ("tool_call", f"get_weather_forecast(city='{dest_input}', start_date='...', end_date='...')"),
                        ("tool_result", "Retrieved 7-day forecast from Open-Meteo API"),
                        ("tool_call", f"get_best_travel_months(city='{dest_input}')"),
                        ("tool_result", "Identified optimal travel seasons"),
                        ("output", f"Completed: Weather data for {dest_input} ready"),
                    ]
                },
                {
                    "agent": "Flight Agent",
                    "icon": "✈️",
                    "steps": [
                        ("think", f"Searching flights to {dest_input}..."),
                        ("tool_call", f"search_flights(origin='New York', destination='{dest_input}', ...)"),
                        ("tool_result", "Found 6 flight options from 6 airlines"),
                        ("tool_call", f"compare_flight_prices(origin='New York', destination='{dest_input}', ...)"),
                        ("tool_result", "Generated comparison links for 4 booking platforms"),
                        ("output", "Completed: Best flights identified with booking links"),
                    ]
                },
                {
                    "agent": "Hotel Agent",
                    "icon": "🏨",
                    "steps": [
                        ("think", f"Finding accommodations in {dest_input}..."),
                        ("tool_call", f"search_hotels(destination='{dest_input}', ...)"),
                        ("tool_result", f"Found hotels across budget/mid/luxury tiers"),
                        ("output", "Completed: Hotel options with Booking.com links"),
                    ]
                },
                {
                    "agent": "Activity Agent",
                    "icon": "🎯",
                    "steps": [
                        ("think", f"Discovering things to do in {dest_input}..."),
                        ("tool_call", f"search_activities(destination='{dest_input}', categories='all')"),
                        ("tool_result", "Found mix of free and paid activities"),
                        ("tool_call", f"get_restaurant_recommendations(destination='{dest_input}', ...)"),
                        ("tool_result", "Generated restaurant search links"),
                        ("output", "Completed: Activities and dining recommendations ready"),
                    ]
                },
                {
                    "agent": "Budget Agent",
                    "icon": "💰",
                    "steps": [
                        ("think", "Calculating budget breakdown with flight and hotel data..."),
                        ("tool_call", f"calculate_trip_budget(destination='{dest_input}', ...)"),
                        ("tool_result", "Generated detailed cost breakdown by category"),
                        ("tool_call", f"optimize_budget(total_budget=3000, destination='{dest_input}', ...)"),
                        ("tool_result", "Optimized allocation: 30% flights, 30% hotels, 18% food, ..."),
                        ("tool_call", f"get_currency_info(destination='{dest_input}')"),
                        ("tool_result", "Retrieved exchange rates and tips"),
                        ("output", "Completed: Budget plan with currency info"),
                    ]
                },
                {
                    "agent": "Itinerary Agent",
                    "icon": "📋",
                    "steps": [
                        ("think", "Compiling all agent reports into day-by-day itinerary..."),
                        ("compile", "Gathering: weather + flights + hotels + activities + budget"),
                        ("optimize", "Scheduling indoor activities on rainy days"),
                        ("optimize", "Grouping nearby attractions to minimize transit"),
                        ("output", "Completed: Full day-by-day itinerary with booking links!"),
                    ]
                },
            ]

            total_start = time.time()

            for agent_data in agents_trace:
                st.markdown(f"### {agent_data['icon']} {agent_data['agent']}")

                for step_type, step_text in agent_data["steps"]:
                    time.sleep(0.15)

                    if step_type == "think":
                        st.markdown(f'<div class="trace-step">💭 <b>Think:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "decide":
                        st.markdown(f'<div class="trace-step">🧠 <b>Decision:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "route":
                        st.markdown(f'<div class="trace-step">➡️ <b>Route:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "tool_call":
                        st.markdown(f'<div class="trace-step trace-tool">🔧 <b>Tool Call:</b> <code>{step_text}</code></div>', unsafe_allow_html=True)
                    elif step_type == "tool_result":
                        st.markdown(f'<div class="trace-step trace-result">✅ <b>Result:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "compile":
                        st.markdown(f'<div class="trace-step">📦 <b>Compile:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "optimize":
                        st.markdown(f'<div class="trace-step">⚡ <b>Optimize:</b> {step_text}</div>', unsafe_allow_html=True)
                    elif step_type == "output":
                        st.markdown(f'<div class="trace-step trace-result">🏁 <b>{step_text}</b></div>', unsafe_allow_html=True)

            total_time = (time.time() - total_start)
            st.success(f"Trace complete! Total visualization time: {total_time:.1f}s")


# ============ TAB 3: Tool Inspector ============
with tab3:
    st.markdown("### Tool Inspector")
    st.markdown("Test individual agent tools with custom parameters and see raw output.")

    tool_choice = st.selectbox("Select Tool:", [
        "search_flights", "compare_flight_prices",
        "search_hotels", "compare_hotel_prices",
        "search_activities", "get_restaurant_recommendations",
        "get_weather_forecast", "get_best_travel_months",
        "calculate_trip_budget", "optimize_budget", "get_currency_info",
    ])

    st.markdown("#### Parameters")

    if tool_choice == "search_flights":
        c1, c2 = st.columns(2)
        with c1:
            p_origin = st.text_input("Origin", "New York", key="tf_origin")
            p_dep = st.text_input("Departure Date", "2025-07-01", key="tf_dep")
        with c2:
            p_dest = st.text_input("Destination", "Tokyo", key="tf_dest")
            p_ret = st.text_input("Return Date", "2025-07-08", key="tf_ret")
        p_pax = st.number_input("Passengers", 1, 10, 1, key="tf_pax")

        if st.button("Execute Tool", key="exec_flights"):
            from tools.flight_tools import search_flights
            start_t = time.time()
            result = search_flights.invoke({
                "origin": p_origin, "destination": p_dest,
                "departure_date": p_dep, "return_date": p_ret, "passengers": p_pax,
            })
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    elif tool_choice == "search_hotels":
        c1, c2 = st.columns(2)
        with c1:
            p_dest = st.text_input("Destination", "Paris", key="th_dest")
            p_ci = st.text_input("Check-in", "2025-07-01", key="th_ci")
        with c2:
            p_co = st.text_input("Check-out", "2025-07-08", key="th_co")
            p_max = st.number_input("Max Price/Night", 50, 2000, 300, key="th_max")

        if st.button("Execute Tool", key="exec_hotels"):
            from tools.hotel_tools import search_hotels
            start_t = time.time()
            result = search_hotels.invoke({
                "destination": p_dest, "check_in": p_ci,
                "check_out": p_co, "guests": 2, "max_price": p_max,
            })
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    elif tool_choice == "search_activities":
        p_dest = st.text_input("Destination", "Barcelona", key="ta_dest")
        p_cat = st.text_input("Categories (or 'all')", "all", key="ta_cat")
        p_budget = st.number_input("Max Budget", 0, 500, 100, key="ta_budget")

        if st.button("Execute Tool", key="exec_activities"):
            from tools.activity_tools import search_activities
            start_t = time.time()
            result = search_activities.invoke({
                "destination": p_dest, "categories": p_cat, "max_budget": p_budget,
            })
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    elif tool_choice == "get_weather_forecast":
        c1, c2, c3 = st.columns(3)
        with c1:
            p_city = st.text_input("City", "Tokyo", key="tw_city")
        with c2:
            p_start = st.text_input("Start Date", "2025-07-01", key="tw_start")
        with c3:
            p_end = st.text_input("End Date", "2025-07-07", key="tw_end")

        if st.button("Execute Tool", key="exec_weather"):
            from tools.weather_tools import get_weather_forecast
            start_t = time.time()
            result = get_weather_forecast.invoke({
                "city": p_city, "start_date": p_start, "end_date": p_end,
            })
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    elif tool_choice == "calculate_trip_budget":
        c1, c2 = st.columns(2)
        with c1:
            p_dest = st.text_input("Destination", "Tokyo", key="tb_dest")
            p_days = st.number_input("Days", 1, 30, 7, key="tb_days")
            p_flight = st.number_input("Flight Cost", 100, 5000, 700, key="tb_flight")
        with c2:
            p_travelers = st.number_input("Travelers", 1, 10, 1, key="tb_travelers")
            p_hotel = st.number_input("Hotel/Night", 20, 2000, 120, key="tb_hotel")
            p_style = st.selectbox("Style", ["budget", "mid", "luxury"], index=1, key="tb_style")

        if st.button("Execute Tool", key="exec_budget"):
            from tools.budget_tools import calculate_trip_budget
            start_t = time.time()
            result = calculate_trip_budget.invoke({
                "destination": p_dest, "num_days": p_days, "num_travelers": p_travelers,
                "flight_cost": p_flight, "hotel_cost_per_night": p_hotel, "travel_style": p_style,
            })
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    elif tool_choice == "get_currency_info":
        p_dest = st.text_input("Destination", "Bangkok", key="tc_dest")
        if st.button("Execute Tool", key="exec_currency"):
            from tools.budget_tools import get_currency_info
            start_t = time.time()
            result = get_currency_info.invoke({"destination": p_dest})
            elapsed = (time.time() - start_t) * 1000
            st.metric("Latency", f"{elapsed:.1f}ms")
            st.markdown(result)

    else:
        st.info(f"Select parameters for {tool_choice} and click Execute.")


# ============ TAB 4: Architecture Deep Dive ============
with tab4:
    st.markdown("### Architecture Deep Dive")

    st.markdown("""
    #### LangGraph State Machine

    VoyageAI uses LangGraph's `StateGraph` to orchestrate agent execution. Each data-gathering agent
    calls tools **directly** (no LLM needed - fast and free). Only the final Itinerary Agent uses an
    LLM to compile results into a polished day-by-day plan.
    """)

    st.code("""
    # State flows through the graph:
    AgentState = {
        "messages": [...],           # Chat history (append-only)
        "travel_request": {...},     # User's trip details
        "flights": [...],            # Flight agent results
        "hotels": [...],             # Hotel agent results
        "activities": [...],         # Activity recommendations
        "weather": [...],            # Weather forecasts
        "budget": {...},             # Budget breakdown
        "itinerary": "",             # Final compiled plan
        "agent_logs": [...],         # Execution trace
        "current_agent": "",         # Active agent name
    }
    """, language="python")

    st.markdown("#### Execution Flow")
    st.markdown("""
    ```
    START
      │
      ├─ Weather Agent (direct tool calls - no LLM)
      │    ├─ get_weather_forecast() → Open-Meteo API
      │    └─ get_best_travel_months() → Climate analysis
      │
      ├─ Flight Agent (direct tool calls - no LLM)
      │    ├─ search_flights() → Route pricing engine
      │    └─ compare_flight_prices() → Platform links
      │
      ├─ Hotel Agent (direct tool calls - no LLM)
      │    └─ search_hotels() → Hotel database
      │
      ├─ Activity Agent (direct tool calls - no LLM)
      │    ├─ search_activities() → Curated database
      │    └─ get_restaurant_recommendations() → Search links
      │
      ├─ Budget Agent (direct tool calls - no LLM)
      │    ├─ calculate_trip_budget() → Cost modeling
      │    ├─ optimize_budget() → Allocation engine
      │    └─ get_currency_info() → Exchange data
      │
      └─ Itinerary Agent (LLM compilation)
           └─ LLM compiles all reports → Day-by-day plan
               (Falls back to raw data if no LLM configured)
      │
      END → Return itinerary to user
    ```
    """)

    st.markdown("#### Agent Tool Mapping")

    tool_data = {
        "Agent": ["Weather", "Weather", "Flight", "Flight", "Hotel", "Hotel", "Activity", "Activity", "Budget", "Budget", "Budget", "Itinerary"],
        "Tool": ["get_weather_forecast", "get_best_travel_months", "search_flights", "compare_flight_prices", "search_hotels", "compare_hotel_prices", "search_activities", "get_restaurant_recommendations", "calculate_trip_budget", "optimize_budget", "get_currency_info", "LLM Compilation"],
        "Data Source": ["Open-Meteo API (free)", "Climate model", "Route pricing engine", "Google/Skyscanner/Kayak links", "Hotel database (30+ cities)", "Booking/Expedia/Google links", "Curated DB (10+ cities)", "Google Maps/TripAdvisor links", "City cost database", "Allocation algorithm", "Exchange rate data", "All agent reports"],
        "Cost": ["Free", "Free", "Free", "Free", "Free", "Free", "Free", "Free", "Free", "Free", "Free", "LLM tokens"],
    }
    st.dataframe(tool_data, use_container_width=True)

    st.markdown("#### LLM Provider Support")
    st.markdown("""
    | Provider | Model | Cost | Speed | Setup |
    |----------|-------|------|-------|-------|
    | **Groq** | llama-3.3-70b-versatile | **FREE** | Blazing fast | [console.groq.com](https://console.groq.com) |
    | **Google** | gemini-2.0-flash | **FREE** | Fast | [aistudio.google.com](https://aistudio.google.com) |
    | **OpenAI** | gpt-4o-mini | ~$0.15/1M tokens | Fast | [platform.openai.com](https://platform.openai.com) |
    """)
