"""
College Selector Service Layer
Handles session management, preference saving, message processing, and recommendations.
"""
import uuid
import logging
import threading
from typing import Dict, Any, List, Optional

from django.utils import timezone

from asgiref.sync import sync_to_async
logger = logging.getLogger(__name__)

from utils.message_constants import MessageType
from .models import CollegeSelectorSession, CollegeSelectorMessage, CollegeRecommendation
from .langchain_service import college_selector_langchain_service
from utils.profile_helpers import get_user_profile_data
from utils.user_helpers import get_user_display_name


def build_intro_message(user, preferences_data: dict, language: str = 'en') -> str:
    """Build a personalized opening message using the student's name and preferences."""
    name = get_user_display_name(user=user)
    degree_type = preferences_data.get('degree_type', 'college')
    primary_major = preferences_data.get('primary_major', '')
    secondary_major = preferences_data.get('secondary_major', '')

    if language == 'hi':
        msg = f"नमस्ते {name}, मुझे बहुत खुशी है कि आप {degree_type} डिग्री प्राप्त करना चाहते हैं"
        if primary_major:
            msg += f", जिसमें आपका मुख्य विषय (major) {primary_major} होगा"
        if secondary_major:
            msg += f" और सहायक विषय (minor) {secondary_major} होगा"
        msg += "। क्या हम शुरू करें? बस कहें, हाँ!"
        return msg

    msg = f"Hi {name}, excited that you wish to pursue a {degree_type} degree"
    if primary_major:
        msg += f" with a major in {primary_major}"
    if secondary_major:
        msg += f" and a minor in {secondary_major}"
    msg += ". Shall we get started? Simply say, Yes!"
    return msg


