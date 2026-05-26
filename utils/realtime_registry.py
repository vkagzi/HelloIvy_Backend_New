"""
Realtime Voice Feature Registry

Maps feature identifiers (e.g. 'domain-discovery', 'career-discovery') to
handler classes that supply the feature-specific logic needed by the
UnifiedRealtimeConsumer.

Each handler implements:
    - verify_access(session_id, user) -> bool
    - get_instructions(session_id, user) -> str
    - get_session_context(session_id, user) -> dict | None
    - log_message(session_id, user, data) -> None
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Global registry ──────────────────────────────────────────
_FEATURE_HANDLERS: Dict[str, 'BaseFeatureHandler'] = {}


def register_feature(feature_id: str, handler: 'BaseFeatureHandler') -> None:
    """Register a feature handler for a given identifier."""
    _FEATURE_HANDLERS[feature_id] = handler
    logger.info(f"📋 Registered realtime feature handler: {feature_id}")


def get_feature_handler(feature_id: str) -> Optional['BaseFeatureHandler']:
    """Return the handler for *feature_id*, or ``None`` if not registered."""
    return _FEATURE_HANDLERS.get(feature_id)


def list_features() -> list[str]:
    """Return all registered feature identifiers."""
    return list(_FEATURE_HANDLERS.keys())


# ── Base handler ─────────────────────────────────────────────
class BaseFeatureHandler(ABC):
    """
    Abstract base that every feature must implement so the unified
    consumer can delegate feature-specific work.
    """

    @abstractmethod
    def verify_access(self, session_id: str, user) -> bool:
        """Return True if *user* may access *session_id*."""
        ...

    @abstractmethod
    def get_session_context(self, session_id: str, user) -> Optional[Dict[str, Any]]:
        """
        Build and return a dict of session context (session info, user
        profile, message history, etc.).  Return ``None`` when the
        session cannot be found.
        """
        ...

    @abstractmethod
    def get_instructions(self, session_id: str, user, context: Optional[Dict[str, Any]]) -> str:
        """
        Return the system instructions string for the AI, using the
        context returned by ``get_session_context``.
        """
        ...

    @abstractmethod
    def log_message(self, session_id: str, user, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Persist a transcript message to the database.

        Return an optional dict of session-progress data that should
        be forwarded to the frontend via the WebSocket (e.g. updated
        ``current_step``, ``total_steps``, ``is_completed``).  Return
        ``None`` when there is nothing to relay.
        """
        ...

    def save_realtime_token_usage(self, session_id: str, user, usage: Dict[str, Any]) -> None:
        """
        Persist accumulated realtime voice token usage to the session model.
        Override in subclasses to save to the appropriate model.
        """
        pass

    def get_session_config(self, session_id: str, user, instructions: str) -> Optional[Dict[str, Any]]:
        """
        Return a custom ``session.update`` payload for the Azure OpenAI
        Realtime API.  Return ``None`` to use the base consumer's default
        voice-conversation config.
        """
        return None

    def get_tools(self) -> list:
        """Return a list of function-calling tool definitions for the
        OpenAI Realtime session.  Return an empty list (default) if the
        feature does not use tool calls."""
        return []

    def handle_tool_call(
        self,
        name: str,
        arguments: Dict[str, Any],
        session_id: str,
        user,
    ) -> Optional[Dict[str, Any]]:
        """Process a function call made by the AI during a voice session.

        Return a dict with:
        - ``output`` (str): text sent back to OpenAI as function output.
        - ``display_content`` (str, optional): markdown/html to display
          in the frontend chat.
        - ``content_type`` (str, optional): ``'markdown'`` or ``'html'``.

        Return ``None`` if the tool name is not recognised.
        """
        return None
