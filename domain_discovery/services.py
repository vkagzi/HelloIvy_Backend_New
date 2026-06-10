"""
Stream & Subject Selection Service Layer
Handles session management, message processing, and integrates with LangChain AI service
"""
import uuid
import threading
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

from utils.message_constants import MessageType
from .models import DomainSession, DomainMessage, DomainRecommendation
from .constants import DOMAIN_CONFIG
from .langchain_service import domain_langchain_service
from apps.profiles.models import UserProfile
from utils.profile_helpers import get_user_profile_data
from utils.profile_formatting import format_user_profile_context
from utils.user_helpers import get_user_display_name
from apps.accounts.models import ActivityLog


# Static intro message — no LLM call needed
DOMAIN_INTRO_MESSAGE = (
    "Hello, I'm Ivy\u2014your career and education guide. "
    "In this module, I'll help you discover which Stream and Subjects fit you best.\n\n"
    "Please answer honestly, ask if anything is unclear, and for multiple-choice questions just reply with A, B, or C.\n\n"
    "Remember, there are no right or wrong answers\u2014just be yourself. Shall we get started?"
)

DOMAIN_INTRO_MESSAGE_HI_MALE = (
    "नमस्ते, मैं आईवी हूँ—आपका करियर और शिक्षा मार्गदर्शक। "
    "इस मॉड्यूल में, मैं आपको यह जानने में मदद करूँगा कि कौन सा स्ट्रीम और विषय आपके लिए सबसे उपयुक्त हैं।\n\n"
    "कृपया ईमानदारी से उत्तर दें, यदि कुछ स्पष्ट न हो तो पूछें, और बहुविकल्पीय प्रश्नों के लिए बस A, B या C के साथ उत्तर दें।\n\n"
    "याद रखें, कोई सही या गलत उत्तर नहीं हैं—बस स्वाभाविक रहें। क्या हम शुरू करें?"
)

DOMAIN_INTRO_MESSAGE_HI_FEMALE = (
    "नमस्ते, मैं आईवी हूँ—आपकी करियर और शिक्षा मार्गदर्शिका। "
    "इस मॉड्यूल में, मैं आपको यह जानने में मदद करूँगी कि कौन सा स्ट्रीम और विषय आपके लिए सबसे उपयुक्त हैं।\n\n"
    "कृपया ईमानदारी से उत्तर दें, यदि कुछ स्पष्ट न हो तो पूछें, और बहुविकल्पीय प्रश्नों के लिए बस A, B या C के साथ उत्तर दें।\n\n"
    "याद रखें, कोई सही या गलत उत्तर नहीं हैं—बस स्वाभाविक रहें। क्या हम शुरू करें?"
)


def build_domain_intro_message(user_name: str, language: str = 'en', persona: str = 'male') -> str:
    """Build a personalized intro message with the user's name for Stream & Subject Selection."""
    if language == 'hi':
        if persona == 'female':
            return (
                f"नमस्ते {user_name}, मैं आईवी हूँ—आपकी करियर और शिक्षा मार्गदर्शिका। "
                f"इस मॉड्यूल में, मैं आपको यह जानने में मदद करूँगी कि कौन सा स्ट्रीम और विषय आपके लिए सबसे उपयुक्त हैं।\n\n"
                f"कृपया ईमानदारी से उत्तर दें, यदि कुछ स्पष्ट न हो तो पूछें, और बहुविकल्पीय प्रश्नों के लिए बस A, B या C के साथ उत्तर दें।\n\n"
                f"याद रखें, कोई सही या गलत उत्तर नहीं हैं—बस स्वाभाविक रहें। क्या हम शुरू करें?"
            )
        return (
            f"नमस्ते {user_name}, मैं आईवी हूँ—आपका करियर और शिक्षा मार्गदर्शक। "
            f"इस मॉड्यूल में, मैं आपको यह जानने में मदद करूँगा कि कौन सा स्ट्रीम और विषय आपके लिए सबसे उपयुक्त हैं।\n\n"
            f"कृपया ईमानदारी से उत्तर दें, यदि कुछ स्पष्ट न हो तो पूछें, और बहुविकल्पीय प्रश्नों के लिए बस A, B या C के साथ उत्तर दें।\n\n"
            f"याद रखें, कोई सही या गलत उत्तर नहीं हैं—बस स्वाभाविक रहें। क्या हम शुरू करें?"
        )
    return (
        f"Hello {user_name}, I'm Ivy\u2014your career and education guide. "
        f"In this module, I'll help you discover which Stream and Subjects fit you best.\n\n"
        f"Please answer honestly, ask if anything is unclear, and for multiple-choice questions just reply with A, B, or C.\n\n"
        f"Remember, there are no right or wrong answers\u2014just be yourself. Shall we get started?"
    )


