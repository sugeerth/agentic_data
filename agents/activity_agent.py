"""Activity and attractions specialist agent."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from tools.activity_tools import search_activities, get_restaurant_recommendations
from config.settings import LLM_MODEL, LLM_TEMPERATURE


ACTIVITY_SYSTEM_PROMPT = """You are the Activities & Attractions Agent for VoyageAI, a multi-agent travel planning system.

Your role is to find the best things to do at the destination. You should:

1. Search for top activities and attractions
2. Mix free and paid activities for budget optimization
3. Include food and dining recommendations
4. Consider the traveler's interests and preferences
5. Organize activities by area to minimize travel time

Prioritize authentic local experiences over tourist traps.
Always include a mix of culture, food, nature, and entertainment."""


def create_activity_agent(llm: ChatOpenAI | None = None):
    """Create the activity search agent."""
    if llm is None:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    tools = [search_activities, get_restaurant_recommendations]

    prompt = ChatPromptTemplate.from_messages([
        ("system", ACTIVITY_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
