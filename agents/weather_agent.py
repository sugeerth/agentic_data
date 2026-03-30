"""Weather forecasting specialist agent."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from tools.weather_tools import get_weather_forecast, get_best_travel_months
from config.settings import LLM_MODEL, LLM_TEMPERATURE


WEATHER_SYSTEM_PROMPT = """You are the Weather Agent for VoyageAI, a multi-agent travel planning system.

Your role is to provide weather intelligence for trip planning. You should:

1. Get the weather forecast for the travel dates
2. Identify days with bad weather for indoor activity planning
3. Recommend what to pack based on conditions
4. Suggest the best times of day for outdoor activities

Use the real Open-Meteo weather API to get accurate forecasts.
Provide practical advice, not just data."""


def create_weather_agent(llm: ChatOpenAI | None = None):
    """Create the weather agent."""
    if llm is None:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    tools = [get_weather_forecast, get_best_travel_months]

    prompt = ChatPromptTemplate.from_messages([
        ("system", WEATHER_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