class DomainDiscoveryService:
    """
    Service class for managing Stream & Subject Selection sessions and conversations.
    Integrates with LangChain-based AI service for question generation and recommendations.
    """

    def __init__(self):
        self.langchain_service = domain_langchain_service
        # Use constants from DomainSession model
        from .models import DomainSession
        # RIASEC questions disabled - only deepdive questions for now
        # self.riasec_questions_count = DomainSession.RIASEC_QUESTIONS_COUNT
        self.riasec_questions_count = 0  # Disabled
        self.min_deepdive_questions = DomainSession.MIN_DEEPDIVE_QUESTIONS
        self.max_deepdive_questions = DomainSession.MAX_DEEPDIVE_QUESTIONS
        self.deepdive_questions_count = DomainSession.MAX_DEEPDIVE_QUESTIONS  # For backward compat
        self.total_steps = self.max_deepdive_questions  # Max as upper bound

    def _get_user_category(self, user_profile: Dict[str, Any]) -> str:
        """Determine user category (school, undergrad, professional) from profile"""
        profile_data = user_profile.get('profile', user_profile)
        educational = profile_data.get('educational', {})
        academic_level = educational.get('academicLevel', '')
        
        # Handle both string and list values (academicLevel can be either)
        if isinstance(academic_level, list):
            academic_level = academic_level[0] if academic_level else ''
        
        academic_level_lower = str(academic_level).lower()
        
        # Map based on exact academicLevel values from profile field definitions
        # Possible values: 'High School (9th–12th grade)', 'College/Undergraduate', 'Postgraduate', 'Working/Completed College'
        
        # High School students
        if 'high school' in academic_level_lower or '9th' in academic_level_lower or '12th' in academic_level_lower:
            return "school_students"
        
        # College/Undergraduate and Postgraduate students
        if any(level in academic_level_lower for level in ['college', 'undergraduate', 'postgraduate', 'postgrad']):
            return "undergrad_postgrad"
        
        # Working/Completed College - treat as professionals
        if 'working' in academic_level_lower or 'completed college' in academic_level_lower:
            return "working_professionals"
            
        # Fallback: Check for work experience/job title as sign of professional
        personal_details = profile_data.get('personalDetails', {})
        if personal_details.get('jobTitle') or profile_data.get('experience'):
            return "working_professionals"
            
        # Final fallback: Default to school students if grade exists, otherwise working professionals
        if user_profile.get('grade'):
            return "school_students"
            
        return "working_professionals"

    def _get_riasec_question(self, category: str, question_number: int) -> Dict[str, Any]:
        """Get a RIASEC question from constants based on category and number"""
        categories = RIASEC_CONFIG.get("categories", {})
        category_data = categories.get(category, categories.get("school_students"))
        questions = category_data.get("questions", [])
        
        # Ensure question_number is within bounds (1-indexed)
        idx = (question_number - 1) % len(questions)
        q_data = questions[idx]
        
        return {
            'question': q_data['prompt'],
            'choices': [q_data['options']['A']['text'], q_data['options']['B']['text']],
            'question_type': 'riasec',
            'dimensions': [q_data['options']['A']['dimension'], q_data['options']['B']['dimension']]
        }

    def _save_token_usage(self, session: DomainSession, new_usage: Dict):
        """Merge new token usage into session's existing token_usage and save."""
        if new_usage is None or not new_usage.get("categories"):
            return
        existing = session.token_usage or {}
        
        # Initialize existing structure if empty
        if "categories" not in existing:
            existing["categories"] = {}
        if "total_input_tokens" not in existing:
            existing["total_input_tokens"] = 0
            existing["total_output_tokens"] = 0
            existing["total_tokens"] = 0
            existing["total_llm_calls"] = 0
            existing["total_cache_read_tokens"] = 0
            existing["total_cache_creation_tokens"] = 0
            existing["total_reasoning_tokens"] = 0
        
        # Merge categories
        for cat_name, cat_data in new_usage.get("categories", {}).items():
            if cat_name not in existing["categories"]:
                existing["categories"][cat_name] = {
                    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_count": 0,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0, "reasoning_tokens": 0,
                }
            existing["categories"][cat_name]["input_tokens"] += cat_data.get("input_tokens", 0)
            existing["categories"][cat_name]["output_tokens"] += cat_data.get("output_tokens", 0)
            existing["categories"][cat_name]["total_tokens"] += cat_data.get("total_tokens", 0)
            existing["categories"][cat_name]["call_count"] += cat_data.get("call_count", 0)
            existing["categories"][cat_name]["cache_read_tokens"] += cat_data.get("cache_read_tokens", 0)
            existing["categories"][cat_name]["cache_creation_tokens"] += cat_data.get("cache_creation_tokens", 0)
            existing["categories"][cat_name]["reasoning_tokens"] += cat_data.get("reasoning_tokens", 0)
        
        # Merge totals
        existing["total_input_tokens"] += new_usage.get("total_input_tokens", 0)
        existing["total_output_tokens"] += new_usage.get("total_output_tokens", 0)
        existing["total_tokens"] += new_usage.get("total_tokens", 0)
        existing["total_llm_calls"] += new_usage.get("total_llm_calls", 0)
        existing["total_cache_read_tokens"] += new_usage.get("total_cache_read_tokens", 0)
        existing["total_cache_creation_tokens"] += new_usage.get("total_cache_creation_tokens", 0)
        existing["total_reasoning_tokens"] += new_usage.get("total_reasoning_tokens", 0)
        
        session.token_usage = existing
        session.save(update_fields=['token_usage'])

    def _generate_and_save_session_notes(self, session_id: str, user_profile: Dict[str, Any]):
        """Background task: generate session notes and save to the session.
        
        Runs in a separate thread so the first question is not blocked.
        Uses its own DB connection (Django handles per-thread connections).
        """
        try:
            from django.db import connection
            token_usage = {}
            session_notes = self.langchain_service.generate_session_notes(user_profile, token_usage=token_usage)
            if session_notes:
                session = DomainSession.objects.get(session_id=session_id)
                session.notes = session_notes
                session.save(update_fields=['notes'])
                self._save_token_usage(session, token_usage)
                logger.info(f"Session notes saved in background for {session_id}")
            connection.close()
        except Exception as e:
            logger.error(f"Error generating session notes in background: {e}")

    def _evaluate_conclusion_background(self, session_id: str, current_step: int, messages: List[Dict[str, Any]], user_profile: Dict[str, Any]):
        """Background task: evaluate whether the conversation should conclude.
        
        Runs in a separate thread (non-blocking). Updates session.metadata with
        should_conclude and pending_topics, and session.total_steps if concluding.
        Only called after min_steps has been reached.
        """
        try:
            from django.db import connection
            token_usage = {}
            
            result = self.langchain_service.evaluate_conclusion(
                current_step=current_step,
                messages=messages,
                user_profile=user_profile,
                min_questions=self.min_deepdive_questions,
                max_questions=self.max_deepdive_questions,
                token_usage=token_usage
            )
            
            session = DomainSession.objects.get(session_id=session_id)
            
            # Update metadata with conclusion check results
            metadata = session.metadata or {}
            metadata['should_conclude'] = result['should_conclude']
            metadata['pending_topics'] = result['pending_topics']
            metadata['last_checked_step'] = current_step
            session.metadata = metadata
            
            # If should conclude, also update total_steps so is_completed returns True
            if result['should_conclude']:
                # Set total_steps to current_step + 2 so: (a) the student answers the
                # current question, (b) the voice AI has one buffer step to deliver a
                # warm wrap-up before is_completed triggers on the step after that.
                # For text mode, check_and_update_conclusion will catch the
                # should_conclude flag on the next step and set total_steps properly.
                session.total_steps = current_step + 2
                session.save(update_fields=['metadata', 'total_steps'])
                logger.info(f"Background conclusion check: CONCLUDING at step {current_step} for {session_id}")
            else:
                session.save(update_fields=['metadata'])
                logger.info(f"Background conclusion check: CONTINUE for {session_id} (pending: {result['pending_topics']})")
            
            self._save_token_usage(session, token_usage)
            connection.close()
        except Exception as e:
            logger.error(f"Error in background conclusion check for {session_id}: {e}")

    # ─── Shared conclusion helpers (used by both text and voice flows) ───

    def check_and_update_conclusion(self, session: DomainSession, new_step: int) -> bool:
        """Check whether the session should conclude at the given step.

        Applies:
        1. Hard cap at ``max_deepdive_questions``.
        2. Honours a prior background ``should_conclude`` flag.

        If concluding, sets ``session.total_steps = new_step`` (caller must
        still persist via ``session.save``).

        Returns True when the session should end.
        """
        # Hard cap
        if new_step >= self.max_deepdive_questions:
            session.total_steps = new_step
            logger.info(f"Conclusion: hard cap reached at step {new_step} for {session.session_id}")
            return True

        # Background conclusion check decided to conclude
        if new_step > self.min_deepdive_questions:
            metadata = session.metadata or {}
            if metadata.get('should_conclude', False):
                session.total_steps = new_step
                logger.info(f"Conclusion: background flag honoured at step {new_step} for {session.session_id}")
                return True

        return False

    def evaluate_conclusion_sync(self, session: DomainSession, new_step: int) -> bool:
        """Run conclusion evaluation synchronously (blocking).

        Called inline from ``process_message`` when past
        ``min_deepdive_questions`` to avoid the race condition where
        rapid messages outpace the asynchronous background thread.

        Updates ``session.metadata`` and ``session.total_steps`` in
        memory; caller must include those fields in ``save_fields``.

        Returns True when the session should conclude.
        """
        try:
            all_messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(session.user)
            token_usage = {}

            result = self.langchain_service.evaluate_conclusion(
                current_step=new_step,
                messages=all_messages,
                user_profile=user_profile,
                min_questions=self.min_deepdive_questions,
                max_questions=self.max_deepdive_questions,
                token_usage=token_usage,
            )

            # Persist evaluation result in metadata so voice mode can see it
            metadata = session.metadata or {}
            metadata['should_conclude'] = result['should_conclude']
            metadata['pending_topics'] = result['pending_topics']
            metadata['last_checked_step'] = new_step
            session.metadata = metadata

            self._save_token_usage(session, token_usage)

            if result['should_conclude']:
                session.total_steps = new_step
                logger.info(f"Synchronous conclusion: CONCLUDING at step {new_step} for {session.session_id}")
                return True

            logger.info(f"Synchronous conclusion: CONTINUE for {session.session_id} (pending: {result['pending_topics']})")
            return False
        except Exception as e:
            logger.error(f"Error in synchronous conclusion check for {session.session_id}: {e}")
            return False

    def fire_conclusion_check(self, session_id: str, current_step: int, user) -> None:
        """Spawn a background thread to evaluate whether the conversation
        should conclude.  Safe to call from any flow (text or voice).

        No-ops if:
        - ``current_step`` < ``min_deepdive_questions``
        - ``current_step`` >= ``max_deepdive_questions`` (hard cap already handled)
        - The step has already been checked (``last_checked_step``).
        """
        if current_step < self.min_deepdive_questions:
            return
        if current_step >= self.max_deepdive_questions:
            return

        try:
            session = DomainSession.objects.get(session_id=session_id)
            if session.is_completed:
                return

            metadata = session.metadata or {}
            if metadata.get('last_checked_step', 0) >= current_step:
                return

            all_messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(user)

            thread = threading.Thread(
                target=self._evaluate_conclusion_background,
                args=(session_id, current_step, all_messages, user_profile),
                daemon=True,
            )
            thread.start()
            logger.info(f"Fired background conclusion check at step {current_step} for {session_id}")
        except Exception as e:
            logger.error(f"Failed to fire conclusion check for {session_id}: {e}")

    def create_session(self, user) -> DomainSession:
        """Create a new Stream & Subject Selection session for a user"""
        # Create new session
        session_id = f"domain_{uuid.uuid4().hex[:12]}"
        session = DomainSession.objects.create(
            user=user,
            session_id=session_id,
            current_step=0,
        )

        ActivityLog.log(
            user=user,
            event_type="module_start",
            description=f"Started Stream & Subject Selection session ({session_id})",
            metadata={"module": "domain_discovery", "session_id": session_id}
        )

        # Get user profile data for AI context
        user_profile = get_user_profile_data(user)
        
        # Fire session notes generation in background thread (non-blocking).
        # Notes enrich later questions but are NOT needed for the first question.
        notes_thread = threading.Thread(
            target=self._generate_and_save_session_notes,
            args=(session_id, user_profile),
            daemon=True
        )
        notes_thread.start()
        
        # Get language and persona from settings
        from utils.user_helpers import get_user_instance
        user_instance = get_user_instance(user)
        language = 'en'
        persona = 'male'
        if user_instance and hasattr(user_instance, 'settings') and isinstance(user_instance.settings, dict):
            language = user_instance.settings.get('voice_language', 'en').lower()
            persona = user_instance.settings.get('voice_persona', 'male').lower()
            
        user_name = get_user_display_name(None, user, 'there')
        intro_content = build_domain_intro_message(
            user_name=user_name,
            language=language,
            persona=persona
        )

        # Static intro message — no LLM call needed
        DomainMessage.objects.create(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type='bot',
            content=intro_content,
            question_type='general',
            choices=[]
        )

        return session

    def get_active_session(self, user) -> Optional[DomainSession]:
        """Get the in-progress Stream & Subject Selection session for a user.
        is_active=True means the session row is valid (not soft-deleted).
        Session completion is determined solely by is_completed (current_step >= total_steps).
        """
        session = DomainSession.objects.filter(
            user=user, is_active=True
        ).order_by('-created_at').first()
        if session and not session.is_completed:
            return session
        return None

    def get_session_by_id(self, session_id: str) -> Optional[DomainSession]:
        """Get a session by its ID"""
        try:
            return DomainSession.objects.get(session_id=session_id)
        except DomainSession.DoesNotExist:
            return None

    def get_session_messages(self, session: DomainSession) -> List[Dict[str, Any]]:
        """Get all messages for a session as a list of dicts"""
        messages = DomainMessage.objects.filter(session=session).order_by('timestamp')
        return [
            {
                'message_id': msg.message_id,
                'type': msg.type,
                'content': msg.content,
                'question_type': msg.question_type,
                'choices': msg.choices,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in messages
        ]

    async def process_message_stream(self, session: DomainSession, user_message: str):
        """
        Async generator that yields SSE-formatted JSON chunks.
        """
        # Cache values that trigger DB queries
        current_step = session.current_step
        new_step = current_step + 1
        
        # Save user message (since this is async, we use sync_to_async or just run in sync context for simple DB ops if needed)
        # But for streaming, we want to start yielding as soon as possible.
        from asgiref.sync import sync_to_async
        
        await sync_to_async(DomainMessage.objects.create)(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type='user',
            content=user_message,
            question_type='general'
        )

        await sync_to_async(ActivityLog.log)(
            user=session.user,
            event_type="llm_interaction",
            description=f"User sent message in Stream & Subject Selection",
            metadata={
                "module": "domain_discovery",
                "session_id": session.session_id,
                "type": "user",
                "content": user_message[:200] + ("..." if len(user_message) > 200 else "")
            }
        )

        # Update session step
        session.current_step = new_step
        
        # Refresh conclusion-related fields
        await sync_to_async(session.refresh_from_db)(fields=['total_steps', 'metadata'])
        
        save_fields = ['current_step', 'updated_at']
        
        # Initialize response variables
        question_type = 'general'
        bot_response = ""
        is_complete = False

        # Get language from settings
        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        PRE_FINAL_QUESTION_HI = (
            "आज आपसे बात करके बहुत अच्छा लगा! इससे पहले कि हम अपना सत्र समाप्त करें, क्या कोई आखिरी सवाल है जो आप पूछना चाहते हैं?"
        )

        CONCLUSION_MSG_HI = (
            "मेरे साथ यह सब साझा करने के लिए धन्यवाद! 🎉 मैंने आपकी रुचियों और जिज्ञासाओं के बारे में बहुत कुछ सीखा है। मुझे हर चीज़ का विश्लेषण करने दें और आपकी व्यक्तिगत डोमेन सिफ़ारिशें तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"
        )

        PRE_FINAL_QUESTION = PRE_FINAL_QUESTION_HI if language == 'hi' else (
            "It was fantastic talking to you today! Is there one final question "
            "you wish to ask before we close our session?"
        )

        CONCLUSION_MSG = CONCLUSION_MSG_HI if language == 'hi' else (
            "Thank you for sharing all of that with me! 🎉 I've learned so much about "
            "your interests and curiosities. Let me analyze everything and prepare your "
            "personalized domain recommendations. Head over to see your results!"
        )

        metadata = session.metadata or {}

        # ── Pre-final answer handling ────────────────────────────
        if metadata.get('pre_final_asked') and not metadata.get('pre_final_answered'):
            metadata['pre_final_answered'] = True
            session.metadata = metadata
            save_fields.append('metadata')
            is_complete = True
            bot_response = await sync_to_async(self._handle_pre_final_response)(session, user_message)

        # ── Step 1: Check existing conclusion state ──────────────
        if not is_complete and session.is_completed:
            is_complete = True
            bot_response = CONCLUSION_MSG
        elif not is_complete and await sync_to_async(self.check_and_update_conclusion)(session, new_step):
            is_complete = True
            save_fields.append('total_steps')
            bot_response = CONCLUSION_MSG

        # ── Step 2: Synchronous conclusion evaluation ────────────
        if (not is_complete
                and new_step >= self.min_deepdive_questions
                and new_step < self.max_deepdive_questions):
            if await sync_to_async(self.evaluate_conclusion_sync)(session, new_step):
                is_complete = True
                save_fields.extend(['total_steps', 'metadata'])
                bot_response = CONCLUSION_MSG
            else:
                # Persist last_checked_step even when not concluding
                metadata = session.metadata or {}
                session.metadata = metadata
                save_fields.append('metadata')

        # ── Pre-final question intercept ─────────────────────────
        if is_complete and not metadata.get('pre_final_asked'):
            is_complete = False
            session.total_steps = new_step + 1
            metadata['pre_final_asked'] = True
            session.metadata = metadata
            if 'total_steps' not in save_fields:
                save_fields.append('total_steps')
            if 'metadata' not in save_fields:
                save_fields.append('metadata')
            bot_response = PRE_FINAL_QUESTION
            question_type = 'general'

        # ── Step 3: Stream and Generate response ──────────
        if not is_complete and not bot_response:
            all_messages = await sync_to_async(self.get_session_messages)(session) if new_step >= 2 else None
            user_profile = await sync_to_async(get_user_profile_data)(session.user)
            user_name = await sync_to_async(get_user_display_name)(None, session.user, '')
            
            question_type = 'deepdive'
            full_bot_response = ""
            
            # Use LangChain astream for true async delivery
            async for chunk in self.langchain_service.astream_question(
                current_step=new_step,
                user_message=user_message if new_step >= 2 else "",
                messages=all_messages,
                user_profile=user_profile,
                min_questions=self.min_deepdive_questions,
                max_questions=self.max_deepdive_questions,
                session_notes=session.notes or "",
                user_name=user_name,
                language=language,
            ):
                full_bot_response += chunk
                yield f"data: {json.dumps({'delta': chunk, 'is_complete': False})}\n\n"
            
            bot_response = full_bot_response


            # Hard cap: if we've hit max questions, conclude regardless
            if new_step >= self.max_deepdive_questions:
                session.total_steps = new_step
                save_fields.append('total_steps')
        else:
            # For non-streaming cases (conclusion/greeting), yield the full response in one chunk
            yield f"data: {json.dumps({'delta': bot_response, 'is_complete': False})}\n\n"

        # Finalize
        await sync_to_async(DomainMessage.objects.create)(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type='bot',
            content=bot_response,
            question_type=question_type,
            choices=[]
        )

        await sync_to_async(session.save)(update_fields=save_fields)
        
        yield f"data: {json.dumps({'delta': '', 'is_complete': True})}\n\n"

    @transaction.atomic
    def process_message(self, session: DomainSession, user_message: str) -> Dict[str, Any]:
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

        return {
            'session_id': session.session_id,
            'bot_response': bot_response,
            'question_type': 'deepdive',  # Simplified for synchronous return
            'choices': [],
            'current_step': session.current_step,
            'riasec_completed': 0, # Not used in Domain Discovery as same as Career
            'deepdive_completed': session.current_step,
            'is_complete': session.is_completed,
            'phase': 'deepdive',
            'progress_percentage': int((session.current_step / session.total_steps) * 100) if session.total_steps > 0 else 0,
            'questions_completed': session.current_step,
        }

    def end_session(self, session: DomainSession) -> DomainSession:
        """Conclude a Stream & Subject Selection session by setting total_steps = current_step.
        This causes is_completed to return True, marking the interview as finished.
        is_active is NOT touched here — it is only a soft-delete/validity flag.
        """
        session.total_steps = session.current_step
        session.save(update_fields=['total_steps'])
        return session

    def _handle_pre_final_response(self, session: DomainSession, user_message: str) -> str:
        """Handle the user's response to the pre-final question.

        If the user asked a question, answer it briefly then append the
        conclusion message.  Otherwise just return the conclusion message.
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        CONCLUSION_MSG_HI = (
            "मेरे साथ यह सब साझा करने के लिए धन्यवाद! 🎉 मैंने आपकी रुचियों और जिज्ञासाओं के बारे में बहुत कुछ सीखा है। मुझे हर चीज़ का विश्लेषण करने दें और आपकी व्यक्तिगत डोमेन सिफ़ारिशें तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"
        )

        CONCLUSION_MSG = CONCLUSION_MSG_HI if language == 'hi' else (
            "Thank you for sharing all of that with me! 🎉 I've learned so much about "
            "your interests and curiosities. Let me analyze everything and prepare your "
            "personalized domain recommendations. Head over to see your results!"
        )

        try:
            # Build conversation history so the LLM has full context to answer
            all_messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(session.user)
            profile_context = format_user_profile_context(user_profile, user_name=get_user_display_name(None, session.user, ''))

            system_instruction = (
                "You are a warm, supportive academic counselor. The student was asked "
                "if they have one final question before the session closes.\n\n"
                "Below is the student's profile and the full conversation history "
                "so you have context to answer any question they may ask.\n\n"
                f"STUDENT PROFILE:\n{profile_context}\n\n"
                "Determine if the student's response contains a genuine question. "
                "If YES: answer it concisely (2-3 sentences max), drawing on the "
                "conversation context and their profile, then end with the "
                "exact closing line provided below.\n"
                "If NO (they said no, goodbye, thanks, etc.): respond ONLY with the "
                "exact closing line below.\n\n"
                f"CLOSING LINE: {CONCLUSION_MSG}"
            )
            if language == 'hi':
                system_instruction += (
                    "\n\n[CRITICAL Hindi Instruction: You MUST answer the student's question in Hindi using Devanagari script. "
                    "Do NOT use English or Hinglish. Your response must be in clear, warm, and natural Hindi. "
                    "Ensure you end with the exact CLOSING LINE in Hindi provided above.]"
                )

            llm_messages = [
                SystemMessage(content=system_instruction),
            ]

            # Add conversation history
            for msg in all_messages:
                content = msg.get('content', '')
                msg_type = msg.get('type')
                if msg_type == MessageType.USER:
                    llm_messages.append(HumanMessage(content=content))
                elif msg_type == MessageType.BOT:
                    llm_messages.append(AIMessage(content=content))

            # Add the current user message (their answer to the pre-final question)
            llm_messages.append(HumanMessage(content=user_message))

            llm = self.langchain_service.llm
            response = llm.invoke(llm_messages)
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            return content.strip()
        except Exception as e:
            logger.error(f"Error handling pre-final response: {e}")
            return CONCLUSION_MSG

    @transaction.atomic
    def generate_recommendations(self, session: DomainSession) -> List[DomainRecommendation]:
        """Generate and store domain recommendations for a session.
        
        Uses select_for_update() to prevent duplicate recommendations when
        multiple concurrent requests are made for the same session.
        """
        # Lock the session row to prevent concurrent recommendation generation
        # This ensures only one request can generate recommendations at a time
        locked_session = DomainSession.objects.select_for_update().get(pk=session.pk)
        
        # Check if recommendations already exist (after acquiring lock)
        existing_recs = DomainRecommendation.objects.filter(session=locked_session)
        if existing_recs.exists():
            return list(existing_recs)

        # Get conversation messages
        messages = self.get_session_messages(locked_session)
        
        # Get user profile data
        user_profile = get_user_profile_data(locked_session.user)
        
        # Get predefined domains for validation
        predefined_domains = DOMAIN_CONFIG
        
        # Token usage tracker for recommendations generation
        token_usage = {}
        
        # Generate recommendations via LangChain
        # This will raise an exception if it fails - no fallbacks
        recommendations_data = self.langchain_service.generate_recommendations(messages, user_profile, token_usage=token_usage)
        
        # Validate we got recommendations
        if not recommendations_data or len(recommendations_data) < 5:
            raise ValueError(f"Failed to generate recommendations. Expected 5, got {len(recommendations_data) if recommendations_data else 0}")
        
        # Store recommendations
        recommendations = []
        
        for idx, rec_data in enumerate(recommendations_data[:5]):
            domain_title = rec_data.get('domain_title', 'Unknown Domain')
            
            # Validate against predefined domains
            if domain_title not in predefined_domains:
                raise ValueError(f"Invalid domain '{domain_title}' returned. Please retry.")
            
            rec = DomainRecommendation.objects.create(
                session=locked_session,
                domain_title=domain_title,
                category=rec_data.get('category', ''),
                match_percentage=rec_data.get('match_percentage', 0),
                key_interests=rec_data.get('key_interests', []),
                sub_domains=rec_data.get('sub_domains', []),
                related_subjects=rec_data.get('related_subjects', []),
                description=rec_data.get('description', predefined_domains[domain_title]),
                why_recommended=rec_data.get('why_recommended', ''),
                exploration_activities=rec_data.get('exploration_activities', []),
                potential_careers=rec_data.get('potential_careers', []),
                rank=idx + 1
            )
            recommendations.append(rec)
        
        # Save token usage from recommendations generation
        self._save_token_usage(locked_session, token_usage)
        
        return recommendations

    def get_recommendations(self, session: DomainSession) -> List[DomainRecommendation]:
        """Get stored recommendations for a session"""
        return list(DomainRecommendation.objects.filter(session=session).order_by('rank'))

    def generate_final_report(self, session: DomainSession) -> Dict[str, Any]:
        """
        Generate the final comprehensive report for a Stream & Subject Selection session.
        Includes student snapshot, interests, strengths, RIASEC analysis, and domain recommendations.
        """
        try:
            # Get conversation messages
            messages = self.get_session_messages(session)
            
            # Get user profile data
            user_profile = get_user_profile_data(session.user)
            
            # Get existing recommendations
            from .serializers import DomainRecommendationSerializer
            recommendations = self.get_recommendations(session)
            rec_data = DomainRecommendationSerializer(recommendations, many=True).data
            
            # Generate report via LangChain service
            token_usage = {}
            user_name = get_user_display_name(None, session.user, 'Student')
            report = self.langchain_service.generate_final_report(
                messages=messages,
                recommendations=rec_data,
                user_profile=user_profile,
                user_name=user_name,
                token_usage=token_usage
            )
            
            # Save token usage from report generation
            self._save_token_usage(session, token_usage)
            
            return report
        
        except Exception as e:
            print(f"Error generating final report: {e}")
            return {
                "report_json": {},
                "report_html": "<p>Error generating report. Please try again.</p>",
                "student_name": get_user_display_name(None, session.user, "Student"),
                "generated_at": datetime.now().isoformat()
            }

    def get_results_summary(self, session: DomainSession) -> Dict[str, Any]:
        """
        Get a summary of results after conversation completion.
        Returns stored recommendations from the database - no LLM calls.
        If no recommendations exist, generates them first.
        """
        try:
            # Get user profile data
            user_profile = get_user_profile_data(session.user)
            
            # Get stored recommendations from database
            recommendations = DomainRecommendation.objects.filter(session=session).order_by('rank')
            
            # If no recommendations exist, generate them
            if not recommendations.exists():
                recommendations = self.generate_recommendations(session)
            
            # Serialize recommendations
            from .serializers import DomainRecommendationSerializer
            user_name = get_user_display_name(None, session.user, 'Student')
            rec_data = DomainRecommendationSerializer(recommendations, many=True).data
            
            # Extract interests from stored recommendations
            all_interests = []
            
            for rec in recommendations:
                # Collect unique interests from all recommendations
                all_interests.extend(rec.key_interests)
            
            # Remove duplicates from interests
            unique_interests = list(dict.fromkeys(all_interests))
            
            # RIASEC scores disabled - may be re-enabled later
            # all_riasec = session.riasec_scores or {}
            # top_dimensions = sorted(all_riasec.items(), key=lambda x: x[1], reverse=True)[:2] if all_riasec else []
            # top_dimensions = [dim[0] for dim in top_dimensions]
            
            results = {
                'session_id': session.session_id,
                'student_name': user_name,
                'current_step': session.current_step,
                'total_steps': session.total_steps,
                'interests_identified': unique_interests[:10],  # Top 10 interests
                'strengths_identified': [],  # Disabled - was duplicating interests
                # RIASEC fields disabled - may be re-enabled later
                # 'riasec_scores': all_riasec,
                # 'top_dimensions': top_dimensions,
                'primary_domains': [r for r in rec_data if r.get('rank', 0) <= 2],
                'secondary_domains': [r for r in rec_data if 2 < r.get('rank', 0) <= 5],
                'completion_percentage': int((session.current_step / session.total_steps) * 100)
            }
            
            return results
        
        except Exception as e:
            print(f"Error getting results summary: {e}")
            return {
                'session_id': session.session_id,
                'student_name': get_user_display_name(None, session.user, 'Student'),
                'error': str(e)
            }

    def get_conversation_transcript(self, session: DomainSession) -> Dict[str, Any]:
        """
        Generate a formatted transcript of the conversation.
        """
        try:
            messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(session.user)
            user_name = get_user_display_name(None, session.user, 'Student')
            
            # Pair bot questions with student responses
            transcript_messages = []
            for i in range(0, len(messages) - 1, 2):
                if i < len(messages) and i + 1 < len(messages):
                    bot_msg = messages[i]
                    user_msg = messages[i + 1]
                    
                    if bot_msg.get('type') == MessageType.BOT and user_msg.get('type') == MessageType.USER:
                        # Use question_type for phase (riasec, deepdive, or general)
                        phase = bot_msg.get('question_type', 'general')
                        question_num = (i // 2) + 1
                        
                        transcript_messages.append({
                            'question_number': question_num,
                            'phase': phase,
                            'bot_question': bot_msg.get('content', ''),
                            'student_response': user_msg.get('content', ''),
                            'timestamp': user_msg.get('timestamp')
                        })

            # Include the final unpaired bot message (concluding message) if present
            concluding_message = None
            if len(messages) % 2 == 1:
                last_msg = messages[-1]
                if last_msg.get('type') == MessageType.BOT:
                    concluding_message = last_msg.get('content', '')

            transcript = {
                'session_id': session.session_id,
                'student_name': user_name,
                'started_at': session.created_at.isoformat(),
                'completed_at': session.updated_at.isoformat() if session.updated_at else None,
                'total_questions': len(transcript_messages),
                'messages': transcript_messages,
                'concluding_message': concluding_message,
            }
            
            return transcript
        
        except Exception as e:
            print(f"Error generating transcript: {e}")
            return {
                'session_id': session.session_id,
                'student_name': get_user_display_name(None, session.user, 'Student'),
                'error': str(e)
            }

    def generate_transcript_file(self, session: DomainSession) -> str:
        """
        Generate a formatted text transcript that can be downloaded.
        """
        try:
            transcript = self.get_conversation_transcript(session)
            
            # Build text transcript
            lines = []
            lines.append("=" * 80)
            lines.append(f"Stream & Subject Selection SESSION TRANSCRIPT")
            lines.append(f"Student: {transcript.get('student_name', 'Student')}")
            lines.append(f"Session ID: {transcript.get('session_id', '')}")
            lines.append(f"Started: {transcript.get('started_at', '')}")
            lines.append(f"Completed: {transcript.get('completed_at', '')}")
            lines.append(f"Total Questions: {transcript.get('total_questions', 0)}")
            lines.append("=" * 80)
            lines.append("")
            
            for msg in transcript.get('messages', []):
                lines.append(f"Question {msg.get('question_number', 0)} - {msg.get('phase', 'Unknown').upper()}")
                lines.append("-" * 80)
                lines.append(f"AI Coach:")
                lines.append(f"  {msg.get('bot_question', '')}")
                lines.append("")
                lines.append(f"Student Response:")
                lines.append(f"  {msg.get('student_response', '')}")
                lines.append("")
                lines.append("")
            
            # Concluding message from the AI Coach
            if transcript.get('concluding_message'):
                lines.append("-" * 80)
                lines.append(f"AI Coach (Concluding):")
                lines.append(f"  {transcript['concluding_message']}")
                lines.append("")

            lines.append("=" * 80)
            lines.append(f"End of Transcript")
            lines.append("=" * 80)
            
            return "\n".join(lines)
        
        except Exception as e:
            print(f"Error generating transcript file: {e}")
            return f"Error generating transcript: {str(e)}"

    def get_debug_info(self, session: DomainSession) -> Dict[str, Any]:
        """
        Get debugging information for the session including system prompts, model info, and user context.
        """
        try:
            # Get user profile data
            user_profile = get_user_profile_data(session.user)
            user_profile_context = format_user_profile_context(user_profile, user_name=get_user_display_name(None, session.user, ''))
            
            # Get model information from langchain service
            llm = self.langchain_service.llm
            recommendations_llm = self.langchain_service.recommendations_llm
            
            # Extract model details
            model_info = {
                'provider': 'azure',
                'main_llm': {
                    'type': type(llm).__name__,
                    'model': getattr(llm, 'model_name', getattr(llm, 'model', 'unknown')),
                    'temperature': getattr(llm, 'temperature', None),
                    'max_tokens': getattr(llm, 'max_tokens', None),
                },
                'recommendations_llm': {
                    'type': type(recommendations_llm).__name__,
                    'model': getattr(recommendations_llm, 'model_name', getattr(recommendations_llm, 'model', 'unknown')),
                    'temperature': getattr(recommendations_llm, 'temperature', None),
                    'max_tokens': getattr(recommendations_llm, 'max_tokens', None),
                }
            }
            
            # Get prompts
            from .prompts import DEEPDIVE_QUESTION_GENERATION_PROMPT, RECOMMENDATIONS_SYSTEM_PROMPT
            
            return {
                'session_id': session.session_id,
                'current_phase': session.current_phase,
                'model_info': model_info,
                'system_prompts': {
                    'deepdive_question_prompt': DEEPDIVE_QUESTION_GENERATION_PROMPT,
                    'recommendations_prompt': RECOMMENDATIONS_SYSTEM_PROMPT,
                },
                'user_profile_context': user_profile_context,
                'session_state': {
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'riasec_completed': session.riasec_completed,
                    'deepdive_completed': session.deepdive_completed,
                    'riasec_questions_count': session.riasec_questions_count,
                    'deepdive_questions_count': session.deepdive_questions_count,
                },
                'token_usage': session.token_usage or {},
            }
        
        except Exception as e:
            print(f"Error getting debug info: {e}")
            return {
                'error': str(e),
                'session_id': session.session_id
            }


# Create singleton instance for use throughout the application
domain_discovery_service = DomainDiscoveryService()
