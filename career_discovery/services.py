"""
Career & Degree Selection Service Layer
Handles session management, message processing, and integrates with LangChain AI service
"""
import json
import uuid
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from .models import CareerSession, CareerMessage, CareerRecommendation
from .langchain_service import career_langchain_service
from .constants import DOMAIN_CAREER_MAPPING, CROSS_DOMAIN_CAREERS
from apps.profiles.models import UserProfile
from domain_discovery.models import DomainMessage, DomainRecommendation
from utils.profile_helpers import get_user_profile_data
from utils.user_helpers import get_user_display_name
from apps.accounts.models import ActivityLog
from asgiref.sync import sync_to_async

# Static intro message — no LLM call needed
CAREER_INTRO_MESSAGE = (
    "Hello, I'm Ivy\u2014your career and education guide. "
    "In this module, I'll help you explore which career paths and degrees fit you best.\n\n"
    "Please answer honestly, ask if anything is unclear, and for multiple-choice questions just reply with A, B, or C.\n\n"
    "Remember, there are no right or wrong answers\u2014just be yourself. Shall we get started?"
)


def build_career_intro_message(user_name: str, primary_domain: str, secondary_domain: str = None, language: str = 'en') -> str:
    """Build a personalized intro message with the user's name and selected domains."""
    if language == 'hi':
        if secondary_domain:
            return (
                f"नमस्ते {user_name}, मुझे आपके करियर विकल्पों को तलाशने में आपकी मदद करने में बहुत खुशी हो रही है। "
                f"आपने 1. {primary_domain} और 2. {secondary_domain} को अपने डोमेन विकल्पों के रूप में चुना है। "
                f"क्या हम शुरू करें?"
            )
        return (
            f"नमस्ते {user_name}, मुझे आपके करियर विकल्पों को तलाशने में आपकी मदद करने में बहुत खुशी हो रही है। "
            f"आपने {primary_domain} को अपने डोमेन विकल्प के रूप में चुना है। "
            f"क्या हम शुरू करें?"
        )
    if secondary_domain:
        return (
            f"Hi {user_name}, I am excited to help you explore your career choices. "
            f"You have selected 1. {primary_domain} & 2. {secondary_domain} as domain choices. "
            f"Shall we get started?"
        )
    return (
        f"Hi {user_name}, I am excited to help you explore your career choices. "
        f"You have selected {primary_domain} as your domain choice. "
        f"Shall we get started?"
    )


