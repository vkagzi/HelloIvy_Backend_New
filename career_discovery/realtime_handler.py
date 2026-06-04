"""
Career & Degree Selection – Realtime voice feature handler

Registered under the identifier ``career-discovery`` so the unified
WebSocket consumer can delegate session lookup, instructions, and
message logging to this module.
"""
import uuid
import logging
from typing import Dict, Any, Optional

from utils.realtime_registry import BaseFeatureHandler, register_feature

logger = logging.getLogger(__name__)


class CareerDiscoveryHandler(BaseFeatureHandler):
    """Feature handler for Career & Degree Selection realtime voice sessions."""

    # ── access ───────────────────────────────────────────────
    def verify_access(self, session_id: str, user) -> bool:
        try:
            from career_discovery.models import CareerSession
            from utils.user_helpers import get_user_instance

            logger.info(f"🔐 Verifying access for career session {session_id}")

            if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
                logger.warning("⚠️ Unauthenticated user – allowing for development")
                return CareerSession.objects.filter(session_id=session_id).exists()

            user_instance = get_user_instance(user)
            if not user_instance:
                return False
            return CareerSession.objects.filter(session_id=session_id, user=user_instance).exists()
        except Exception as e:
            logger.error(f"❌ Error verifying career session access: {e}", exc_info=True)
            return False

    # ── context ──────────────────────────────────────────────
    def get_session_context(self, session_id: str, user) -> Optional[Dict[str, Any]]:
        try:
            from career_discovery.models import CareerSession, CareerMessage
            from domain_discovery.models import DomainRecommendation
            from utils.user_helpers import get_user_instance
            from utils.profile_helpers import get_user_profile_data

            user_instance = get_user_instance(user)
            qs = CareerSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                return None

            session_user = session.user
            user_profile = get_user_profile_data(session_user)

            messages = CareerMessage.objects.filter(session=session).order_by('timestamp')
            message_history = [
                {'role': 'assistant' if m.type == 'bot' else 'user', 'content': m.content}
                for m in messages
            ]

            # Domain recommendations from prior Stream & Subject Selection
            domain_context: Dict[str, Any] = {}
            if session.domain_session:
                recommendations = DomainRecommendation.objects.filter(
                    session=session.domain_session
                ).order_by('rank', '-match_percentage')[:5]
                domain_context = {
                    'recommendations': [
                        {
                            'title': rec.domain_title,
                            'match_percentage': rec.match_percentage,
                            'explanation': rec.why_recommended,
                            'key_interests': rec.key_interests,
                        }
                        for rec in recommendations
                    ]
                }

            # Include pre-computed domain choices if available
            metadata = session.metadata or {}
            domain_choices = metadata.get('domain_choices', {})

            return {
                'session': {
                    'current_phase': session.current_phase,
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'notes': session.notes,
                    'is_completed': session.is_completed,
                    'pre_final_asked': metadata.get('pre_final_asked', False),
                },
                'user_profile': user_profile,
                'message_history': message_history,
                'domain_context': domain_context,
                'domain_choices': domain_choices,
            }
        except Exception as e:
            logger.error(f"Error getting career session context: {e}", exc_info=True)
            return None

    # ── instructions ─────────────────────────────────────────
    def get_instructions(self, session_id: str, user, context: Optional[Dict[str, Any]]) -> str:
        try:
            from career_discovery.langchain_service import career_langchain_service

            # Get language from settings
            from utils.user_helpers import get_user_instance
            user_instance = get_user_instance(user)
            language = 'en'
            if user_instance and hasattr(user_instance, 'settings') and isinstance(user_instance.settings, dict):
                language = user_instance.settings.get('voice_language', 'en').lower()

            if not context:
                try:
                    prompt_data = career_langchain_service.build_prompt_for_step(
                        step=1,
                        user_profile={},
                        domain_context={},
                        session_notes="",
                        language=language,
                    )
                    instructions = prompt_data["system_prompt"]
                    if prompt_data["dynamic_context"]:
                        instructions += "\n\n" + prompt_data["dynamic_context"]
                    return instructions
                except Exception:
                    return "You are a helpful Career & Degree Selection assistant. Help the student explore specific career paths."

            session_info = context.get('session', {})
            user_profile = context.get('user_profile', {})
            domain_context = context.get('domain_context', {})

            profile_data = user_profile.get('profile', {})
            personal = profile_data.get('personalDetails', {})
            educational = profile_data.get('educational', {})
            first_name = getattr(user, 'first_name', '') or 'there'
            academic_level = educational.get('academicLevel', 'student')

            current_step = session_info.get('current_step', 0)
            domain_choices = context.get('domain_choices', {})
            domain_context_with_choices = dict(domain_context) if domain_context else {}
            if domain_choices:
                domain_context_with_choices['domain_choices'] = domain_choices

            latest_user_response = ""

            prompt_data = career_langchain_service.build_prompt_for_step(
                step=current_step,
                user_response=latest_user_response,
                user_profile=user_profile,
                user_name=first_name,
                domain_context=domain_context_with_choices,
                session_notes=session_info.get('notes', ''),
                messages=None,
                language=language,
            )

            instructions = prompt_data["system_prompt"]
            if prompt_data["dynamic_context"]:
                instructions += "\n\n" + prompt_data["dynamic_context"]

            domain_selection_instructions = prompt_data["domain_selection_instructions"]

            is_concluding = session_info.get('is_completed', False) or (current_step + 1 >= session_info.get('total_steps', 18))
            pre_final_asked = session_info.get('pre_final_asked', False)

            status_line = ''
            if is_concluding:
                if language == 'hi':
                    if not pre_final_asked:
                        status_line = (
                            '- STATUS: The session evaluation has determined we have gathered enough information. '
                            'In your NEXT response, ask the student: "आज आपसे बात करके बहुत अच्छा लगा! '
                            'इससे पहले कि हम अपना सत्र समाप्त करें, क्या कोई आखिरी सवाल है जो आप पूछना चाहते हैं?" '
                            'Wait for their response before wrapping up. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation. Do not shift to a more formal or robotic tone for the closing.'
                        )
                    else:
                        status_line = (
                            '- STATUS: The pre-final question has already been asked. '
                            'If the student asked a question, answer it briefly and warmly in Hindi Devanagari (2-3 sentences). '
                            'Then wrap up the conversation in Hindi Devanagari: thank them for sharing, let them know their '
                            'personalized career recommendations are being prepared, and say goodbye. '
                            'Exact closing message: "मेरे साथ यह सब साझा करने के लिए धन्यवाद! 🎉 मैंने आपकी रुचियों और शक्तियों के बारे में बहुत कुछ सीखा है। मुझे हर चीज़ का विश्लेषण करने दें और आपकी व्यक्तिगत करियर सिफारिशें तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"'
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation.'
                        )
                else:
                    if not pre_final_asked:
                        status_line = (
                            '- STATUS: The session evaluation has determined we have gathered enough information. '
                            'In your NEXT response, ask the student: "It was fantastic talking to you today! '
                            'Is there one final question you wish to ask before we close our session?" '
                            'Wait for their response before wrapping up. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation. Do not shift to a more formal or robotic tone for the closing.'
                        )
                    else:
                        status_line = (
                            '- STATUS: The pre-final question has already been asked. '
                            'If the student asked a question, answer it briefly and warmly (2-3 sentences). '
                            'Then wrap up the conversation: thank them for sharing, let them know their '
                            'personalized career recommendations are being prepared, and say goodbye. '
                            'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation. The goodbye should feel natural and continuous, not like a different speaker.'
                        )

            instructions += f"""
{domain_selection_instructions}
<voice_conversation_context>
You are having a natural voice conversation with {first_name}, a {academic_level}.
{status_line}

VOICE-SPECIFIC GUIDELINES:
- The session starts with a personalized intro message from Ivy. If you are asked to announce the intro, speak it exactly as given, word for word. Do not paraphrase or add to it.
- Domain selection has already been completed before this conversation. Do NOT ask the student to select domains.
- Keep responses concise and natural for voice conversation
- One question at a time - do not bundle questions
- Each response = A brief acknowledgment (1 sentence) + ONE question
- Be warm, conversational, and genuine - not robotic
- No lists, no numbering, no multiple questions in one response
- Do NOT use any formatting (markdown, bullets, asterisks) in your responses
- Speak in full, natural sentences as if talking face-to-face
- Sound like a trusted advisor who's present and listening
- When presenting options, speak them naturally rather than listing them
- VOICE CONSISTENCY: Maintain the same voice style, tone, pacing, energy level, and expressiveness from the very first message through to the conclusion. Whether you are asking questions, acknowledging responses, delivering the closing message, or resuming after a pause — your voice should sound like the same person throughout.
</voice_conversation_context>
"""
            return instructions
        except Exception as e:
            logger.error(f"❌ Error building career instructions: {e}", exc_info=True)
            return "You are a helpful Career & Degree Selection assistant. Help the student explore specific career paths."

    # ── logging ──────────────────────────────────────────────
    def log_message(self, session_id: str, user, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            from career_discovery.models import CareerSession, CareerMessage
            from utils.user_helpers import get_user_instance

            msg_type = data.get('type', '')
            transcript, role = self._extract_transcript(data, msg_type)
            if not transcript:
                return None

            user_instance = get_user_instance(user)
            qs = CareerSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                logger.warning(f"Career session {session_id} not found for message logging")
                return None

            message_type = 'bot' if role == 'assistant' else 'user'
            CareerMessage.objects.create(
                session=session,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                type=message_type,
                content=transcript,
                step_number=session.current_step,
                phase=session.get_current_phase(),
                medium='voice',
            )
            logger.info(f"💾 Saved {message_type} voice message for career session {session_id}")

            # Mark *pre_final_asked* when the AI actually delivers its
            # response in a concluding session.  Setting it here — on the
            # bot turn — ensures the instruction refresh triggered by the
            # *previous* user turn carried the "please ask" STATUS, while
            # the *next* user-turn refresh will carry "already asked".
            if role == 'assistant':
                metadata = session.metadata or {}
                approaching_end = (session.current_step + 1 >= session.total_steps)
                if approaching_end and not session.is_completed and not metadata.get('pre_final_asked'):
                    metadata['pre_final_asked'] = True
                    session.metadata = metadata
                    session.save(update_fields=['metadata'])
                return None

            if role == 'user':
                session.current_step += 1
                update_fields = ['current_step', 'updated_at']

                # Before marking complete, check if we need to ask the
                # pre-final question first.
                metadata = session.metadata or {}
                if session.current_step >= session.total_steps and not session.is_completed:
                    if not metadata.get('pre_final_asked'):
                        # Extend by 1 step so the AI can ask the pre-final
                        # question and the user can respond before completion.
                        session.total_steps += 1
                        update_fields.append('total_steps')
                    else:
                        session.is_completed = True
                        update_fields.append('is_completed')

                session.save(update_fields=update_fields)

                approaching_end = (session.current_step + 1 >= session.total_steps)

                # Refresh instructions when approaching the end
                # so the AI receives the closing STATUS.
                should_update = approaching_end or session.is_completed

                return {
                    'type': 'session.progress',
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'questions_completed': session.current_step,
                    'progress_percentage': round((session.current_step / session.total_steps) * 100) if session.total_steps else 0,
                    'is_completed': session.is_completed,
                    'should_update_instructions': should_update,
                }

            return None
        except Exception as e:
            logger.error(f"Error logging career conversation message: {e}", exc_info=True)
            return None

    # ── domain extraction ────────────────────────────────────
    @staticmethod
    def _extract_and_save_domain_choices(session) -> None:
        """Extract domain choices from the first Q&A turns and save to session metadata.

        Called once after the user answers Q2 (secondary domain selection).
        Mirrors the structured extraction logic in the text-mode service.
        """
        try:
            from career_discovery.models import CareerMessage
            from career_discovery.langchain_service import career_langchain_service
            from domain_discovery.models import DomainRecommendation

            # Get the first messages (intro, Q1, A1, Q2, A2)
            messages = list(
                CareerMessage.objects.filter(session=session)
                .order_by('timestamp')
                .values('type', 'content')[:6]
            )
            if not messages:
                logger.warning(f"No messages found for domain extraction in session {session.session_id}")
                return

            # Build domain_context from session's domain_session
            domain_context: Dict[str, Any] = {}
            if session.domain_session:
                recommendations = DomainRecommendation.objects.filter(
                    session=session.domain_session
                ).order_by('rank', '-match_percentage')[:5]
                domain_context = {
                    'recommendations': [
                        {
                            'title': rec.domain_title,
                            'match_percentage': rec.match_percentage,
                            'explanation': rec.why_recommended,
                            'key_interests': rec.key_interests,
                        }
                        for rec in recommendations
                    ]
                }

            # Convert to the format expected by extract_domain_choices
            formatted_messages = [
                {'type': m['type'], 'content': m['content']}
                for m in messages
            ]

            domain_choices = career_langchain_service.extract_domain_choices(
                messages=formatted_messages,
                domain_context=domain_context,
            )

            # Persist in session metadata
            meta = session.metadata or {}
            meta['domain_choices'] = domain_choices
            session.metadata = meta
            session.save(update_fields=['metadata'])
            logger.info(
                f"✅ Voice domain extraction for {session.session_id}: "
                f"{domain_choices.get('primary_domain')} + {domain_choices.get('secondary_domain')}"
            )
        except Exception as e:
            logger.error(f"❌ Error extracting domain choices for voice session: {e}", exc_info=True)

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
            from career_discovery.models import CareerSession
            from utils.user_helpers import get_user_instance

            user_instance = get_user_instance(user)
            qs = CareerSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                logger.warning(f"Career session {session_id} not found for token usage save")
                return

            self._merge_realtime_into_token_usage(session, usage)
        except Exception as e:
            logger.error(f"Error saving realtime token usage for career session: {e}", exc_info=True)

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
register_feature('career-discovery', CareerDiscoveryHandler())
