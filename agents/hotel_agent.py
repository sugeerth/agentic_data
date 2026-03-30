"""Hotel search specialist agent."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from tools.hotel_tools import search_hotels, compare_hotel_prices
from config.llm_factory import create_llm


HOTEL_SYSTEM_PROMPT = """You are the Hotel Search Agent for VoyageAI, a multi-agent travel planning system.

Your role is to find the best accommodation options. You should:

1. Search for hotels matching the traveler's budget and style
2. Compare prices across booking platforms
3. Consider location relative to planned activities
4. Recommend options across different price ranges

Always present options for budget, mid-range, and luxury tiers when available.
Highlight key amenities and location advantages."""


def create_hotel_agent(llm: BaseChatModel | None = None):
    """Create the hotel search agent."""
    if llm is None:
        llm = create_llm()

    tools = [search_hotels, compare_hotel_prices]

    prompt = ChatPromptTemplate.from_messages([
        ("system", HOTEL_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
