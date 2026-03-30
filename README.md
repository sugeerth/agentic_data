# VoyageAI - Multi-Agent Travel Planning System

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge)](https://sugeerth.github.io/agentic_data/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Powered-orange?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<div align="center">
  <img src="docs/assets/banner.png" alt="VoyageAI Banner" width="800"/>

  **An intelligent multi-agent travel planning system powered by LangGraph, LangChain, and Langfuse**

  *Plan your perfect trip with AI agents that specialize in flights, hotels, activities, weather, budgets, and itinerary creation.*
</div>

---

## Architecture

VoyageAI uses a **supervisor-worker** multi-agent architecture where specialized agents collaborate to create comprehensive travel plans:

```
                    +-------------------+
                    |   Supervisor      |
                    |   (Orchestrator)  |
                    +--------+----------+
                             |
          +------------------+------------------+
          |         |        |        |         |
     +----v---+ +--v---+ +--v--+ +---v---+ +---v----+
     | Flight | | Hotel| |Activ| |Weather| | Budget |
     | Agent  | | Agent| |Agent| | Agent | | Agent  |
     +--------+ +------+ +-----+ +-------+ +--------+
          |         |        |        |         |
          +------------------+------------------+
                             |
                    +--------v----------+
                    |  Itinerary Agent  |
                    |  (Final Planner)  |
                    +-------------------+
```

### Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Supervisor** | Orchestrates all agents, manages state, decides execution order | Agent routing, state management |
| **Flight Agent** | Searches for optimal flights based on dates, budget, preferences | Flight search APIs, price comparison |
| **Hotel Agent** | Finds accommodations matching style, location, and budget | Hotel search, review analysis |
| **Activity Agent** | Discovers local attractions, restaurants, and experiences | Places API, review aggregation |
| **Weather Agent** | Provides weather forecasts to optimize daily planning | Weather APIs, seasonal analysis |
| **Budget Agent** | Tracks spending, optimizes allocation, finds deals | Budget optimization, currency conversion |
| **Itinerary Agent** | Compiles all recommendations into a cohesive day-by-day plan | Schedule optimization, conflict resolution |

## Features

- **Multi-Agent Orchestration** - LangGraph-powered supervisor pattern with conditional routing
- **Specialized AI Agents** - Each agent is an expert in its domain with dedicated tools
- **Real-time Observability** - Langfuse integration for tracing agent interactions
- **Beautiful Streamlit UI** - Interactive chat interface with live agent status
- **Budget Optimization** - Smart allocation across flights, hotels, and activities
- **Weather-Aware Planning** - Daily activities adapt to weather forecasts
- **Conflict Resolution** - Agents negotiate to resolve scheduling conflicts
- **Export Ready** - Download your itinerary as PDF or share via link

## Quick Start

### Prerequisites

- Python 3.10+
- An OpenAI API key (or any LangChain-compatible LLM)

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
OPENAI_API_KEY=your_openai_key          # Required: LLM provider
LANGFUSE_PUBLIC_KEY=your_public_key     # Optional: Observability
LANGFUSE_SECRET_KEY=your_secret_key     # Optional: Observability
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Demo

<div align="center">
  <img src="docs/assets/demo.gif" alt="VoyageAI Demo" width="700"/>
</div>

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

## Tech Stack

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** - Multi-agent orchestration with state machines
- **[LangChain](https://langchain.com/)** - LLM tooling and agent framework
- **[Langfuse](https://langfuse.com/)** - Observability and tracing
- **[Streamlit](https://streamlit.io/)** - Interactive web UI
- **[OpenAI GPT-4](https://openai.com/)** - Language model backbone (swappable)

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
│   └── settings.py         # Configuration
├── docs/                   # GitHub Pages
│   ├── index.html
│   └── assets/
└── tests/
    └── test_agents.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Built with AI by <strong>Sugeerth</strong>
  <br/>
  <a href="https://sugeerth.github.io/agentic_data/">View Live Demo</a>
</div>
