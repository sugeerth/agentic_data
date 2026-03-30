"""Configuration settings for VoyageAI."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Agent Configuration
MAX_AGENT_ITERATIONS = 5
SUPERVISOR_RECURSION_LIMIT = 25

# Demo mode (uses mock data instead of real APIs)
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
