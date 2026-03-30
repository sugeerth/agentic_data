"""Flight search specialist agent."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from tools.flight_tools import search_flights, compare_flight_prices
from config.settings import LLM_MODEL, LLM_TEMPERATURE


FLIGHT_SYSTEM_PROMPT = """You are the Flight Search Agent for VoyageAI, a multi-agent travel planning system.

Your role is to find the best flight options for the traveler. You should:

1. Search for flights between the origin and destination
2. Compare prices across platforms
3. Recommend the best options considering price, duration, and number of stops
4. Provide direct booking links

Always present at least 3 options: best price, best duration, and best overall value.
Be concise and data-driven in your recommendations."""


def create_flight_agent(llm: ChatOpenAI | None = None):
    """Create the flight search agent."""
    if llm is None:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    tools = [search_flights, compare_flight_prices]

    prompt = ChatPromptTemplate.from_messages([
        ("system", FLIGHT_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
