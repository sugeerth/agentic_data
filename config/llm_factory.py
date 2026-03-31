"""LLM Factory - supports multiple free and paid LLM providers.

Supported providers (all free tiers available):
- Groq: Free tier, blazing fast, llama-3.3-70b-versatile (recommended)
- Google Gemini: Free tier, gemini-2.0-flash
- OpenAI: Paid, gpt-4o-mini
"""

from langchain_core.language_models.chat_models import BaseChatModel
from config.settings import (
    LLM_PROVIDER, LLM_TEMPERATURE,
    GROQ_API_KEY, GROQ_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    GOOGLE_API_KEY, GOOGLE_MODEL,
)


def create_llm(provider: str | None = None, temperature: float | None = None) -> BaseChatModel:
    """Create an LLM instance from the configured (or specified) provider.

    Args:
        provider: Override the default provider ("groq", "openai", "google")
        temperature: Override the default temperature

    Returns:
        A LangChain chat model instance
    """
    provider = (provider or LLM_PROVIDER).lower()
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    if provider == "groq":
        return _create_groq_llm(temp)
    elif provider == "google":
        return _create_google_llm(temp)
    elif provider == "openai":
        return _create_openai_llm(temp)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: groq (free), google (free), openai (paid)"
        )


def _create_groq_llm(temperature: float) -> BaseChatModel:
    """Create a Groq LLM (FREE - https://console.groq.com)."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com\n"
            "Then: export GROQ_API_KEY=your_key_here"
        )
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=temperature,
        api_key=GROQ_API_KEY,
        max_retries=2,
        timeout=30,
    )


def _create_google_llm(temperature: float) -> BaseChatModel:
    """Create a Google Gemini LLM (FREE - https://aistudio.google.com)."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY not set. Get a free key at https://aistudio.google.com\n"
            "Then: export GOOGLE_API_KEY=your_key_here"
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GOOGLE_MODEL,
        temperature=temperature,
        google_api_key=GOOGLE_API_KEY,
        max_retries=2,
        timeout=30,
    )


def _create_openai_llm(temperature: float) -> BaseChatModel:
    """Create an OpenAI LLM (paid)."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY not set. Get a key at https://platform.openai.com\n"
            "Or use a free provider: export LLM_PROVIDER=groq"
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=temperature,
    )


def get_provider_info() -> dict:
    """Get information about the current LLM provider configuration."""
    provider = LLM_PROVIDER.lower()
    info = {
        "provider": provider,
        "model": "",
        "cost": "",
        "status": "not_configured",
        "setup_url": "",
    }

    if provider == "groq":
        info["model"] = GROQ_MODEL
        info["cost"] = "FREE (rate limited)"
        info["setup_url"] = "https://console.groq.com"
        info["status"] = "configured" if GROQ_API_KEY else "needs_api_key"
    elif provider == "google":
        info["model"] = GOOGLE_MODEL
        info["cost"] = "FREE (rate limited)"
        info["setup_url"] = "https://aistudio.google.com"
        info["status"] = "configured" if GOOGLE_API_KEY else "needs_api_key"
    elif provider == "openai":
        info["model"] = OPENAI_MODEL
        info["cost"] = "Paid (~$0.15/1M input tokens)"
        info["setup_url"] = "https://platform.openai.com"
        info["status"] = "configured" if OPENAI_API_KEY else "needs_api_key"

    return info
