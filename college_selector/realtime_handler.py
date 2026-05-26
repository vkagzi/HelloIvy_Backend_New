"""
College Selector – Realtime voice feature handler

Registered under the identifier ``college-selector`` so the unified
WebSocket consumer can delegate session lookup, instructions, and
message logging to this module.
"""
import uuid
import logging
from typing import Dict, Any, Optional

from utils.realtime_registry import BaseFeatureHandler, register_feature

logger = logging.getLogger(__name__)


class CollegeSelectorHandler(BaseFeatureHandler):
    """Feature handler for College Selector realtime voice sessions."""

    def __init__(self):
        # Buffer tool-generated display content per session so it can be
        # merged into the next assistant message instead of appearing as
        # a separate entry in the transcript.
        self._pending_display: Dict[str, str] = {}

    def verify_access(self, session_id: str, user) -> bool:
        try:
            from college_selector.models import CollegeSelectorSession
            from utils.user_helpers import get_user_instance

            if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
                return CollegeSelectorSession.objects.filter(session_id=session_id).exists()

            user_instance = get_user_instance(user)
            if not user_instance:
                return False
            return CollegeSelectorSession.objects.filter(session_id=session_id, user=user_instance).exists()
        except Exception as e:
            logger.error(f"Error verifying college selector session access: {e}", exc_info=True)
            return False

    def get_session_context(self, session_id: str, user) -> Optional[Dict[str, Any]]:
        try:
            from college_selector.models import CollegeSelectorSession, CollegeSelectorMessage
            from utils.user_helpers import get_user_instance
            from utils.profile_helpers import get_user_profile_data

            user_instance = get_user_instance(user)
            qs = CollegeSelectorSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                return None

            profile_user = user_instance or session.user
            user_profile = get_user_profile_data(profile_user)

            messages = CollegeSelectorMessage.objects.filter(session=session).order_by('timestamp')
            message_history = [
                {'role': 'assistant' if m.type == 'bot' else 'user', 'content': m.content}
                for m in messages
            ]

            return {
                'session': {
                    'current_phase': session.current_phase,
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'is_completed': session.is_completed,
                    'preferences': session.preferences,
                    'metadata': session.metadata,
                },
                'user_profile': user_profile,
                'message_history': message_history,
            }
        except Exception as e:
            logger.error(f"Error getting college selector session context: {e}", exc_info=True)
            return None

    def get_instructions(self, session_id: str, user, context: Optional[Dict[str, Any]]) -> str:
        try:
            from college_selector.langchain_service import college_selector_langchain_service

            if not context:
                return "You are a helpful college admissions counselor."

            session_info = context.get('session', {})
            user_profile = context.get('user_profile', {})
            preferences = session_info.get('preferences', {})

            instructions = college_selector_langchain_service.build_voice_instructions(
                preferences=preferences,
                user_profile=user_profile,
                session_info=session_info,
            )
            return instructions
        except Exception as e:
            logger.error(f"Error building college selector instructions: {e}", exc_info=True)
            return "You are a helpful college admissions counselor."

    @staticmethod
    def _extract_transcript(data: Dict[str, Any], msg_type: str):
        """Extract transcript and role from the incoming data dict."""
        transcript = data.get('transcript', '')
        if not transcript:
            return '', ''
        role = 'assistant' if 'assistant' in msg_type.lower() or 'response' in msg_type.lower() else 'user'
        return transcript, role

    def log_message(self, session_id: str, user, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Log a voice transcript and manage session-completion detection.

        For **user turns** the handler:
        1. Increments ``current_step``.
        2. Checks if the background conclusion flag (``should_conclude``) or
           the hard-cap (``MAX_CONVERSATION_QUESTIONS``) has been reached.
        3. When concluding, marks ``current_phase = 'completed'`` immediately
           (no buffer steps) so the frontend receives ``is_completed: True``.
        4. Fires a new background conclusion evaluation when appropriate.

        For **assistant turns** the handler checks whether the background
        thread set ``should_conclude`` while the AI was speaking.  If so it
        marks the session completed and returns a progress message – this
        handles the case where no further user messages will arrive.

        Returns a ``session.progress`` dict (or ``None``) that the consumer
        forwards to the frontend.
        """
        try:
            from college_selector.models import CollegeSelectorSession, CollegeSelectorMessage
            from utils.user_helpers import get_user_instance

            msg_type = data.get('type', '')
            transcript, role = self._extract_transcript(data, msg_type)
            if not transcript:
                return None

            user_instance = get_user_instance(user)
            qs = CollegeSelectorSession.objects.filter(session_id=session_id)
            if user_instance:
                qs = qs.filter(user=user_instance)
            session = qs.first()
            if not session:
                return None

            message_type = 'bot' if role == 'assistant' else 'user'

            # If there is buffered display content (e.g. comparison table)
            # from a preceding tool call, prepend it to this assistant
            # message so they appear as a single transcript entry.
            if role == 'assistant' and session_id in self._pending_display:
                transcript = self._pending_display.pop(session_id) + '\n\n' + transcript

            CollegeSelectorMessage.objects.create(
                session=session,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                type=message_type,
                content=transcript,
                medium='voice',
            )

            # ── Assistant turns ──────────────────────────────────────
            if role == 'assistant':
                session.refresh_from_db(fields=['current_step', 'total_steps', 'metadata', 'current_phase'])
                if session.current_phase == 'completed':
                    return None  # already done

                metadata = session.metadata or {}
                should_conclude = metadata.get('should_conclude', False)
                if should_conclude:
                    # Background thread determined the conversation should
                    # end.  Mark completed and notify the frontend.
                    session.current_phase = 'completed'
                    session.save(update_fields=['current_phase'])
                    user_count = CollegeSelectorMessage.objects.filter(
                        session=session, type='user',
                    ).count()
                    logger.info(
                        f"College selector: marked completed on assistant turn "
                        f"(step {session.current_step}) for {session_id}"
                    )
                    return {
                        'type': 'session.progress',
                        'current_step': session.current_step,
                        'total_steps': session.total_steps,
                        'questions_completed': user_count,
                        'progress_percentage': 100,
                        'is_completed': True,
                        'should_update_instructions': False,
                    }
                return None

            # ── User turns ───────────────────────────────────────────
            if role == 'user':
                session.current_step += 1
                new_step = session.current_step
                update_fields = ['current_step', 'updated_at']

                # Refresh metadata so we see the latest background-thread
                # updates (should_conclude).
                session.refresh_from_db(fields=['total_steps', 'metadata'])

                from college_selector.services import college_selector_service

                concluding = False
                if not session.is_completed:
                    concluding = college_selector_service.check_and_update_conclusion(
                        session, new_step,
                    )
                    if concluding:
                        # Mark completed immediately – no buffer steps.
                        session.current_phase = 'completed'
                        if 'current_phase' not in update_fields:
                            update_fields.append('current_phase')
                        logger.info(
                            f"College selector: marked completed on user turn "
                            f"(step {new_step}) for {session_id}"
                        )

                session.save(update_fields=update_fields)

                # Fire non-blocking background conclusion check
                if not session.is_completed and not concluding:
                    college_selector_service.fire_conclusion_check(
                        session_id, new_step, user_instance or session.user,
                    )

                user_count = CollegeSelectorMessage.objects.filter(
                    session=session, type='user',
                ).count()
                progress = min(
                    100, int((user_count / max(session.total_steps, 1)) * 100),
                )

                return {
                    'type': 'session.progress',
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'questions_completed': user_count,
                    'progress_percentage': progress,
                    'is_completed': session.is_completed,
                    'should_update_instructions': concluding or session.is_completed,
                }

            return None
        except Exception as e:
            logger.error(f"Error logging college selector message: {e}", exc_info=True)
            return None

    # ── Tool calling ─────────────────────────────────────────
    def get_tools(self):
        """Return OpenAI Realtime API tool definitions."""
        return [
            {
                "type": "function",
                "name": "display_comparison_table",
                "description": (
                    "Display a formatted comparison table of the student's "
                    "selected countries in the chat interface.  Call this tool "
                    "when comparing countries so the student can see the data "
                    "while you speak about it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "countries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Country name",
                                    },
                                    "avg_tuition": {
                                        "type": "string",
                                        "description": "Average tuition fees per year (e.g. '$30,000 - $55,000')",
                                    },
                                    "living_cost": {
                                        "type": "string",
                                        "description": "Average cost of living per year (e.g. '$15,000 - $20,000')",
                                    },
                                    "education_quality": {
                                        "type": "string",
                                        "description": "Education quality rating as X/5 (e.g. '5/5', '4/5')",
                                    },
                                    "post_study_visa": {
                                        "type": "string",
                                        "description": "Post-study work visa info (e.g. 'OPT: 1–3 years')",
                                    },
                                    "immigration_ease": {
                                        "type": "string",
                                        "description": "Immigration ease rating as X/5 (e.g. '3/5', '4/5')",
                                    },
                                },
                                "required": [
                                    "name",
                                    "avg_tuition",
                                    "living_cost",
                                    "education_quality",
                                    "post_study_visa",
                                    "immigration_ease",
                                ],
                            },
                        },
                    },
                    "required": ["countries"],
                },
            },
        ]

    def handle_tool_call(
        self,
        name: str,
        arguments: Dict[str, Any],
        session_id: str,
        user,
    ) -> Optional[Dict[str, Any]]:
        """Process an AI tool call and return display content."""
        if name == 'display_comparison_table':
            countries = arguments.get('countries', [])
            if not countries:
                return {'output': 'No countries provided.'}

            # Build a markdown comparison table
            table = (
                "| # | Country | Avg Tuition (USD/yr) | Living Cost (USD/yr) "
                "| Education Quality | Post-Study Work Visa | Immigration Ease |\n"
                "|---|---------|---------------------|---------------------"
                "|-------------------|---------------------|------------------|\n"
            )
            for i, c in enumerate(countries, 1):
                table += (
                    f"| {i} | {c.get('name', '')} "
                    f"| {c.get('avg_tuition', '')} "
                    f"| {c.get('living_cost', '')} "
                    f"| {c.get('education_quality', '')} "
                    f"| {c.get('post_study_visa', '')} "
                    f"| {c.get('immigration_ease', '')} |\n"
                )
            table += (
                "\n💡 **Tip**: Consider your budget, career goals, and "
                "long-term plans when comparing these countries."
            )

            # Buffer the table so it gets merged into the next assistant
            # message (the spoken follow-up), keeping them as one transcript
            # entry instead of two.
            self._pending_display[session_id] = table

            return {
                'output': 'Comparison table displayed to the student.',
                'display_content': table,
                'content_type': 'markdown',
            }

        logger.warning(f"Unknown tool call '{name}' for college selector")
        return {'output': f'Unknown tool: {name}'}

    def save_realtime_token_usage(self, session_id: str, user, usage_data: Dict[str, Any]) -> None:
        try:
            from college_selector.models import CollegeSelectorSession
            session = CollegeSelectorSession.objects.filter(session_id=session_id).first()
            if not session:
                return

            existing = session.token_usage or {}
            if "total_tokens" not in existing:
                existing["total_tokens"] = 0
                existing["total_input_tokens"] = 0
                existing["total_output_tokens"] = 0

            existing["total_input_tokens"] += usage_data.get("input_tokens", 0)
            existing["total_output_tokens"] += usage_data.get("output_tokens", 0)
            existing["total_tokens"] += usage_data.get("total_tokens", 0)

            session.token_usage = existing
            session.save(update_fields=['token_usage'])
        except Exception as e:
            logger.error(f"Error saving college selector token usage: {e}", exc_info=True)


# Register handler with unified consumer
_handler = CollegeSelectorHandler()
register_feature("college-selector", _handler)
