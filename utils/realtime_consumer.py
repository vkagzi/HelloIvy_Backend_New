"""
Base Realtime WebSocket Consumer for OpenAI Realtime API
Pluggable base class that can be extended for different features

Supports two providers:

1. OpenAI Direct (preferred when OPENAI_API_KEY is set):
   - WebSocket URL: wss://api.openai.com/v1/realtime?model={model}
   - Authentication: Bearer token
   - Env: OPENAI_API_KEY, OPENAI_REALTIME_MODEL

2. Azure OpenAI (fallback):
   - WebSocket URL: wss://{endpoint}/openai/realtime?api-version={version}&deployment={deployment}
   - Authentication: api-key header
   - Env: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
          AZURE_OPENAI_REALTIME_DEPLOYMENT, AZURE_OPENAI_REALTIME_API_VERSION
"""
import json
import asyncio
import websockets
import logging
from abc import ABC, abstractmethod
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class BaseRealtimeConsumer(AsyncWebsocketConsumer, ABC):
    """
    Base WebSocket consumer for Azure OpenAI Realtime API
    
    This is a pluggable base class that handles:
    - WebSocket connection management
    - Azure OpenAI Realtime API integration
    - Audio streaming
    - Transcript management
    
    Subclasses must implement:
    - get_session_id(): Extract session ID from request
    - verify_access(): Verify user has access to the session
    - get_instructions(): Build AI instructions for the session
    - log_message(data): Log messages to database (optional)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.openai_ws = None
        self.session_id = None
        self.user = None
        self._client_connected = False
        self._listener_task = None
        
        # Accumulated realtime token usage across all responses
        self._realtime_token_usage = {
            'total_tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'input_text_tokens': 0,
            'input_audio_tokens': 0,
            'output_text_tokens': 0,
            'output_audio_tokens': 0,
            'input_cached_tokens': 0,
            'response_count': 0,
        }
        
        # Skip logging counter: when > 0, the next N assistant responses
        # are not persisted to the database (used for system prompts like
        # intro announcements and mode-switch acknowledgements).
        self._skip_logging_count = 0
        
        # OpenAI direct configuration (takes precedence over Azure)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_realtime_model = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-1.5')
        
        # Azure OpenAI configuration (fallback)
        self.azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.realtime_deployment = os.getenv('AZURE_OPENAI_REALTIME_DEPLOYMENT', 'gpt-realtime-1.5')
        self.realtime_api_version = os.getenv('AZURE_OPENAI_REALTIME_API_VERSION', '2024-10-01-preview')
        
        # Determine provider
        self._use_openai_direct = bool(self.openai_api_key)
        
        # Selected accent preference
        self.accent = None
        
        # Selected language preference (e.g. 'en', 'hi')
        self.language = 'en'
        
        # Silent reconnection tracking
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 2
    
    async def connect(self):
        """Accept WebSocket connection from client"""
        try:
            # Extract session ID and user from request
            self.session_id = await self.get_session_id()
            self.user = self.scope.get('user')
            
            if not self.session_id:
                logger.warning("No session ID provided")
                await self.accept()
                await self.send_error("No session ID provided")
                return
            
            # Verify user has access to this session
            has_access = await self.verify_access()
            if not has_access:
                logger.warning(f"User does not have access to session {self.session_id}")
                await self.accept()
                await self.send_error("Access denied: Invalid session")
                return
            
            await self.accept()
            self._client_connected = True
            logger.info(f"✅ Client connected to realtime session {self.session_id}")
            
            # Initialize OpenAI connection
            try:
                await self.connect_to_openai()
            except Exception as e:
                logger.error(f"Error during OpenAI connection: {e}", exc_info=True)
                await self.send_error(f"Failed to initialize voice connection: {str(e)}")
                # Don't close the connection - allow retry
                
        except Exception as e:
            logger.error(f"Error in connect: {e}", exc_info=True)
            try:
                await self.accept()
                await self.send_error(f"Connection error: {str(e)}")
            except:
                pass  # Connection may already be closed
    
    async def disconnect(self, close_code):
        """Clean up when client disconnects"""
        self._client_connected = False
        
        openai_state = 'None'
        if self.openai_ws:
            try:
                openai_state = f'open={self.openai_ws.open}, close_code={self.openai_ws.close_code}, close_reason={self.openai_ws.close_reason}'
            except Exception:
                openai_state = 'error reading state'
        
        logger.info(
            f"🔌 Client disconnect START for session {self.session_id} | "
            f"close_code={close_code} | "
            f"openai_ws={openai_state} | "
            f"tokens={self._realtime_token_usage['total_tokens']} responses={self._realtime_token_usage['response_count']} | "
            f"listener_task_done={self._listener_task.done() if self._listener_task else 'None'}"
        )
        
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self.openai_ws:
            await self.openai_ws.close()
        
        # Persist accumulated token usage to the database
        if self._realtime_token_usage['response_count'] > 0:
            try:
                await self.save_realtime_token_usage(self._realtime_token_usage)
                logger.info(f"💾 Saved realtime token usage for session {self.session_id}: {self._realtime_token_usage['total_tokens']} total tokens across {self._realtime_token_usage['response_count']} responses")
            except Exception as e:
                logger.error(f"❌ Failed to save realtime token usage for session {self.session_id}: {e}", exc_info=True)
        
        logger.info(f"✅ Client disconnect COMPLETE for session {self.session_id} with code: {close_code}")
    
    async def safe_send(self, text_data: str) -> bool:
        """Safely send data to client, handling disconnection gracefully"""
        if not self._client_connected:
            return False
        try:
            await self.send(text_data=text_data)
            return True
        except Exception as e:
            # Client already disconnected, just log and ignore
            self._client_connected = False
            logger.debug(f"Could not send to client (likely disconnected): {e}")
            return False
    
    async def receive(self, text_data):
        """Receive message from client and forward to OpenAI"""
        try:
            data = json.loads(text_data)
            
            # Respond to client-side keepalive pings
            if data.get('type') == 'ping':
                await self.safe_send(json.dumps({'type': 'pong'}))
                return
            
            # Skip-logging signal from frontend (not forwarded to OpenAI)
            if data.get('type') == 'session.skip_logging':
                count = data.get('count', 1)
                self._skip_logging_count += count
                logger.info(f"⏭️ Skip logging requested for next {count} assistant response(s) (total pending: {self._skip_logging_count})")
                return
            
            # Allow subclasses to log conversation events
            if data.get('type') in ['conversation.item.created', 'input_audio_buffer.commit']:
                await self.log_message(data)
            
            if self.openai_ws:
                await self.openai_ws.send(text_data)
            else:
                # Upstream connection lost — try silent reconnection
                reconnected = await self._reconnect_to_openai()
                if reconnected:
                    try:
                        await self.openai_ws.send(text_data)
                    except Exception:
                        await self.send_error("Voice connection lost. Please reconnect.")
                else:
                    await self.send_error("Voice connection lost. Please reconnect.")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON received")
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(
                f"🔌 OpenAI WS closed while forwarding for session {self.session_id} | "
                f"code={e.code} reason='{e.reason}'"
            )
            self.openai_ws = None
            await self.send_error("Voice connection lost. Please reconnect.")
        except Exception as e:
            logger.error(f"Error forwarding message to OpenAI: {e}")
            await self.send_error(f"Error: {str(e)}")
    
    async def connect_to_openai(self):
        """Establish WebSocket connection to OpenAI or Azure OpenAI Realtime API"""
        if self._use_openai_direct:
            await self._connect_openai_direct()
        else:
            await self._connect_azure_openai()
    
    async def _connect_openai_direct(self):
        """Connect to OpenAI's native Realtime API (wss://api.openai.com)"""
        try:
            openai_url = f"wss://api.openai.com/v1/realtime?model={self.openai_realtime_model}"
            
            logger.info(f"Attempting to connect to OpenAI Realtime at: {openai_url}")
            logger.info(f"Using model: {self.openai_realtime_model}")
            
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            }
            
            self.openai_ws = await websockets.connect(
                openai_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=10,
            )
            
            logger.info(f"✅ WebSocket connection established for session {self.session_id}")
            
            self._listener_task = asyncio.create_task(self.listen_to_openai())
            await self.configure_openai_session()
            
            logger.info(f"✅ Successfully connected to OpenAI Realtime API for session {self.session_id}")
            
        except websockets.exceptions.InvalidStatusCode as e:
            error_msg = f"Invalid status code from OpenAI: {e.status_code}"
            logger.error(f"{error_msg} - {e}")
            await self.send_error(f"Failed to connect to OpenAI: {error_msg}")
        except websockets.exceptions.WebSocketException as e:
            error_msg = f"WebSocket error: {str(e)}"
            logger.error(f"{error_msg}")
            await self.send_error(f"Failed to connect to OpenAI: {error_msg}")
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Failed to connect to OpenAI: {error_msg}", exc_info=True)
            await self.send_error(f"Failed to connect to OpenAI: {error_msg}")
    
    async def _connect_azure_openai(self):
        """Connect to Azure OpenAI Realtime API"""
        if not self.azure_endpoint or not self.azure_api_key:
            error_msg = "Azure OpenAI credentials not configured"
            logger.error(f"{error_msg}. Endpoint: {self.azure_endpoint}, API Key: {'***' if self.azure_api_key else 'None'}")
            await self.send_error(error_msg)
            return
        
        try:
            base_url = self.azure_endpoint.replace('https://', 'wss://').replace('http://', 'ws://')
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            
            openai_url = f"{base_url}/openai/realtime?api-version={self.realtime_api_version}&deployment={self.realtime_deployment}"
            
            logger.info(f"Attempting to connect to Azure OpenAI at: {openai_url}")
            logger.info(f"Using deployment: {self.realtime_deployment}")
            
            headers = {
                "api-key": self.azure_api_key,
            }
            
            self.openai_ws = await websockets.connect(
                openai_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=10,
            )
            
            logger.info(f"✅ WebSocket connection established for session {self.session_id}")
            
            self._listener_task = asyncio.create_task(self.listen_to_openai())
            await self.configure_openai_session()
            
            logger.info(f"✅ Successfully connected to Azure OpenAI Realtime API for session {self.session_id}")
            
        except websockets.exceptions.InvalidStatusCode as e:
            error_msg = f"Invalid status code from Azure OpenAI: {e.status_code}"
            logger.error(f"{error_msg} - {e}")
            await self.send_error(f"Failed to connect to Azure OpenAI: {error_msg}")
        except websockets.exceptions.WebSocketException as e:
            error_msg = f"WebSocket error: {str(e)}"
            logger.error(f"{error_msg}")
            await self.send_error(f"Failed to connect to Azure OpenAI: {error_msg}")
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Failed to connect to Azure OpenAI: {error_msg}", exc_info=True)
            await self.send_error(f"Failed to connect to Azure OpenAI: {error_msg}")
    
    # Voice style directive appended to all session instructions so the AI
    # maintains a consistent speaking style across reconnections and mode switches.
    VOICE_STYLE_DIRECTIVE = (
        "\n\n[Voice Style Consistency: Throughout this ENTIRE conversation — from the very first "
        "greeting through to the final goodbye — maintain a consistent voice style. Keep the same "
        "tone, pacing, energy level, warmth, and expressiveness at all times. This applies to every "
        "phase of the conversation including: the opening intro, asking questions, acknowledging "
        "responses, transitioning between topics, delivering the closing/conclusion message, "
        "resuming after a pause, and switching between text and voice modes. Do not change your "
        "speaking style when responding to system instructions, mode switches, pauses, or after "
        "any interruptions. Your voice should sound like the same person from start to finish, "
        "as if the conversation never paused or changed context.]"
    )

    def get_voice_style_directive(self) -> str:
        """Return the voice style directive, tailored for language settings."""
        if getattr(self, 'language', 'en') == 'hi':
            return (
                "\n\n[Voice Style Consistency: Throughout the remainder of this conversation, you MUST speak in Hindi. "
                "Ignore any previous instructions to speak or maintain voice style in English. You must transition "
                "to speaking in warm, natural, and friendly Hindi immediately. "
                "Ensure your text transcript output is always in Hindi (Devanagari script). "
                "Maintain a consistent tone, pacing, energy level, and warmth at all times in Hindi.]"
            )
        return self.VOICE_STYLE_DIRECTIVE

    def get_accent_directive(self) -> str:
        """Return the appropriate system instruction directive for the requested accent/language."""
        if getattr(self, 'language', 'en') == 'hi':
            voice = self.get_voice()
            gender_directive = (
                "You are a female Hindi-speaking counselor. You MUST speak and write using feminine grammatical forms in Hindi "
                "(e.g., use 'करूँगी' instead of 'करूँगा', and 'मार्गदर्शिका' instead of 'मार्गदर्शक')."
            ) if voice == 'marin' else (
                "You are a male Hindi-speaking counselor. You MUST speak and write using masculine grammatical forms in Hindi "
                "(e.g., use 'करूँगा' instead of 'करूँगी', and 'मार्गदर्शक' instead of 'मार्गदर्शिका')."
            )
            return (
                f"\n\n[Language and Transcript Directive: {gender_directive} You MUST converse with the student in Hindi. "
                "Speak in clear, natural, and warm Hindi. Both your spoken audio and your text transcript MUST be in Hindi (using Devanagari script). "
                "The student will also speak and type in Hindi. Your responses, transcriptions, and all messages in the chatbox must be written strictly in Hindi (Devanagari script) - do not use English translation or Hinglish.]"
            )
        accent = getattr(self, 'accent', None)
        if accent == 'indian':
            return (
                "\n\n[Accent Directive: You are an Indian counselor. You MUST speak with a distinct, prominent, and authentic Indian English accent. "
                "Do NOT sound American or British. Differentiate your speech using the following Indian English phonetic patterns:\n"
                "1. Rhythm: Use a syllable-timed rhythm (where each syllable has equal duration), which is characteristic of Indian English, rather than stress-timed rhythm.\n"
                "2. Vowels: Pronounce vowels like in 'late' or 'goat' as pure monophthongs (pure 'ay' and 'oh' sounds) rather than diphthongs.\n"
                "3. Consonants: Pronounce 't' and 'd' sounds with a slight retroflex (tongue curled back slightly towards the roof of the mouth, as in Indian languages), and ensure 'th' sounds (like in 'this' or 'think') are pronounced as clear plosives (closer to 'd' or 't').\n"
                "4. Intonation: Adopt a warm, friendly, and authentic Indian regional intonation, cadence, and cadence patterns.\n"
                "Make sure your accent is clearly and distinctly Indian from your very first word to your last.]"
            )
        elif accent == 'british':
            return (
                "\n\n[Accent Directive: You are a British counselor. You MUST speak with a clear, polished, and distinct British English accent (Received Pronunciation). "
                "Maintain British pronunciation, speech rhythms, intonation, and phrasing throughout the entire conversation.]"
            )
        elif accent == 'american':
            return (
                "\n\n[Accent Directive: You are an American counselor. You MUST speak with a clear, natural, and distinct standard American English accent. "
                "Maintain standard American pronunciation and intonation throughout the entire conversation.]"
            )
        return ""

    async def configure_openai_session(self):
        """Send initial session configuration to OpenAI with custom instructions"""
        try:
            logger.info(f"⚙️ Configuring session for {self.session_id} (accent: {getattr(self, 'accent', 'None')})")
            instructions = self.get_accent_directive() + "\n\n" + await self.get_instructions()
            instructions += self.get_voice_style_directive()
            logger.info(f"📝 Got instructions (length: {len(instructions)} chars)")
            
            from django.conf import settings
            transcription_model = "gpt-4o-transcribe"
            if not self._use_openai_direct:
                transcription_model = getattr(settings, 'AZURE_OPENAI_WHISPER_DEPLOYMENT', 'whisper')

            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],  # Enable both text and audio
                    "voice": self.get_voice(),
                    "instructions": instructions,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": transcription_model,
                        "language": getattr(self, 'language', 'en'),
                    },
                    "input_audio_noise_reduction": self.get_noise_reduction_config(),
                    "turn_detection": self.get_turn_detection_config(),
                    # "temperature": self.get_temperature(),
                    # "max_response_output_tokens": self.get_max_tokens()
                }
            }
            
            if self.openai_ws:
                provider = "OpenAI" if self._use_openai_direct else "Azure OpenAI"
                model_info = self.openai_realtime_model if self._use_openai_direct else self.realtime_deployment
                logger.info(f"📤 Sending session configuration for {provider} model: {model_info}")
                await self.openai_ws.send(json.dumps(session_config))
                logger.info(f"✅ Session configuration sent for session {self.session_id}")
                
                # Send a connection success message to client
                await self.safe_send(json.dumps({
                    "type": "connection.ready",
                    "message": f"Connected to {provider} Realtime API"
                }))
            else:
                logger.error(f"❌ OpenAI WebSocket is closed or None for session {self.session_id}")
                await self.safe_send(json.dumps({
                    "type": "error",
                    "error": {"message": "OpenAI WebSocket connection not available", "type": "connection_error"}
                }))
                
        except Exception as e:
            logger.error(f"❌ Error configuring session: {e}", exc_info=True)
            await self.safe_send(json.dumps({
                "type": "error",
                "error": {"message": f"Failed to configure session: {str(e)}", "type": "connection_error"}
            }))
    
    async def listen_to_openai(self):
        """Listen for responses from OpenAI and forward to client"""
        try:
            provider = "OpenAI" if self._use_openai_direct else "Azure OpenAI"
            logger.info(f"🎧 Started listening to {provider} for session {self.session_id}")
            async for message in self.openai_ws:
                # Forward all messages to client (ignore if client disconnected)
                sent = await self.safe_send(message)
                
                # Parse and handle specific events
                if sent:
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type')
                        
                        # Log significant events
                        if msg_type in ['response.done', 'conversation.item.created', 'session.updated', 'session.created',
                                        'conversation.item.input_audio_transcription.completed', 'response.audio_transcript.done']:
                            logger.info(f"📨 OpenAI event: {msg_type} for session {self.session_id}")
                        
                        # Allow subclasses to handle message logging
                        # Capture user transcripts from audio transcription
                        if msg_type == 'conversation.item.input_audio_transcription.completed':
                            await self.log_message(data)
                        # Capture assistant transcripts from audio responses
                        elif msg_type == 'response.audio_transcript.done':
                            if self._skip_logging_count > 0:
                                self._skip_logging_count -= 1
                                logger.info(f"⏭️ Skipped logging assistant response for session {self.session_id} (remaining skips: {self._skip_logging_count})")
                            else:
                                await self.log_message(data)
                        # Accumulate token usage from completed responses
                        elif msg_type == 'response.done':
                            response_data = data.get('response', {})
                            usage = response_data.get('usage')
                            if usage and response_data.get('status') != 'cancelled':
                                self._accumulate_token_usage(usage)
                            # Process function calls in the response output
                            for output_item in response_data.get('output', []):
                                if output_item.get('type') == 'function_call':
                                    await self._process_tool_call(output_item)
                        
                    except json.JSONDecodeError:
                        pass  # Non-JSON message, just forward
                
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(
                f"🔌 {provider} upstream WS closed for session {self.session_id} | "
                f"code={e.code} reason='{e.reason}' | "
                f"client_connected={self._client_connected} | "
                f"tokens={self._realtime_token_usage['total_tokens']} responses={self._realtime_token_usage['response_count']}"
            )
        except Exception as e:
            logger.error(f"❌ Error listening to {provider} for session {self.session_id}: {e}", exc_info=True)
        finally:
            # Mark the upstream connection as dead so receive() won't
            # attempt to write to a closed socket.
            self.openai_ws = None
            logger.info(f"🔌 {provider} upstream listener ended for session {self.session_id} | client_still_connected={self._client_connected}")
            # Try silent reconnection before notifying the client
            if self._client_connected:
                reconnected = await self._reconnect_to_openai()
                if not reconnected:
                    await self.send_error("Voice connection lost. Please reconnect.")
    
    async def _reconnect_to_openai(self) -> bool:
        """Attempt to silently re-establish the upstream OpenAI connection.
        Returns True if reconnection succeeded."""
        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_reconnect_attempts:
            logger.warning(f"❌ Max OpenAI reconnect attempts reached for session {self.session_id}")
            self._reconnect_attempts = 0
            return False
        
        try:
            logger.info(f"🔄 Attempting OpenAI reconnect ({self._reconnect_attempts}/{self._max_reconnect_attempts}) for session {self.session_id}")
            await self.connect_to_openai()
            
            if self.openai_ws:
                self._reconnect_attempts = 0
                logger.info(f"✅ Successfully reconnected to OpenAI for session {self.session_id}")
                return True
        except Exception as e:
            logger.error(f"❌ OpenAI reconnect attempt failed for session {self.session_id}: {e}", exc_info=True)
        
        self._reconnect_attempts = 0
        return False
    
    async def send_error(self, error_message: str):
        """Send error message to client (safely handles disconnection)"""
        error_data = {
            "type": "error",
            "error": {
                "message": error_message,
                "type": "connection_error"
            }
        }
        await self.safe_send(json.dumps(error_data))
    
    # ===== Abstract methods to be implemented by subclasses =====
    
    @abstractmethod
    async def get_session_id(self) -> Optional[str]:
        """
        Extract session ID from the WebSocket request.
        
        Returns:
            Session ID string or None if not found
        """
        pass
    
    @abstractmethod
    async def verify_access(self) -> bool:
        """
        Verify that the current user has access to this session.
        
        Returns:
            True if access is granted, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_instructions(self) -> str:
        """
        Build custom instructions for the AI based on session context.
        
        Returns:
            Instruction string for the AI
        """
        pass
    
    async def log_message(self, data: Dict[str, Any]) -> None:
        """
        Log conversation messages to database (optional).
        
        Args:
            data: Message data from OpenAI Realtime API
        """
        # Default: no logging
        # Subclasses can override to implement logging
        pass
    
    async def save_realtime_token_usage(self, usage: Dict[str, Any]) -> None:
        """
        Persist accumulated realtime token usage to the database (optional).
        Called on disconnect if any tokens were used.
        
        Args:
            usage: Accumulated token usage dict
        """
        # Default: no persistence
        # Subclasses can override to implement saving
        pass

    async def _process_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Handle a function call emitted by OpenAI in ``response.done``.

        Subclasses (e.g. the unified consumer) override this to delegate
        to the feature handler, send the function output back to OpenAI,
        and relay any display content to the frontend.
        """
        pass
    
    # ===== Token usage helpers =====
    
    def _accumulate_token_usage(self, usage: Dict[str, Any]) -> None:
        """Accumulate token counts from a response.done usage object."""
        input_details = usage.get('input_token_details', {}) or {}
        output_details = usage.get('output_token_details', {}) or {}
        
        self._realtime_token_usage['total_tokens'] += usage.get('total_tokens', 0)
        self._realtime_token_usage['input_tokens'] += usage.get('input_tokens', 0)
        self._realtime_token_usage['output_tokens'] += usage.get('output_tokens', 0)
        self._realtime_token_usage['input_text_tokens'] += input_details.get('text_tokens', 0)
        self._realtime_token_usage['input_audio_tokens'] += input_details.get('audio_tokens', 0)
        self._realtime_token_usage['input_cached_tokens'] += input_details.get('cached_tokens', 0)
        self._realtime_token_usage['output_text_tokens'] += output_details.get('text_tokens', 0)
        self._realtime_token_usage['output_audio_tokens'] += output_details.get('audio_tokens', 0)
        self._realtime_token_usage['response_count'] += 1
        
        logger.info(f"📊 Realtime tokens accumulated (response #{self._realtime_token_usage['response_count']}): "
                     f"total={self._realtime_token_usage['total_tokens']}, "
                     f"audio_in={self._realtime_token_usage['input_audio_tokens']}, "
                     f"audio_out={self._realtime_token_usage['output_audio_tokens']}")
    
    # ===== Configuration methods (can be overridden by subclasses) =====
    
    def get_voice(self) -> str:
        """Get the voice to use for TTS. Override to customize."""
        return "cedar"
    
    def get_noise_reduction_config(self) -> Optional[Dict[str, str]]:
        """Get noise reduction configuration. Override to customize.
        
        Returns:
            {"type": "near_field"} for close-talking microphones (headphones),
            {"type": "far_field"} for laptop or conference room microphones,
            or None to disable noise reduction.
        """
        return {"type": "near_field"}
    
    def get_turn_detection_config(self) -> Dict[str, Any]:
        """Get turn detection configuration. Override to customize.
        
        silence_duration_ms: How long the user must be silent before the
        server commits the audio buffer and triggers a response.  A higher
        value (800-1200ms) prevents the bot from jumping in when the user
        merely pauses between sentences.
        """
        return {
            # "type": "semantic_vad",
            # "eagerness": "low"
            "type": "server_vad",
            "threshold": 0.6,
            "prefix_padding_ms": 400,
            "silence_duration_ms": 1500
        }
    
    def get_temperature(self) -> float:
        """Get temperature setting. Override to customize."""
        return 0.8
    
    def get_max_tokens(self) -> int:
        """Get max response tokens. Override to customize."""
        return 4096
