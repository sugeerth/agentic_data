"""Configuration settings for VoyageAI."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider: "groq" (free), "openai", or "google" (free)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# Groq Configuration (FREE - get key at console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# OpenAI Configuration (paid)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Google Gemini Configuration (FREE - get key at aistudio.google.com)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

# Resolved LLM settings
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# Pick the active model name for display
if LLM_PROVIDER == "groq":
    LLM_MODEL = GROQ_MODEL
elif LLM_PROVIDER == "google":
    LLM_MODEL = GOOGLE_MODEL
else:
    LLM_MODEL = OPENAI_MODEL

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Agent Configuration
MAX_AGENT_ITERATIONS = 5
SUPERVISOR_RECURSION_LIMIT = 25

# Demo mode (uses mock data instead of real APIs)
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
