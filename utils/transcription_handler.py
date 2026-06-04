"""
Transcription-Only – Realtime voice feature handler

Registered under ``transcription-only`` so the unified WebSocket consumer
can provide a lightweight, transcription-focused session that does NOT
generate AI responses – it only converts user speech to text.
"""
import logging
from typing import Dict, Any, Optional

from utils.realtime_registry import BaseFeatureHandler, register_feature

logger = logging.getLogger(__name__)


class TranscriptionOnlyHandler(BaseFeatureHandler):
    """Feature handler for transcription-only realtime sessions."""

    def verify_access(self, session_id: str, user) -> bool:
        # Transcription is a lightweight utility; allow any connected user.
        return True

    def get_session_context(self, session_id: str, user) -> Optional[Dict[str, Any]]:
        return None

    def get_instructions(self, session_id: str, user, context: Optional[Dict[str, Any]]) -> str:
        # Not used – transcription-only sessions do not generate responses.
        return ""

    def log_message(self, session_id: str, user, data: Dict[str, Any]) -> None:
        # No persistent logging for raw transcription.
        pass

    def get_session_config(self, session_id: str, user, instructions: str) -> Optional[Dict[str, Any]]:
        """
        Return a transcription-only session configuration.

        Uses a standard ``session.update`` with ``modalities: ["text"]``
        so the model never generates audio.  ``turn_detection`` is disabled
        so responses are only created when the client explicitly commits
        the audio buffer.  ``input_audio_transcription`` delivers streaming
        transcription via ``conversation.item.input_audio_transcription.*``
        events.
        """
        import os
        from django.conf import settings
        transcription_model = "gpt-4o-transcribe"
        if not os.getenv('OPENAI_API_KEY'):
            transcription_model = getattr(settings, 'AZURE_OPENAI_WHISPER_DEPLOYMENT', 'whisper')

        language = 'en'
        if user and hasattr(user, 'settings') and isinstance(user.settings, dict):
            language = user.settings.get('voice_language', 'en').lower()
        if language not in ['en', 'hi']:
            language = 'en'

        return {
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": transcription_model,
                    "language": language,
                },
                "turn_detection": None,
            },
        }


# Auto-register when this module is imported
register_feature("transcription-only", TranscriptionOnlyHandler())