class CareerDiscoveryService:
    """
    Service class for managing Career & Degree Selection sessions and conversations.
    Integrates with LangChain-based AI service for question generation and recommendations.
    """

    def __init__(self):
        self.langchain_service = career_langchain_service
        self.total_steps = 18  # 2 Domain Motivation + 16 Career Explorer (domain selection moved to pre-session)

    def get_domain_discovery_context(self, session: CareerSession) -> Dict[str, Any]:
        """Get Stream & Subject Selection session context (Q&A + recommendations)"""
        if not session.domain_session:
            return {}
        
        try:
            domain_session = session.domain_session
            
            # Get all Stream & Subject Selection messages
            domain_messages = DomainMessage.objects.filter(
                session=domain_session
            ).order_by('timestamp')
            
            messages = [
                {
                    'type': msg.type,
                    'content': msg.content,
                    'question_type': msg.question_type,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in domain_messages
            ]
            
            # Get domain recommendations (top 5)
            recommendations = DomainRecommendation.objects.filter(
                session=domain_session
            ).order_by('rank', '-match_percentage')[:5]
            
            domain_results = [
                {
                    'title': rec.domain_title,
                    'description': rec.description,
                    'match_percentage': rec.match_percentage,
                    'explanation': rec.why_recommended,
                    'category': rec.category,
                    'key_interests': rec.key_interests
                }
                for rec in recommendations
            ]
            
            return {
                'session_id': domain_session.session_id,
                'messages': messages,
                'recommendations': domain_results,
                'completed_at': domain_session.updated_at.isoformat() if domain_session.updated_at else None
            }
        except Exception as e:
            print(f"Error fetching Stream & Subject Selection context: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _save_token_usage(self, session: CareerSession, new_usage: Dict):
        """Merge new token usage into session's existing token_usage and save."""
        if new_usage is None or not new_usage.get("categories"):
            return
        existing = session.token_usage or {}
        
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
        
        existing["total_input_tokens"] += new_usage.get("total_input_tokens", 0)
        existing["total_output_tokens"] += new_usage.get("total_output_tokens", 0)
        existing["total_tokens"] += new_usage.get("total_tokens", 0)
        existing["total_llm_calls"] += new_usage.get("total_llm_calls", 0)
        existing["total_cache_read_tokens"] += new_usage.get("total_cache_read_tokens", 0)
        existing["total_cache_creation_tokens"] += new_usage.get("total_cache_creation_tokens", 0)
        existing["total_reasoning_tokens"] += new_usage.get("total_reasoning_tokens", 0)
        
        session.token_usage = existing
        session.save(update_fields=['token_usage'])

    def create_session(self, user, domain_session=None, primary_domain=None, secondary_domain=None, degree_preference: str = 'career_only') -> CareerSession:
        """Create a new Career & Degree Selection session for a user.
        
        Domain choices (primary_domain, secondary_domain) are selected by the user
        on the landing page before starting the session.
        """
        # Build domain_choices metadata upfront
        career_refs: list = list(DOMAIN_CAREER_MAPPING.get(primary_domain, []))
        if secondary_domain:
            career_refs += [
                c for c in DOMAIN_CAREER_MAPPING.get(secondary_domain, [])
                if c not in career_refs
            ]

        hybrid_refs: list = []
        if secondary_domain:
            for domain in (primary_domain, secondary_domain):
                other = secondary_domain if domain == primary_domain else primary_domain
                for entry in CROSS_DOMAIN_CAREERS.get(domain, []):
                    if entry.get('secondary_domain') == other:
                        name = entry.get('career', '')
                        if name and name not in hybrid_refs:
                            hybrid_refs.append(name)

        domain_choices = {
            'primary_domain': primary_domain,
            'secondary_domain': secondary_domain,
            'career_references': career_refs,
            'hybrid_career_references': hybrid_refs,
        }

        # Create new session
        session_id = f"career_{uuid.uuid4().hex[:12]}"
        # Validate degree_preference value
        valid_preferences = ('career_only', 'career_and_postgrad')
        if degree_preference not in valid_preferences:
            degree_preference = 'career_only'
        session = CareerSession.objects.create(
            user=user,
            session_id=session_id,
            domain_session=domain_session,
            current_step=0,
            total_steps=self.total_steps,
            metadata={'domain_choices': domain_choices, 'degree_preference': degree_preference},
        )

        ActivityLog.log(
            user=user,
            event_type="module_start",
            description=f"Started Career & Degree Selection session ({session_id})",
            metadata={"module": "career_discovery", "session_id": session_id}
        )

        # Get user profile data for AI context
        user_profile = get_user_profile_data(user)
        
        # Get Stream & Subject Selection context
        domain_context = self.get_domain_discovery_context(session)
        domain_context['domain_choices'] = domain_choices
        
        print("domain_context in create_session:", domain_context)
        
        # Log domain context for debugging
        if domain_context and domain_context.get('recommendations'):
            print(f"[SUCCESS] Domain context loaded with {len(domain_context.get('recommendations', []))} recommendations")
            for i, rec in enumerate(domain_context.get('recommendations', []), 1):
                print(f"  {i}. {rec.get('title')} ({rec.get('match_percentage')}%)")
        else:
            print("[WARNING] No domain recommendations found for this session")
        
        # Generate session notes in background - not needed for the first question
        # Notes will be ready by the time the student responds to Q1
        session_id_for_notes = session.session_id
        def _generate_notes_background():
            try:
                notes_token_usage = {}
                notes = self.langchain_service.generate_session_notes(
                    user_profile=user_profile,
                    domain_context=domain_context,
                    token_usage=notes_token_usage
                )
                if notes:
                    # Use a fresh DB query to avoid stale state
                    from .models import CareerSession as CS
                    s = CS.objects.get(session_id=session_id_for_notes)
                    s.notes = notes
                    s.save(update_fields=['notes'])
                    self._save_token_usage(s, notes_token_usage)
                    print(f"[SUCCESS] Session notes saved in background ({len(notes)} chars)")
            except Exception as e:
                print(f"[WARNING] Background session notes generation failed: {e}")
                import traceback
                traceback.print_exc()
        
        notes_thread = threading.Thread(target=_generate_notes_background, daemon=True)
        notes_thread.start()
        
        # Get language from settings
        from utils.user_helpers import get_user_instance
        user_instance = get_user_instance(user)
        language = 'en'
        if user_instance and hasattr(user_instance, 'settings') and isinstance(user_instance.settings, dict):
            language = user_instance.settings.get('voice_language', 'en').lower()

        # Dynamic intro message with user name and selected domains
        user_name = get_user_display_name(None, user, 'there')
        intro_message = build_career_intro_message(
            user_name=user_name,
            primary_domain=primary_domain,
            secondary_domain=secondary_domain,
            language=language,
        )
        CareerMessage.objects.create(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type='bot',
            content=intro_message,
            step_number=0
        )

        return session

    def get_active_session(self, user) -> Optional[CareerSession]:
        """Get the active (non-completed) Career & Degree Selection session for a user"""
        session = CareerSession.objects.filter(
            user=user, is_active=True
        ).order_by('-created_at').first()
        if session and not session.is_completed:
            return session
        return None

    def get_session_by_id(self, session_id: str) -> Optional[CareerSession]:
        """Get a session by its ID"""
        try:
            return CareerSession.objects.get(session_id=session_id)
        except CareerSession.DoesNotExist:
            return None

    def get_session_messages(self, session: CareerSession) -> List[Dict[str, Any]]:
        """Get all messages for a session as a list of dicts"""
        messages = CareerMessage.objects.filter(session=session).order_by('timestamp')
        return [
            {
                'message_id': msg.message_id,
                'type': msg.type,
                'content': msg.content,
                'step_number': msg.step_number,
                'phase': msg.phase,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in messages
        ]

    async def process_message_stream(self, session: CareerSession, user_message: str):
        """Streaming version of process_message that yields chunks."""
        # Get language from settings
        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        PRE_FINAL_QUESTION_HI = (
            "आज आपसे बात करके बहुत अच्छा लगा! इससे पहले कि हम अपना सत्र समाप्त करें, क्या कोई आखिरी सवाल है जो आप पूछना चाहते हैं?"
        )
        CONCLUSION_MSG_HI = (
            "मेरे साथ यह सब साझा करने के लिए धन्यवाद! 🎉 मैंने आपकी रुचियों और शक्तियों के बारे में बहुत कुछ सीखा है। मुझे हर चीज़ का विश्लेषण करने दें और आपकी व्यक्तिगत करियर सिफारिशें तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"
        )

        await sync_to_async(ActivityLog.log)(
            user=session.user,
            event_type="llm_interaction",
            description=f"User sent message in Career & Degree Selection (stream)",
            metadata={
                "module": "career_discovery",
                "session_id": session.session_id,
                "type": "user",
                "content": user_message[:200]
            }
        )

        # Increment step
        current_step = int(session.current_step)
        new_step = current_step + 1
        session.current_step = new_step

        PRE_FINAL_QUESTION = PRE_FINAL_QUESTION_HI if language == 'hi' else (
            "It was fantastic talking to you today! Is there one final question "
            "you wish to ask before we close our session?"
        )

        CONCLUSION_MSG = CONCLUSION_MSG_HI if language == 'hi' else (
            "Thank you for sharing all of that with me! 🎉 I've learned so much about "
            "your interests and strengths. Let me analyze everything and prepare your "
            "personalized career recommendations. Head over to see your results!"
        )

        metadata = session.metadata or {}
        bot_response_full = ""
        is_complete = False

        # ── Pre-final answer handling ────────────────────────────
        if metadata.get('pre_final_asked') and not metadata.get('pre_final_answered'):
            metadata['pre_final_answered'] = True
            session.metadata = metadata
            is_complete = True
            bot_response_full = await sync_to_async(self._handle_pre_final_response)(session, user_message)
            yield f"data: {json.dumps({'delta': bot_response_full, 'is_complete': True})}\n\n"
        else:
            is_complete = new_step >= self.total_steps

            if is_complete and not metadata.get('pre_final_asked'):
                is_complete = False
                session.total_steps = new_step + 1
                metadata['pre_final_asked'] = True
                session.metadata = metadata
                bot_response_full = PRE_FINAL_QUESTION
                yield f"data: {json.dumps({'delta': bot_response_full, 'is_complete': False})}\n\n"
            elif is_complete:
                bot_response_full = CONCLUSION_MSG
                yield f"data: {json.dumps({'delta': bot_response_full, 'is_complete': True})}\n\n"
            else:
                # Actual LLM stream
                all_messages = await sync_to_async(self.get_session_messages)(session)
                user_profile = await sync_to_async(get_user_profile_data)(session.user)
                domain_context = await sync_to_async(self.get_domain_discovery_context)(session)
                domain_context['domain_choices'] = session.metadata.get('domain_choices', {})
                token_usage = {}

                user_name = await sync_to_async(get_user_display_name)(None, session.user, 'there')

                # Use astream_question for true async streaming
                async for chunk in self.langchain_service.astream_question(
                    step=new_step,
                    user_response=user_message,
                    messages=all_messages,
                    user_profile=user_profile,
                    user_name=user_name,
                    domain_context=domain_context,
                    session_notes=session.notes or "",
                    token_usage=token_usage,
                    language=language,
                ):
                    bot_response_full += chunk
                    yield f"data: {json.dumps({'delta': chunk, 'is_complete': False})}\n\n"

                
                # Signal completion
                yield f"data: {json.dumps({'delta': '', 'is_complete': is_complete})}\n\n"

        await sync_to_async(session.save)()

        # Save full bot response to DB
        await sync_to_async(CareerMessage.objects.create)(
            session=session,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            type='bot',
            content=bot_response_full,
            step_number=new_step
        )

        if is_complete:
            await sync_to_async(ActivityLog.log)(
                user=session.user,
                event_type="module_complete",
                description=f"Completed Career & Degree Selection session ({session.session_id})",
                metadata={"module": "career_discovery", "session_id": session.session_id}
            )


    @transaction.atomic
    def process_message(self, session: CareerSession, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and generate the next question or finalize the conversation.
        """
        from asgiref.sync import async_to_sync

        async def _consume_stream():
            resp = ""
            complete = False
            async for chunk_json in self.process_message_stream(session, user_message):
                if chunk_json.startswith("data: "):
                    try:
                        data = json.loads(chunk_json[6:].strip())
                        resp += data.get("delta", "")
                        complete = data.get("is_complete", False)
                    except json.JSONDecodeError:
                        continue
            return resp, complete

        # Consume the stream to get the full response for the sync API
        bot_response, is_complete = async_to_sync(_consume_stream)()

        # Refresh token_usage from DB to include latest
        session.refresh_from_db(fields=['token_usage', 'current_step'])

        return {
            'session_id': session.session_id,
            'user_message': user_message,
            'bot_response': bot_response,
            'current_step': session.current_step,
            'total_steps': self.total_steps,
            'is_complete': is_complete,
            'token_usage': session.token_usage or {}
        }

    def end_session(self, session: CareerSession) -> None:
        """End an active session"""
        session.is_active = False
        session.save(update_fields=['is_active'])

    def _handle_pre_final_response(self, session: CareerSession, user_message: str) -> str:
        """Handle the user's response to the pre-final question.

        If the user asked a question, answer it briefly then append the
        conclusion message.  Otherwise just return the conclusion message.
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        # Get language from settings
        language = 'en'
        if session.user and hasattr(session.user, 'settings') and isinstance(session.user.settings, dict):
            language = session.user.settings.get('voice_language', 'en').lower()

        CONCLUSION_MSG_HI = (
            "मेरे साथ यह सब साझा करने के लिए धन्यवाद! 🎉 मैंने आपकी रुचियों और शक्तियों के बारे में बहुत कुछ सीखा है। मुझे हर चीज़ का विश्लेषण करने दें और आपकी व्यक्तिगत करियर सिफारिशें तैयार करने दें। अपने परिणाम देखने के लिए आगे बढ़ें!"
        )

        CONCLUSION_MSG = CONCLUSION_MSG_HI if language == 'hi' else (
            "Thank you for sharing all of that with me! 🎉 I've learned so much about "
            "your interests and strengths. Let me analyze everything and prepare your "
            "personalized career recommendations. Head over to see your results!"
        )

        try:
            # Build conversation history so the LLM has full context to answer
            all_messages = self.get_session_messages(session)
            user_profile = get_user_profile_data(session.user)

            from utils.profile_formatting import format_user_profile_context
            from utils.user_helpers import get_user_display_name as _get_name
            profile_context = format_user_profile_context(user_profile, user_name=_get_name(None, session.user, ''))

            system_prompt = (
                "You are a warm, supportive career counselor. The student was asked "
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
                system_prompt += (
                    "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. "
                    "Do NOT use English or Hinglish. If they ask a question, answer it warmly and concisely in Hindi, "
                    "then end with the exact closing line: " + CONCLUSION_MSG + "]"
                )

            llm_messages = [
                SystemMessage(content=system_prompt),
            ]

            # Add conversation history
            for msg in all_messages:
                content = msg.get('content', '')
                msg_type = msg.get('type')
                if msg_type == 'user':
                    llm_messages.append(HumanMessage(content=content))
                elif msg_type == 'bot':
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
            import logging
            logging.getLogger(__name__).error(f"Error handling pre-final response: {e}")
            return CONCLUSION_MSG

    @transaction.atomic
    def generate_recommendations(self, session: CareerSession) -> Dict[str, Any]:
        """
        Generate career recommendations based on the conversation.
        Stores recommendations in the database and returns them.
        """
        # Clear any existing recommendations for this session
        CareerRecommendation.objects.filter(session=session).delete()

        # Get all messages
        all_messages = self.get_session_messages(session)
        
        # Get user profile data for AI context
        user_profile = get_user_profile_data(session.user)
        
        # Get Stream & Subject Selection context
        domain_context = self.get_domain_discovery_context(session)
        domain_context['domain_choices'] = session.metadata.get('domain_choices', {})

        # Derive degree filter based on student's academic level and their chosen preference
        # Academic level comes from the user's profile educational.academicLevel field
        degree_filter = 'all'  # Default: show all degree types
        academic_level = ''
        try:
            profile_data = user_profile.get('profile_data', {}) if isinstance(user_profile, dict) else {}
            educational = profile_data.get('educational', {})
            if not isinstance(educational, dict):
                educational = {}
            academic_level = (
                educational.get('academicLevel', '')
                or user_profile.get('academicLevel', '')
                or ''
            ).strip()
        except Exception:
            academic_level = ''

        HIGH_SCHOOL_LEVEL = 'High School (8th\u201312th grade)'
        if academic_level == HIGH_SCHOOL_LEVEL:
            # High school students → ONLY show UG degrees in recommendations
            degree_filter = 'ug_only'
        else:
            # Undergrad / PG / Working Professional → respect their stated preference
            degree_pref = session.metadata.get('degree_preference', 'career_only')
            if degree_pref == 'career_and_postgrad':
                degree_filter = 'career_and_postgrad'
            else:
                degree_filter = 'career_only'  # default: no postgrad

        print(f"[DEGREE FILTER] academic_level='{academic_level}' | degree_preference='{session.metadata.get('degree_preference', 'career_only')}' | degree_filter='{degree_filter}'")

        # Token usage tracker for recommendations
        token_usage = {}

        # Generate recommendations via LangChain service
        recommendations_data = self.langchain_service.generate_recommendations(
            all_messages, 
            user_profile,
            domain_context,
            token_usage=token_usage,
            degree_filter=degree_filter,
        )

        # Post-process: for ug_only, strip out any non-UG degrees the AI may have included
        UG_KEYWORDS = ('b.', 'ba ', 'bs ', 'btech', 'b.tech', 'bsc', 'b.sc', 'bba', 'b.a', 'b.s', 'be ', 'b.e', 'bachelor', 'undergraduate', 'ug ')
        PG_KEYWORDS = ('m.', 'mba', 'ms ', 'm.s', 'ma ', 'm.a', 'mtech', 'm.tech', 'msc', 'm.sc', 'master', 'phd', 'ph.d', 'doctorate', 'postgrad', 'pg ')
        if degree_filter == 'ug_only':
            for rec_data in recommendations_data:
                filtered_degrees = []
                for deg in rec_data.get('degrees', []):
                    deg_name = (deg.get('degree', '') if isinstance(deg, dict) else str(deg)).lower()
                    is_pg = any(kw in deg_name for kw in PG_KEYWORDS)
                    if not is_pg:
                        filtered_degrees.append(deg)
                rec_data['degrees'] = filtered_degrees if filtered_degrees else rec_data.get('degrees', [])
        elif degree_filter == 'career_only':
            # Remove postgrad degrees — only keep UG-level degrees
            for rec_data in recommendations_data:
                filtered_degrees = []
                for deg in rec_data.get('degrees', []):
                    deg_name = (deg.get('degree', '') if isinstance(deg, dict) else str(deg)).lower()
                    is_pg = any(kw in deg_name for kw in PG_KEYWORDS)
                    if not is_pg:
                        filtered_degrees.append(deg)
                rec_data['degrees'] = filtered_degrees if filtered_degrees else rec_data.get('degrees', [])


        # Store recommendations in database
        from .serializers import CareerRecommendationSerializer
        stored_recommendations = []
        for i, rec_data in enumerate(recommendations_data):
            rec = CareerRecommendation.objects.create(
                session=session,
                career_title=rec_data.get('career_title', 'Unknown Career'),
                match_percentage=rec_data.get('match_percentage', 0),
                required_skills=rec_data.get('required_skills', []),
                next_steps=rec_data.get('next_steps', []),
                description=rec_data.get('description', ''),
                why_recommended=rec_data.get('why_recommended', ''),
                alignment_points=rec_data.get('alignment_points', []),
                related_subjects=rec_data.get('related_subjects', []),
                degrees=rec_data.get('degrees', []),
                day_in_life=rec_data.get('day_in_life', ''),
                pros_and_cons=rec_data.get('pros_and_cons', {}),
                work_life_balance=rec_data.get('work_life_balance', ''),
                feasibility=rec_data.get('feasibility', {}),
                skill_gaps=rec_data.get('skill_gaps', []),
                rank=i + 1
            )
            stored_recommendations.append(rec)
        
        # Save token usage from recommendations generation
        self._save_token_usage(session, token_usage)
        
        # Serialize all recommendations at once
        return CareerRecommendationSerializer(stored_recommendations, many=True).data

    def get_stored_recommendations(self, session: CareerSession) -> List[Dict[str, Any]]:
        """Get previously stored recommendations for a session"""
        recommendations = CareerRecommendation.objects.filter(session=session).order_by('rank')
        return [
            {
                'id': rec.id,
                'career_title': rec.career_title,
                'match_percentage': rec.match_percentage,
                'required_skills': rec.required_skills,
                'next_steps': rec.next_steps,
                'description': rec.description,
                'why_recommended': rec.why_recommended,
                'alignment_points': rec.alignment_points,
                'related_subjects': rec.related_subjects,
                'degrees': rec.degrees,
                'day_in_life': rec.day_in_life,
                'pros_and_cons': rec.pros_and_cons,
                'work_life_balance': rec.work_life_balance,
                'feasibility': rec.feasibility,
                'skill_gaps': rec.skill_gaps,
                'rank': rec.rank
            } for rec in recommendations
        ]

    def get_conversation_transcript(self, session: CareerSession) -> Dict[str, Any]:
        """Generate a formatted transcript of the conversation."""
        try:
            messages = self.get_session_messages(session)
            user_name = get_user_display_name(None, session.user, 'Student')
            
            # Pair bot questions with student responses
            transcript_messages = []
            for i in range(0, len(messages), 2):
                if i < len(messages) and i + 1 < len(messages):
                    bot_msg = messages[i]
                    user_msg = messages[i + 1]
                    
                    if bot_msg.get('type') == 'bot' and user_msg.get('type') == 'user':
                        question_num = (i // 2) + 1
                        transcript_messages.append({
                            'question_number': question_num,
                            'bot_question': bot_msg.get('content', ''),
                            'student_response': user_msg.get('content', ''),
                            'timestamp': user_msg.get('timestamp')
                        })

            # Check for trailing bot message (conclusion)
            concluding_message = None
            if len(messages) % 2 == 1:
                last_msg = messages[-1]
                if last_msg.get('type') == 'bot':
                    concluding_message = last_msg.get('content', '')

            return {
                'session_id': session.session_id,
                'student_name': user_name,
                'started_at': session.created_at.isoformat(),
                'completed_at': session.updated_at.isoformat() if session.updated_at else None,
                'total_questions': len(transcript_messages),
                'messages': transcript_messages,
                'concluding_message': concluding_message,
            }
        except Exception as e:
            print(f"Error generating transcript: {e}")
            return {
                'session_id': session.session_id,
                'student_name': get_user_display_name(None, session.user, 'Student'),
                'error': str(e)
            }


# Global service instance
career_discovery_service = CareerDiscoveryService()
