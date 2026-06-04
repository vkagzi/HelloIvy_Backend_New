"""
Stream & Subject Selection – Realtime voice feature handler

Registered under the identifier ``domain-discovery`` so the unified
WebSocket consumer can delegate session lookup, instructions, and
message logging to this module.
"""
import uuid
import logging
from typing import Dict, Any, Optional

from utils.realtime_registry import BaseFeatureHandler, register_feature

logger = logging.getLogger(__name__)


class DomainDiscoveryHandler(BaseFeatureHandler):
    """Feature handler for Stream & Subject Selection realtime voice sessions."""

    # ── access ───────────────────────────────────────────────
    def verify_access(self, session_id: str, user) -> bool:
        try:
            from domain_discovery.models import DomainSession
            from utils.user_helpers import get_user_instance

            logger.info(f"🔐 Verifying access for domain session {session_id}")

            if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
                logger.warning("⚠️ Unauthenticated user – allowing for development")
                return DomainSession.objects.filter(session_id=session_id).exists()

            user_instance = get_user_instance(user)
            if not user_instance:
                return False
            return DomainSession.objects.filter(session_id=session_id, user=user_instance).exists()
        except Exception as e:
            logger.error(f"❌ Error verifying domain session access: {e}", exc_info=True)
            return False

    # ── context ──────────────────────────────────────────────
    def get_session_context(self, session_id: str, user) -> Optional[Dict[str, Any]]:
        try:
            from domain_discovery.models import DomainSession, DomainMessage
            from utils.user_helpers import get_user_instance
            from utils.profile_helpers import get_user_profile_data

            user_instance = get_user_instance(user)
            qs = DomainSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                return None

            profile_user = user_instance or session.user
            user_profile = get_user_profile_data(profile_user)

            messages = DomainMessage.objects.filter(session=session).order_by('timestamp')
            message_history = [
                {'role': 'assistant' if m.type == 'bot' else 'user', 'content': m.content}
                for m in messages
            ]

            metadata = session.metadata or {}
            return {
                'session': {
                    'current_phase': session.current_phase,
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'riasec_completed': session.riasec_completed,
                    'deepdive_completed': session.deepdive_completed,
                    'notes': getattr(session, 'notes', ''),
                    'is_completed': session.is_completed,
                    'should_conclude': metadata.get('should_conclude', False),
                    'approaching_end': session.current_step + 1 >= session.total_steps,
                    'pre_final_asked': metadata.get('pre_final_asked', False),
                },
                'user_profile': user_profile,
                'message_history': message_history,
            }
        except Exception as e:
            logger.error(f"Error getting domain session context: {e}", exc_info=True)
            return None

    # ── instructions ─────────────────────────────────────────
    def get_instructions(self, session_id: str, user, context: Optional[Dict[str, Any]]) -> str:
        try:
            from domain_discovery.langchain_service import domain_langchain_service

            # Fetch language from settings
            from utils.user_helpers import get_user_instance
            user_instance = get_user_instance(user)
            language = 'en'
            if user_instance and hasattr(user_instance, 'settings') and isinstance(user_instance.settings, dict):
                language = user_instance.settings.get('voice_language', 'en').lower()

            if not context:
                try:
                    prompt_data = domain_langchain_service.build_prompt_for_step(
                        step=1,
                        user_profile={},
                        min_questions=10,
                        max_questions=20,
                        session_notes="",
                        language=language,
                    )
                    return prompt_data["system_prompt"]
                except Exception:
                    return "You are a helpful Stream & Subject Selection assistant."

            session_info = context.get('session', {})
            user_profile = context.get('user_profile', {})

            profile_data = user_profile.get('profile', {})
            personal = profile_data.get('personalDetails', {})
            educational = profile_data.get('educational', {})
            first_name = getattr(user, 'first_name', '') or 'there'
            academic_level = educational.get('academicLevel', 'student')

            current_step = session_info.get('deepdive_completed', 0) + 1

            # NOTE: conversation history is NOT included in the system
            # instructions because the frontend seeds it into the Realtime API
            # context via seedConversationHistory(). Including it here too would
            # duplicate every message and quickly exhaust the context window.
            prompt_data = domain_langchain_service.build_prompt_for_step(
                step=current_step,
                user_profile=user_profile,
                min_questions=10,
                max_questions=session_info.get('total_steps', 20),
                session_notes=session_info.get('notes', ''),
                user_name=first_name,
                language=language,
            )
            instructions = prompt_data["system_prompt"]

            is_concluding = session_info.get('should_conclude') or session_info.get('is_completed') or session_info.get('approaching_end', False)
            pre_final_asked = session_info.get('pre_final_asked', False)

            status_line = ''
            if is_concluding:
                if not pre_final_asked:
                    if language == 'hi':
                        status_line = (
                            '- STATUS: The session evaluation has determined we have gathered enough information. '
                            'In your NEXT response, ask the student in Devanagari script Hindi: "आज आपसे बात करके बहुत अच्छा लगा! '
                            'इससे पहले कि हम अपना सत्र समाप्त करें, क्या कोई आखिरी सवाल है जो आप पूछना चाहते हैं?" '
                            'Wait for their response before wrapping up. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation.'
                        )
                    else:
                        status_line = (
                            '- STATUS: The session evaluation has determined we have gathered enough information. '
                            'In your NEXT response, ask the student: "It was fantastic talking to you today! '
                            'Is there one final question you wish to ask before we close our session?" '
                            'Wait for their response before wrapping up. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation. Do not shift to a more formal or robotic tone for the closing.'
                        )
                else:
                    if language == 'hi':
                        status_line = (
                            '- STATUS: The pre-final question has already been asked. '
                            'If the student asked a question, answer it briefly and warmly in Devanagari script Hindi (2-3 sentences). '
                            'Then wrap up the conversation in Devanagari script Hindi: thank them for sharing, let them know their '
                            'personalized domain recommendations are being prepared, and say goodbye. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation.'
                        )
                    else:
                        status_line = (
                            '- STATUS: The pre-final question has already been asked. '
                            'If the student asked a question, answer it briefly and warmly (2-3 sentences). '
                            'Then wrap up the conversation: thank them for sharing, let them know their '
                            'personalized domain recommendations are being prepared, and say goodbye. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation. The goodbye should feel natural and continuous, not like a different speaker.'
                        )

            instructions += f"""

<voice_conversation_context>
You are having a natural voice conversation with {first_name}, a {academic_level}.

Current Progress:
- Current step: {session_info.get('current_step', 0)} of {session_info.get('total_steps', 20)}
- Phase: {session_info.get('current_phase', 'deepdive')}
- Questions asked: {session_info.get('deepdive_completed', 0)}
{status_line}

VOICE-SPECIFIC GUIDELINES:
- The session starts with a static intro message from Ivy. If you are asked to announce the intro, speak it exactly as given, word for word. Do not paraphrase or add to it.
- After the student responds to the intro, proceed to ask your first deepdive question.
- Keep responses concise and natural for voice conversation
- One question at a time - do not bundle questions
- Be warm and conversational in tone
- Do NOT use any formatting (markdown, bullets, numbering, asterisks) in your responses
- Speak in full, natural sentences as if talking face-to-face
- After each student response, briefly acknowledge what they said before asking the next question
- VOICE CONSISTENCY: Maintain the same voice style, tone, pacing, energy level, and expressiveness from the very first message through to the conclusion. Whether you are asking questions, acknowledging responses, transitioning between topics, delivering the closing message, or resuming after a pause — your voice should sound like the same person throughout.
</voice_conversation_context>
"""
            return instructions
        except Exception as e:
            logger.error(f"❌ Error building domain instructions: {e}", exc_info=True)
            return "You are a helpful Stream & Subject Selection assistant."

    # ── logging ──────────────────────────────────────────────
    def log_message(self, session_id: str, user, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Log a voice transcript and – for user turns – mirror the same
        session-progression logic that the text ``process_message`` uses:

        1. Increment ``current_step``.
        2. Hard-cap at ``MAX_DEEPDIVE_QUESTIONS`` → mark session complete.
        3. Honour a prior background conclusion check (``should_conclude``).
        4. Fire a new background conclusion evaluation once past
           ``MIN_DEEPDIVE_QUESTIONS``.

        Returns a ``session.progress`` dict for user turns so the
        consumer can relay it to the frontend.
        """
        try:
            from domain_discovery.models import DomainSession, DomainMessage
            from utils.user_helpers import get_user_instance

            msg_type = data.get('type', '')
            transcript, role = self._extract_transcript(data, msg_type)
            if not transcript:
                return None

            user_instance = get_user_instance(user)
            qs = DomainSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                logger.warning(f"Domain session {session_id} not found for message logging")
                return None

            message_type = 'bot' if role == 'assistant' else 'user'
            DomainMessage.objects.create(
                session=session,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                type=message_type,
                content=transcript,
                question_type='deepdive',
                medium='voice',
            )
            logger.info(f"💾 Saved {message_type} voice message for domain session {session_id}")

            # Mark *pre_final_asked* when the AI actually delivers its
            # response in a concluding session.  Setting it here — on the
            # bot turn — ensures the instruction refresh triggered by the
            # *previous* user turn carried the "please ask" STATUS, while
            # the *next* user-turn refresh will carry "already asked".
            if role == 'assistant':
                session.refresh_from_db(fields=['current_step', 'total_steps', 'metadata', 'is_completed'])
                metadata = session.metadata or {}
                approaching_end = (session.current_step + 1 >= session.total_steps)
                should_conclude = metadata.get('should_conclude', False)
                is_concluding = session.is_completed or should_conclude or approaching_end
                if is_concluding and not metadata.get('pre_final_asked'):
                    metadata['pre_final_asked'] = True
                    session.metadata = metadata
                    session.save(update_fields=['metadata'])
                return None

            if role == 'user':
                session.current_step += 1
                new_step = session.current_step
                update_fields = ['current_step', 'updated_at']

                # Refresh conclusion-related fields from DB so we see the latest
                # background thread updates (should_conclude, total_steps).
                session.refresh_from_db(fields=['total_steps', 'metadata'])

                from domain_discovery.services import domain_discovery_service

                # Only run conclusion logic if the session isn't already completed
                concluding = False
                if not session.is_completed:
                    concluding = domain_discovery_service.check_and_update_conclusion(session, new_step)
                    if concluding:
                        # Voice mode: give the AI two extra steps –
                        # one for the pre-final question, one for the wrap-up.
                        session.total_steps = new_step + 2
                        update_fields.append('total_steps')
                        # Ensure should_conclude is persisted so get_instructions
                        # recognises the concluding state even before approaching_end
                        # (e.g. hard-cap conclusion where background flag was never set).
                        meta_c = session.metadata or {}
                        if not meta_c.get('should_conclude'):
                            meta_c['should_conclude'] = True
                            session.metadata = meta_c
                            if 'metadata' not in update_fields:
                                update_fields.append('metadata')

                approaching_end = (session.current_step + 1 >= session.total_steps)

                session.save(update_fields=update_fields)

                # Fire non-blocking background conclusion check (no-ops if not needed)
                if not session.is_completed and not concluding:
                    domain_discovery_service.fire_conclusion_check(
                        session_id, new_step, user_instance or session.user,
                    )

                return {
                    'type': 'session.progress',
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'questions_completed': session.current_step,
                    'progress_percentage': round((session.current_step / session.total_steps) * 100) if session.total_steps else 0,
                    'is_completed': session.is_completed,
                    'should_update_instructions': approaching_end or concluding or session.is_completed,
                }

            return None
        except Exception as e:
            logger.error(f"Error logging domain conversation message: {e}", exc_info=True)
            return None

    # ── helpers ──────────────────────────────────────────────
    @staticmethod
    def _extract_transcript(data: Dict[str, Any], msg_type: str):
        transcript = None
        role = None
        if msg_type == 'conversation.item.input_audio_transcription.completed':
            transcript = data.get('transcript', '').strip()
            role = 'user'
        elif msg_type == 'response.audio_transcript.done':
            transcript = data.get('transcript', '').strip()
            role = 'assistant'
        return transcript, role

    # ── token usage persistence ──────────────────────────────
    def save_realtime_token_usage(self, session_id: str, user, usage: Dict[str, Any]) -> None:
        try:
            from domain_discovery.models import DomainSession
            from utils.user_helpers import get_user_instance

            user_instance = get_user_instance(user)
            qs = DomainSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                logger.warning(f"Domain session {session_id} not found for token usage save")
                return

            self._merge_realtime_into_token_usage(session, usage)
        except Exception as e:
            logger.error(f"Error saving realtime token usage for domain session: {e}", exc_info=True)

    @staticmethod
    def _merge_realtime_into_token_usage(session, new_usage: Dict[str, Any]) -> None:
        """Merge realtime voice token usage into session.token_usage under the 'realtime_voice' category."""
        existing = session.token_usage or {}
        if 'categories' not in existing:
            existing['categories'] = {}

        # Initialize totals if missing
        for key in ('total_input_tokens', 'total_output_tokens', 'total_tokens',
                    'total_llm_calls', 'total_cache_read_tokens', 'total_cache_creation_tokens',
                    'total_reasoning_tokens'):
            existing.setdefault(key, 0)

        cat = existing['categories'].get('realtime_voice', {
            'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'call_count': 0,
            'cache_read_tokens': 0, 'cache_creation_tokens': 0, 'reasoning_tokens': 0,
            'input_text_tokens': 0, 'input_audio_tokens': 0,
            'output_text_tokens': 0, 'output_audio_tokens': 0,
            'input_cached_tokens': 0, 'response_count': 0,
        })

        # Accumulate standard category fields
        cat['input_tokens'] += new_usage.get('input_tokens', 0)
        cat['output_tokens'] += new_usage.get('output_tokens', 0)
        cat['total_tokens'] += new_usage.get('total_tokens', 0)
        cat['call_count'] += new_usage.get('response_count', 0)
        cat['cache_read_tokens'] += new_usage.get('input_cached_tokens', 0)

        # Accumulate audio/text detail fields
        cat['input_text_tokens'] += new_usage.get('input_text_tokens', 0)
        cat['input_audio_tokens'] += new_usage.get('input_audio_tokens', 0)
        cat['output_text_tokens'] += new_usage.get('output_text_tokens', 0)
        cat['output_audio_tokens'] += new_usage.get('output_audio_tokens', 0)
        cat['input_cached_tokens'] += new_usage.get('input_cached_tokens', 0)
        cat['response_count'] += new_usage.get('response_count', 0)

        existing['categories']['realtime_voice'] = cat

        # Update top-level totals
        existing['total_input_tokens'] += new_usage.get('input_tokens', 0)
        existing['total_output_tokens'] += new_usage.get('output_tokens', 0)
        existing['total_tokens'] += new_usage.get('total_tokens', 0)
        existing['total_llm_calls'] += new_usage.get('response_count', 0)
        existing['total_cache_read_tokens'] += new_usage.get('input_cached_tokens', 0)

        session.token_usage = existing
        session.save(update_fields=['token_usage'])


# ── Auto-register on import ─────────────────────────────────
register_feature('domain-discovery', DomainDiscoveryHandler())
