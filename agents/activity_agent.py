"""Activity and attractions specialist agent."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from tools.activity_tools import search_activities, get_restaurant_recommendations
from config.llm_factory import create_llm


ACTIVITY_SYSTEM_PROMPT = """You are the Activities & Attractions Agent for VoyageAI, a multi-agent travel planning system.

Your role is to find the best things to do at the destination. You should:

1. Search for top activities and attractions
2. Mix free and paid activities for budget optimization
3. Include food and dining recommendations
4. Consider the traveler's interests and preferences
5. Organize activities by area to minimize travel time

Prioritize authentic local experiences over tourist traps.
Always include a mix of culture, food, nature, and entertainment."""


def create_activity_agent(llm: BaseChatModel | None = None):
    """Create the activity search agent."""
    if llm is None:
        llm = create_llm()

    tools = [search_activities, get_restaurant_recommendations]

    prompt = ChatPromptTemplate.from_messages([
        ("system", ACTIVITY_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
