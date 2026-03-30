"""Flight search specialist agent."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from tools.flight_tools import search_flights, compare_flight_prices
from config.llm_factory import create_llm


FLIGHT_SYSTEM_PROMPT = """You are the Flight Search Agent for VoyageAI, a multi-agent travel planning system.

Your role is to find the best flight options for the traveler. You should:

1. Search for flights between the origin and destination
2. Compare prices across platforms
3. Recommend the best options considering price, duration, and number of stops
4. Provide direct booking links

Always present at least 3 options: best price, best duration, and best overall value.
Be concise and data-driven in your recommendations."""


def create_flight_agent(llm: BaseChatModel | None = None):
    """Create the flight search agent."""
    if llm is None:
        llm = create_llm()

    tools = [search_flights, compare_flight_prices]

    prompt = ChatPromptTemplate.from_messages([
        ("system", FLIGHT_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
