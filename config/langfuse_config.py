"""Langfuse observability integration for VoyageAI."""

import os
from config.settings import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST


def get_langfuse_callback():
    """Get the Langfuse callback handler for LangChain if credentials are available.

    Returns None if Langfuse is not configured (optional dependency).
    """
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return None

    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        return handler
    except ImportError:
        print("Langfuse not installed. Run: pip install langfuse")
        return None
    except Exception as e:
        print(f"Langfuse setup error: {e}")
        return None


def trace_agent_run(agent_name: str, input_data: dict, output_data: str):
    """Log an agent run to Langfuse for observability.

    This is a convenience wrapper that works even if Langfuse is not configured.
    """
    handler = get_langfuse_callback()
    if handler is None:
        return

    try:
        from langfuse import Langfuse

        langfuse = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )

        trace = langfuse.trace(name=f"voyageai-{agent_name}")
        trace.span(
            name=f"{agent_name}-execution",
            input=input_data,
            output=output_data,
        )
    except Exception:
        pass  # Langfuse is optional