class CollegeSelectorService:
    """Service class for managing College Selector sessions."""

    def __init__(self):
        self.langchain_service = college_selector_langchain_service
        self.max_conversation_questions = CollegeSelectorSession.MAX_CONVERSATION_QUESTIONS
        self.min_conversation_questions = CollegeSelectorSession.MIN_CONVERSATION_QUESTIONS

    def _save_token_usage(self, session: CollegeSelectorSession, new_usage: Dict):
        if new_usage is None or not new_usage.get("categories"):
            return
        existing = session.token_usage or {}
        if "categories" not in existing:
            existing["categories"] = {}
            existing["total_input_tokens"] = 0
            existing["total_output_tokens"] = 0
            existing["total_tokens"] = 0
            existing["total_llm_calls"] = 0

        for cat_name, cat_data in new_usage.get("categories", {}).items():
            if cat_name not in existing["categories"]:
                existing["categories"][cat_name] = {
                    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_count": 0,
                }
            for key in ["input_tokens", "output_tokens", "total_tokens", "call_count"]:
                existing["categories"][cat_name][key] += cat_data.get(key, 0)

        for key in ["total_input_tokens", "total_output_tokens", "total_tokens", "total_llm_calls"]:
            existing[key] += new_usage.get(key, 0)

        session.token_usage = existing
        session.save(update_fields=['token_usage'])

    def create_session(self, user) -> CollegeSelectorSession:
        """Create a new College Selector session in preferences phase."""
        session_id = f"college_{uuid.uuid4().hex[:12]}"
        session = CollegeSelectorSession.objects.create(
            user=user,
            session_id=session_id,
            current_step=0,
            current_phase='preferences',
        )
        return session

    # ─── Conclusion check helpers (used by voice flow) ────────────

    def _evaluate_conclusion_background(self, session_id: str, current_step: int, messages: List[Dict[str, Any]], preferences: Dict[str, Any], user_profile: Dict[str, Any]):
        """Background task: evaluate whether the conversation should conclude.

        Runs in a separate thread (non-blocking). Updates session.metadata with
        should_conclude and pending_topics, and session.total_steps if concluding.
        """
        try:
            from django.db import connection
            token_usage = {}

            result = self.langchain_service.evaluate_conclusion(
                current_step=current_step,
                messages=messages,
                preferences=preferences,
                user_profile=user_profile,
                min_questions=self.min_conversation_questions,
                max_questions=self.max_conversation_questions,
                token_usage=token_usage,
            )

            session = CollegeSelectorSession.objects.get(session_id=session_id)

            metadata = session.metadata or {}
            metadata['should_conclude'] = result['should_conclude']
            metadata['pending_topics'] = result['pending_topics']
            metadata['last_checked_step'] = current_step
            session.metadata = metadata

            if result['should_conclude']:
                session.save(update_fields=['metadata'])
                logger.info(f"College selector background conclusion: CONCLUDING at step {current_step} for {session_id}")
            else:
                session.save(update_fields=['metadata'])
                logger.info(f"College selector background conclusion: CONTINUE for {session_id} (pending: {result['pending_topics']})")

            self._save_token_usage(session, token_usage)
            connection.close()
        except Exception as e:
            logger.error(f"Error in background conclusion check for college selector {session_id}: {e}")

    def check_and_update_conclusion(self, session: CollegeSelectorSession, new_step: int) -> bool:
        """Check whether the session should conclude at the given step.

        Applies:
        1. Hard cap at ``max_conversation_questions``.
        2. Honours a prior background ``should_conclude`` flag.

        If concluding, sets ``session.total_steps = new_step`` (caller must
        still persist via ``session.save``).

        Returns True when the session should end.
        """
        if new_step >= self.max_conversation_questions:
            session.total_steps = new_step
            logger.info(f"College selector conclusion: hard cap at step {new_step} for {session.session_id}")
            return True

        if new_step > self.min_conversation_questions:
            metadata = session.metadata or {}
            if metadata.get('should_conclude', False):
                session.total_steps = new_step
                logger.info(f"College selector conclusion: background flag honoured at step {new_step} for {session.session_id}")
                return True

        return False

    def fire_conclusion_check(self, session_id: str, current_step: int, user) -> None:
        """Spawn a background thread to evaluate whether the conversation
        should conclude. Safe to call from any flow (text or voice).

        No-ops if:
        - ``current_step`` < ``min_conversation_questions``
        - ``current_step`` >= ``max_conversation_questions`` (hard cap already handled)
        - The step has already been checked.
        """
        if current_step < self.min_conversation_questions:
            return
        if current_step >= self.max_conversation_questions:
            return

        try:
            session = CollegeSelectorSession.objects.get(session_id=session_id)
            if session.is_completed:
                return

            metadata = session.metadata or {}
            if metadata.get('last_checked_step', 0) >= current_step:
                return

            all_messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(user)

            thread = threading.Thread(
                target=self._evaluate_conclusion_background,
                args=(session_id, current_step, all_messages, session.preferences, user_profile),
                daemon=True,
            )
            thread.start()
            logger.info(f"College selector: fired background conclusion check at step {current_step} for {session_id}")
        except Exception as e:
            logger.error(f"Failed to fire college selector conclusion check for {session_id}: {e}")

    def save_preferences(self, session: CollegeSelectorSession, preferences_data: dict) -> CollegeSelectorSession:
        """Save static questionnaire answers and transition to conversation phase."""
        metadata = session.metadata or {}
        metadata['conversation_started_at'] = timezone.now().isoformat()

        session.preferences = preferences_data
        session.preferences_completed = True
        session.current_phase = 'conversation'
        session.metadata = metadata
        session.save(update_fields=['preferences', 'preferences_completed', 'current_phase', 'metadata', 'updated_at'])

        # Get language from settings
        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        # Create initial bot message
        intro = build_intro_message(session.user, preferences_data, language=language)
        CollegeSelectorMessage.objects.create(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type=MessageType.BOT,
            content=intro,
        )

        return session

    def get_session_by_id(self, session_id: str) -> Optional[CollegeSelectorSession]:
        try:
            return CollegeSelectorSession.objects.get(session_id=session_id)
        except CollegeSelectorSession.DoesNotExist:
            return None

    def get_session_messages(self, session: CollegeSelectorSession) -> List[Dict[str, Any]]:
        messages = CollegeSelectorMessage.objects.filter(session=session).order_by('timestamp')
        return [
            {
                'message_id': msg.message_id,
                'type': msg.type,
                'content': msg.content,
                'medium': msg.medium,
                'timestamp': msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    async def process_message_stream(self, session: CollegeSelectorSession, user_message: str):
        """Asynchronous generator for streaming AI responses via SSE."""
        import json
        from asgiref.sync import sync_to_async
        
        current_step = session.current_step

        # Access Check: Admins and paid users get full access, others capped at 5
        # from apps.accounts.services import check_module_access
        # access_info = await sync_to_async(check_module_access)(session.user, "college_selector")
        
        # if access_info["access"] == "trial" and access_info["current_usage"] >= access_info["limit"]:
        #     # Trial limit reached
        #     lock_message = "Purchase to continue this module"
        #     yield f"data: {json.dumps({'delta': lock_message, 'is_complete': True, 'error': 'TRIAL_LIMIT_REACHED'})}\n\n"
        #     return

        new_step = current_step + 1

        # Get language from settings
        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        # Save user message
        await sync_to_async(CollegeSelectorMessage.objects.create)(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type=MessageType.USER,
            content=user_message,
        )

        session.current_step = new_step
        is_complete = False
        bot_response = ""
        save_fields = ['current_step', 'updated_at']

        if new_step >= self.max_conversation_questions:
            is_complete = True
            if language == 'hi':
                bot_response = (
                    "सभी प्रश्नों के लिए धन्यवाद! अब मुझे अच्छी तरह समझ आ गया है कि आप क्या तलाश रहे हैं। "
                    "मुझे आपके लिए 20 कॉलेज सिफारिशों की व्यक्तिगत सूची तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"
                )
            else:
                bot_response = (
                    "Thank you for all your questions! I now have a great understanding of what you're looking for. "
                    "Let me prepare your personalized list of 20 college recommendations. Head over to see your results!"
                )
            session.total_steps = new_step
            session.current_phase = 'completed'
            save_fields.extend(['total_steps', 'current_phase'])
            
            yield f"data: {json.dumps({'delta': bot_response, 'is_complete': False})}\n\n"
        else:
            # Generate AI response
            all_messages = await sync_to_async(self.get_session_messages)(session)
            user_profile = await sync_to_async(get_user_profile_data)(session.user)
            
            bot_response_full = ""
            token_usage = {}

            # Use LangChain astream for non-blocking delivery
            async for chunk in self.langchain_service.astream_question(
                current_step=new_step,
                messages=all_messages,
                preferences=session.preferences,
                user_profile=user_profile,
                token_usage=token_usage,
                language=language,
            ):
                bot_response_full += chunk
                yield f"data: {json.dumps({'delta': chunk, 'is_complete': False})}\n\n"
            
            bot_response = bot_response_full
            
            # Check for implicit conclusion in non-streaming result if needed, 
            # but for now we rely on the background check or hard cap.
            # We'll fire the background check after this.
            
            await sync_to_async(self._save_token_usage)(session, token_usage)

        # Save bot response
        await sync_to_async(CollegeSelectorMessage.objects.create)(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type=MessageType.BOT,
            content=bot_response,
        )

        await sync_to_async(session.save)(update_fields=save_fields)
        
        # Background check for next time
        if not is_complete:
            await sync_to_async(self.fire_conclusion_check)(session.session_id, new_step, session.user)
            
        yield f"data: {json.dumps({'delta': '', 'is_complete': True})}\n\n"

    def process_message(self, session: CollegeSelectorSession, user_message: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for process_message_stream.
        """
        import json
        from asgiref.sync import async_to_sync

        async def _collect_stream():
            full_response = ""
            async for chunk in self.process_message_stream(session, user_message):
                if chunk.startswith("data: "):
                    try:
                        data = json.loads(chunk[6:].strip())
                        full_response += data.get('delta', '')
                    except (json.JSONDecodeError, ValueError):
                        continue
            return full_response

        bot_response = async_to_sync(_collect_stream)()
        
        # Refresh session to get latest state after stream updates
        session.refresh_from_db()

        questions_completed = CollegeSelectorMessage.objects.filter(
            session=session, type=MessageType.USER
        ).count()
        progress = min(100, int((questions_completed / max(session.total_steps if session.total_steps > 0 else self.max_conversation_questions, 1)) * 100))

        return {
            'session_id': session.session_id,
            'bot_response': bot_response,
            'current_step': session.current_step,
            'is_complete': session.current_phase == 'completed',
            'progress_percentage': progress,
            'questions_completed': questions_completed,
            'token_usage': session.token_usage or {},
        }

    def end_session(self, session: CollegeSelectorSession) -> None:
        session.current_phase = 'completed'
        session.total_steps = session.current_step
        session.save(update_fields=['current_phase', 'total_steps', 'updated_at'])

    def generate_recommendations(self, session: CollegeSelectorSession) -> list:
        """Generate 20 college recommendations via LLM."""
        all_messages = self.get_session_messages(session)
        user_profile = get_user_profile_data(session.user)
        token_usage = {}

        result = self.langchain_service.generate_recommendations(
            preferences=session.preferences,
            user_profile=user_profile,
            messages=all_messages,
            token_usage=token_usage,
        )

        # Clear old recommendations
        CollegeRecommendation.objects.filter(session=session).delete()

        recommendations = []
        for rank, rec_data in enumerate(result["recommendations"], start=1):
            rec = CollegeRecommendation.objects.create(
                session=session,
                university_name=rec_data.get("university_name", ""),
                website_url=rec_data.get("website_url", ""),
                location=rec_data.get("location", ""),
                country=rec_data.get("country", ""),
                deadlines=rec_data.get("deadlines", {}),
                degree_and_major=rec_data.get("degree_and_major", ""),
                tuition_fees=rec_data.get("tuition_fees", ""),
                cost_of_living=rec_data.get("cost_of_living", ""),
                scholarships=rec_data.get("scholarships", []),
                academic_requirements=rec_data.get("academic_requirements", {}),
                additional_requirements=rec_data.get("additional_requirements", []),
                university_type=rec_data.get("university_type", ""),
                global_ranking=rec_data.get("global_ranking", {}),
                acceptance_rate=rec_data.get("acceptance_rate", ""),
                application_fee=rec_data.get("application_fee", ""),
                tests_required=rec_data.get("tests_required", []),
                post_study_work_visa=rec_data.get("post_study_work_visa", ""),
                employment_rate=rec_data.get("employment_rate", ""),
                language=rec_data.get("language", "English"),
                campus_type=rec_data.get("campus_type", ""),
                intl_student_support=rec_data.get("intl_student_support", ""),
                fit_category=rec_data.get("fit_category", "match"),
                fit_reasoning=rec_data.get("fit_reasoning", ""),
                suggested_deadline=rec_data.get("suggested_deadline", ""),
                match_percentage=rec_data.get("match_percentage", 50),
                description=rec_data.get("description", ""),
                rank=rank,
            )
            recommendations.append(rec)

        self._save_token_usage(session, token_usage)
        return recommendations

    def get_recommendations(self, session: CollegeSelectorSession) -> list:
        return list(CollegeRecommendation.objects.filter(session=session).order_by('rank'))

    def get_transcript(self, session: CollegeSelectorSession) -> Dict[str, Any]:
        messages = CollegeSelectorMessage.objects.filter(session=session).order_by('timestamp')
        transcript_messages = []
        question_num = 0
        pending_bot = None

        for msg in messages:
            if msg.type == MessageType.BOT:
                if pending_bot:
                    # Flush previous unpaired bot message (e.g. comparison table)
                    question_num += 1
                    transcript_messages.append({
                        'question_number': question_num,
                        'bot_question': pending_bot.content,
                        'student_response': '',
                        'timestamp': pending_bot.timestamp,
                    })
                pending_bot = msg
            elif msg.type == MessageType.USER and pending_bot:
                question_num += 1
                transcript_messages.append({
                    'question_number': question_num,
                    'bot_question': pending_bot.content,
                    'student_response': msg.content,
                    'timestamp': msg.timestamp,
                })
                pending_bot = None

        # Flush any trailing bot message (e.g. concluding message)
        if pending_bot:
            question_num += 1
            transcript_messages.append({
                'question_number': question_num,
                'bot_question': pending_bot.content,
                'student_response': '',
                'timestamp': pending_bot.timestamp,
            })

        user = session.user
        return {
            'session_id': session.session_id,
            'student_name': get_user_display_name(None, user, ''),
            'started_at': session.created_at,
            'completed_at': session.updated_at,
            'total_questions': question_num,
            'messages': transcript_messages,
        }


# Singleton
college_selector_service = CollegeSelectorService()
