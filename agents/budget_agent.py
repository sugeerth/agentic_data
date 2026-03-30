"""Budget optimization specialist agent."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from tools.budget_tools import calculate_trip_budget, optimize_budget, get_currency_info
from config.settings import LLM_MODEL, LLM_TEMPERATURE


BUDGET_SYSTEM_PROMPT = """You are the Budget Optimization Agent for VoyageAI, a multi-agent travel planning system.

Your role is to manage the trip budget intelligently. You should:

1. Calculate a detailed budget breakdown
2. Optimize allocation based on traveler priorities
3. Provide currency information and exchange tips
4. Identify money-saving opportunities
5. Ensure the trip stays within budget

Be practical and specific with your recommendations.
Always provide both per-day and total costs."""


def create_budget_agent(llm: ChatOpenAI | None = None):
    """Create the budget agent."""
    if llm is None:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    tools = [calculate_trip_budget, optimize_budget, get_currency_info]

    prompt = ChatPromptTemplate.from_messages([
        ("system", BUDGET_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=3)
