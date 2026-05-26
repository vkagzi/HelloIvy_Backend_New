"""
Unified Realtime WebSocket Consumer

A single WebSocket endpoint that handles voice sessions for ANY registered
feature.  The client connects to ``ws/voice/realtime/`` and passes two
query parameters:

    ?feature=<feature-id>&session_id=<uuid>

The consumer looks up the feature handler from the registry and delegates
all feature-specific work (access check, instructions, logging) to it.

This replaces the per-feature consumer subclasses
(DomainDiscoveryRealtimeConsumer, CareerDiscoveryRealtimeConsumer, …)
while reusing the proven Azure OpenAI plumbing from BaseRealtimeConsumer.
"""
import json
import logging
from typing import Optional, Dict, Any

from asgiref.sync import sync_to_async

from utils.realtime_consumer import BaseRealtimeConsumer
from utils.realtime_registry import get_feature_handler, BaseFeatureHandler

logger = logging.getLogger(__name__)


class UnifiedRealtimeConsumer(BaseRealtimeConsumer):
    """
    Delegates to the correct :class:`BaseFeatureHandler` based on the
    ``feature`` query-string parameter provided by the client.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_id: Optional[str] = None
        self.handler: Optional[BaseFeatureHandler] = None
        self._requested_voice: Optional[str] = None

    # ── helpers to parse query string ────────────────────────
    def _parse_query_params(self) -> Dict[str, str]:
        qs = self.scope.get('query_string', b'').decode()
        params: Dict[str, str] = {}
        for part in qs.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v
        return params

    # ── abstract method implementations ──────────────────────

    # Allowed OpenAI Realtime voice identifiers
    _ALLOWED_VOICES = {'cedar', 'marin'}

    async def get_session_id(self) -> Optional[str]:
        """
        Parse both ``session_id`` and ``feature`` from the query string.
        Resolves the feature handler so it's available for later calls.
        """
        params = self._parse_query_params()
        session_id = params.get('session_id')
        self.feature_id = params.get('feature')

        # Read optional voice preference from the client
        requested_voice = params.get('voice', '').lower()
        if requested_voice in self._ALLOWED_VOICES:
            self._requested_voice = requested_voice

        if not self.feature_id:
            logger.warning("No 'feature' query param provided")
            return None

        self.handler = get_feature_handler(self.feature_id)
        if not self.handler:
            logger.warning(f"Unknown feature identifier: {self.feature_id}")
            return None

        logger.info(f"🔀 Unified consumer resolved feature={self.feature_id}, session={session_id}, voice={self._requested_voice}")
        return session_id

    def get_voice(self) -> str:
        """Return the client-requested voice, falling back to the base default."""
        if self._requested_voice:
            return self._requested_voice
        return super().get_voice()

    @sync_to_async
    def verify_access(self) -> bool:
        if not self.handler or not self.session_id:
            return False
        return self.handler.verify_access(self.session_id, self.user)

    async def get_instructions(self) -> str:
        if not self.handler or not self.session_id:
            return "You are a helpful assistant."

        context = await sync_to_async(self.handler.get_session_context)(self.session_id, self.user)
        return self.handler.get_instructions(self.session_id, self.user, context)

    async def log_message(self, data: Dict[str, Any]) -> None:
        if not self.handler or not self.session_id:
            return
        result = await sync_to_async(self.handler.log_message)(self.session_id, self.user, data)
        if result:
            # If the handler signals that instructions should be refreshed
            # (e.g. session is concluding), push updated instructions to
            # OpenAI so the bot speaks the closing message.
            if result.pop('should_update_instructions', False):
                await self._refresh_openai_instructions()
            await self.safe_send(json.dumps(result))

    async def save_realtime_token_usage(self, usage: Dict[str, Any]) -> None:
        if not self.handler or not self.session_id:
            return
        await sync_to_async(self.handler.save_realtime_token_usage)(self.session_id, self.user, usage)

    async def _refresh_openai_instructions(self) -> None:
        """Re-fetch instructions from the handler and push a session.update
        to OpenAI so the bot picks up the closing STATUS (or any other
        instruction change) on its next response."""
        if not self.openai_ws or not self.handler:
            return
        try:
            instructions = await self.get_instructions()
            instructions += self.VOICE_STYLE_DIRECTIVE
            await self.openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "instructions": instructions,
                    "voice": self.get_voice(),
                },
            }))
            logger.info(f"🔄 Refreshed OpenAI instructions for feature={self.feature_id}, session={self.session_id}")
        except Exception as e:
            logger.error(f"❌ Error refreshing instructions: {e}", exc_info=True)

    async def configure_openai_session(self):
        """Delegate to the handler's custom session config when provided."""
        if not self.handler:
            return await super().configure_openai_session()

        instructions = await self.get_instructions()
        instructions += self.VOICE_STYLE_DIRECTIVE
        custom_config = self.handler.get_session_config(
            self.session_id, self.user, instructions
        )
        if custom_config is None:
            await super().configure_openai_session()
        else:
            # Send the handler-provided session config directly
            if self.openai_ws:
                logger.info(f"📤 Sending custom session config for feature={self.feature_id}")
                await self.openai_ws.send(json.dumps(custom_config))
                await self.safe_send(json.dumps({
                    "type": "connection.ready",
                    "message": "Connected to Azure OpenAI Realtime API"
                }))
            else:
                await self.send_error("OpenAI WebSocket connection not available")
                return

        # Register handler tools (if any) as a separate session.update so
        # they work regardless of whether the handler provides a custom
        # config or falls back to the base consumer's default.
        tools = self.handler.get_tools()
        if tools and self.openai_ws:
            await self.openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {"tools": tools},
            }))
            logger.info(
                f"🔧 Registered {len(tools)} tool(s) for feature={self.feature_id}"
            )

    async def _process_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Route an AI function call to the feature handler."""
        if not self.handler:
            return

        call_id = tool_call.get('call_id')
        name = tool_call.get('name', '')
        arguments_json = tool_call.get('arguments', '{}')

        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, TypeError):
            arguments = {}

        logger.info(
            f"🔧 Processing tool call '{name}' (call_id={call_id}) "
            f"for feature={self.feature_id}, session={self.session_id}"
        )

        result = await sync_to_async(self.handler.handle_tool_call)(
            name, arguments, self.session_id, self.user,
        )

        # Send any display content to the frontend
        if result and result.get('display_content'):
            await self.safe_send(json.dumps({
                'type': 'display.content',
                'content': result['display_content'],
                'content_type': result.get('content_type', 'markdown'),
            }))

        # Submit function output back to OpenAI and trigger continuation
        output_text = (result or {}).get('output', 'Done')
        if self.openai_ws:
            await self.openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output_text,
                },
            }))
            await self.openai_ws.send(json.dumps({"type": "response.create"}))
