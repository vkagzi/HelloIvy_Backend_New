import json
from typing import List, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


def log_system_prompt(logger, prompt: str, max_len: int = 2000) -> None:
    """Log the system prompt, truncating to `max_len` to avoid huge logs."""
    try:
        logger.debug("LLM system prompt: %s", prompt[:max_len])
    except Exception:
        logger.debug("LLM system prompt: <unserializable>")


def log_llm_messages(logger, messages: List[Any], max_content_len: int = 1000) -> None:
    """Sanitize and log a list of LLM messages (System/Human/AI).

    Truncates content and safely serializes to JSON for structured logs.
    """
    try:
        debug_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                role = 'system'
            elif isinstance(m, HumanMessage):
                role = 'user'
            elif isinstance(m, AIMessage):
                role = 'assistant'
            else:
                role = 'unknown'

            content = getattr(m, 'content', '') or ''
            debug_messages.append({'role': role, 'content': content[:max_content_len]})

        logger.debug("LLM messages: %s", json.dumps(debug_messages, ensure_ascii=False))
    except Exception:
        logger.debug("LLM messages: <unserializable or truncated>")
