# VoyageAI - Multi-Agent Travel Planning System

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge)](https://sugeerth.github.io/agentic_data/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Powered-orange?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<div align="center">

  **A multi-agent travel planning system built on LangGraph (most agents call tools directly; an LLM only compiles the final itinerary).**

  *Plan a trip with agents for flights, hotels, activities, weather, budgets, and itinerary creation.*
</div>

---

## Architecture

VoyageAI runs a fixed linear LangGraph chain. Each node runs once, in order, appending its output to shared state; there is no supervisor or routing. Five of the six nodes call their tools directly (no LLM); only the final itinerary node uses an LLM (with a no-LLM fallback).

```
  START -> weather -> flight -> hotel -> activity -> budget -> itinerary -> END
```

### Nodes

| Node | Role | Tools |
|------|------|-------|
| **Weather** | Fetches a weather forecast and best-travel-months for the destination | `get_weather_forecast`, `get_best_travel_months` (Open-Meteo) |
| **Flight** | Generates flight options and a price-comparison link list | `search_flights`, `compare_flight_prices` (synthetic) |
| **Hotel** | Generates accommodation options within a budget cap | `search_hotels` (synthetic) |
| **Activity** | Generates attractions and restaurant recommendations | `search_activities`, `get_restaurant_recommendations` (synthetic) |
| **Budget** | Computes a trip budget, an allocation, and currency info | `calculate_trip_budget`, `optimize_budget`, `get_currency_info` |
| **Itinerary** | Concatenates the prior node outputs into a day-by-day plan (LLM, with no-LLM fallback) | LLM compilation |

**Data sources:** Weather is a real API call (Open-Meteo, no key needed). Flights, hotels, and activities are realistic synthetic/mock data — fares, times, and ratings are generated from hardcoded route/region tables (`random.uniform` pricing), while airline names and the booking deep-links (Google Flights, Skyscanner, Kayak, etc.) are real.

## Features

- **Linear LangGraph chain** - Six nodes run in a fixed order over shared state
- **Specialized nodes** - Each node owns its own domain tools
- **Observability (optional)** - Langfuse tracing when `LANGFUSE_*` keys are set
- **Streamlit UI** - Interactive chat interface with live agent status
- **Budget Optimization** - Allocation across flights, hotels, and activities

## Quick Start

### Prerequisites

- Python 3.10+
- A free LLM API key (choose one):
  - **Groq** (recommended, free): Get key at [console.groq.com](https://console.groq.com)
  - **Google Gemini** (free): Get key at [aistudio.google.com](https://aistudio.google.com)
  - **OpenAI** (paid): Get key at [platform.openai.com](https://platform.openai.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/sugeerth/agentic_data.git
cd agentic_data

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running the App

```bash
# Start the Streamlit UI
streamlit run app.py

# Or run in CLI mode
python3 main.py --destination "Tokyo" --dates "2025-04-01 to 2025-04-07" --budget 3000
```

### Environment Variables

```env
# Use Groq (FREE) - recommended
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key              # Free at console.groq.com

# Or use Google Gemini (FREE)
# LLM_PROVIDER=google
# GOOGLE_API_KEY=your_google_key        # Free at aistudio.google.com

# Or use OpenAI (paid)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_openai_key

# Optional: Observability
# LANGFUSE_PUBLIC_KEY=your_public_key
# LANGFUSE_SECRET_KEY=your_secret_key
```

### Run Evaluation

```bash
# Test all agent tools across 5 destinations (no LLM needed)
python3 -m evaluation.evaluator

# Results: 92.6/100 overall score, 55 tool calls, 5 destinations
```

### Agent Internals Visualizer

```bash
# Launch the multi-page Streamlit app with agent visualization
streamlit run app.py
# Navigate to "Agent Visualizer" in the sidebar
```

## Demo

### Sample Output

```
Planning a 5-day trip to Tokyo with $3,000 budget...

Flight Agent: Found round-trip LAX -> NRT for $650 (ANA, 1 stop)
Hotel Agent: Shinjuku Granbell Hotel - $120/night, 4.5 stars
Weather Agent: Expect 18-22C, light rain on Day 3
Activity Agent: Top picks - Tsukiji Market, Meiji Shrine, Akihabara
Budget Agent: $650 flights + $600 hotel + $750 food + $500 activities = $2,500 (under budget!)
Itinerary Agent: Compiled 5-day plan with indoor activities on rainy Day 3

Your complete itinerary is ready!
```

## Evaluation Results

All agent tools are evaluated across 5 destinations. The checks score for the presence of expected keywords in each tool's text output (e.g. prices, airlines, booking links) — they measure output shape, not real-world accuracy:

```
Overall Score: 92.6/100 | 55 tool calls | 5 destinations tested

Flight Agent:   100/100  (search_flights, compare_flight_prices)
Hotel Agent:    100/100  (search_hotels, compare_hotel_prices)
Activity Agent:  98/100  (search_activities, get_restaurant_recommendations)
Budget Agent:   100/100  (calculate_trip_budget, optimize_budget, get_currency_info)
Weather Agent:   65/100  (get_weather_forecast, get_best_travel_months)
                          ^ Lower score because the Open-Meteo HTTPS call failed on the test
                            machine; expected to pass when that HTTPS call succeeds
```

Run `python3 -m evaluation.evaluator` to reproduce. View detailed results at the [Internals & Eval page](https://sugeerth.github.io/agentic_data/visualizer.html).

## Tech Stack

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** - Multi-agent orchestration with state machines
- **[LangChain](https://langchain.com/)** - LLM tooling and agent framework
- **[Langfuse](https://langfuse.com/)** - Observability and tracing
- **[Streamlit](https://streamlit.io/)** - Interactive web UI
- **[Groq](https://groq.com/)** - Free LLM inference (default)
- **[Google Gemini](https://aistudio.google.com/)** - Free alternative LLM
- **[Open-Meteo](https://open-meteo.com/)** - Free weather API (no key needed)

## Project Structure

```
agentic_data/
├── app.py                  # Streamlit UI
├── main.py                 # CLI entry point
├── requirements.txt        # Dependencies
├── .env.example            # Environment template
├── agents/
│   ├── __init__.py
│   ├── supervisor.py       # Orchestrator agent
│   ├── flight_agent.py     # Flight search specialist
│   ├── hotel_agent.py      # Hotel search specialist
│   ├── activity_agent.py   # Activities & attractions
│   ├── weather_agent.py    # Weather forecasting
│   ├── budget_agent.py     # Budget optimization
│   └── itinerary_agent.py  # Final itinerary compiler
├── tools/
│   ├── __init__.py
│   ├── flight_tools.py     # Flight search tools
│   ├── hotel_tools.py      # Hotel search tools
│   ├── activity_tools.py   # Activity search tools
│   ├── weather_tools.py    # Weather API tools
│   └── budget_tools.py     # Budget calculation tools
├── graph/
│   ├── __init__.py
│   ├── state.py            # Shared state definition
│   └── workflow.py         # LangGraph workflow
├── config/
│   ├── settings.py         # Configuration
│   ├── llm_factory.py      # Multi-provider LLM factory (Groq/Google/OpenAI)
│   └── langfuse_config.py  # Observability integration
├── evaluation/
│   ├── evaluator.py        # Agent evaluation framework
│   └── eval_results.json   # Latest evaluation results
├── pages/
│   └── agent_visualizer.py # Streamlit agent internals page
├── docs/                   # GitHub Pages
│   ├── index.html          # Main showcase
│   └── visualizer.html     # Agent internals & eval visualization
└── tests/
    └── test_agents.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  By <strong>Sugeerth</strong>
  <br/>
  <a href="https://sugeerth.github.io/agentic_data/">View Live Demo</a>
</div>
