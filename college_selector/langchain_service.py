"""
LangChain-based AI Service for College Selector using Azure OpenAI.
"""
import os
import logging
import traceback
from typing import List, Dict, Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from django.conf import settings
from utils.azure_openai import create_azure_chat_openai
from utils.message_constants import MessageType
from utils.profile_formatting import format_user_profile_context

from .prompts import (
    CONVERSATION_SYSTEM_PROMPT,
    RECOMMENDATIONS_SYSTEM_PROMPT,
    CONCLUSION_CHECK_PROMPT,
    COLLEGE_RECOMMENDATION_SESSION_LEARNINGS,
    build_preferences_context,
)

logger = logging.getLogger(__name__)


# ================== Pydantic Output Schemas ==================

class ConversationResponseSchema(BaseModel):
    response: str = Field(description="The counselor's message to the student")
    student_done: bool = Field(description="True if the student has no more questions", default=False)


class DeadlinesSchema(BaseModel):
    early_action: str = Field(description="Early Action deadline", default="")
    early_decision: str = Field(description="Early Decision deadline", default="")
    regular_decision: str = Field(description="Regular Decision deadline", default="")
    rolling: str = Field(description="Rolling admission deadline", default="")


class AcademicRequirementsSchema(BaseModel):
    gpa: str = Field(description="Minimum GPA requirement", default="")
    sat: str = Field(description="SAT score requirement", default="")
    act: str = Field(description="ACT score requirement", default="")


class GlobalRankingSchema(BaseModel):
    qs: str = Field(description="QS World University ranking", default="")
    the: str = Field(description="Times Higher Education ranking", default="")
    usn: str = Field(description="US News ranking", default="")


class CollegeRecommendationSchema(BaseModel):
    university_name: str = Field(description="Full official university name")
    website_url: str = Field(description="Official admissions URL", default="")
    location: str = Field(description="City, State/Province, Country")
    country: str = Field(description="Country name")
    deadlines: DeadlinesSchema = Field(description="EA/ED/RD/Rolling deadlines", default_factory=DeadlinesSchema)
    degree_and_major: str = Field(description="Specific program name", default="")
    tuition_fees: str = Field(description="Annual tuition with USD equivalent", default="")
    cost_of_living: str = Field(description="Monthly cost of living estimate", default="")
    scholarships: List[str] = Field(description="Available scholarship types", default_factory=list)
    academic_requirements: AcademicRequirementsSchema = Field(description="GPA, SAT, ACT requirements", default_factory=AcademicRequirementsSchema)
    additional_requirements: List[str] = Field(description="SOPs, LORs, Portfolio etc.", default_factory=list)
    university_type: str = Field(description="Public/Private/Research", default="")
    global_ranking: GlobalRankingSchema = Field(description="QS/THE/USN rankings", default_factory=GlobalRankingSchema)
    acceptance_rate: str = Field(description="Acceptance rate percentage", default="")
    application_fee: str = Field(description="Application fee", default="")
    tests_required: List[str] = Field(description="Required standardized tests", default_factory=list)
    post_study_work_visa: str = Field(description="Post-study visa info", default="")
    employment_rate: str = Field(description="Post-grad employment rate", default="")
    language: str = Field(description="Instruction language", default="English")
    campus_type: str = Field(description="Urban/Suburban/Rural", default="")
    intl_student_support: str = Field(description="International student services", default="")
    fit_category: str = Field(description="reach/match/safe", default="match")
    fit_reasoning: str = Field(
        description="2-3 sentence explanation of WHY this college is categorized as reach/match/safe based on the student's specific academic profile (GPA, test scores) compared to the college's admission statistics (acceptance rate, average admitted GPA/SAT/ACT)",
        default=""
    )
    suggested_deadline: str = Field(
        description="The recommended application round and date for this student to apply (e.g. 'Early Decision — Nov 1, 2026' or 'Regular Decision — Jan 15, 2027'). Choose the best strategy based on the student's fit category: reach schools should apply ED/EA for best chances, safe schools can use RD.",
        default=""
    )
    match_percentage: int = Field(description="0-100 match score", ge=0, le=100, default=50)
    description: str = Field(description="Why this college is recommended", default="")


class CollegeRecommendationsOutput(BaseModel):
    recommendations: List[CollegeRecommendationSchema] = Field(
        description="List of 20 college recommendations",
        min_length=1,
        max_length=20,
    )


# ================== Service Class ==================

class CollegeSelectorLangChainService:
    """LangChain-based service for College Selector conversations and recommendations."""

    def __init__(self):
        self._llm = None
        self._recommendations_llm = None
        self._is_initialized = False

    def _initialize_llm(self):
        if self._is_initialized:
            return
        try:
            reasoning_effort = os.getenv("REASONING_EFFORT", None)
            self._llm = create_azure_chat_openai(temperature=0.7, max_tokens=800, reasoning_effort=reasoning_effort)
            self._recommendations_llm = create_azure_chat_openai(temperature=0.7, max_tokens=16000, reasoning_effort=reasoning_effort)
            self._is_initialized = True
            logger.info("College Selector LangChain Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize College Selector LangChain Service: {e}")
            raise

    @property
    def llm(self):
        if not self._is_initialized:
            self._initialize_llm()
        return self._llm

    @property
    def recommendations_llm(self):
        if not self._is_initialized:
            self._initialize_llm()
        return self._recommendations_llm

    def _extract_token_usage(self, raw_response) -> Dict[str, int]:
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_token_details": {"cache_read": 0, "cache_creation": 0},
            "output_token_details": {"reasoning": 0},
        }
        try:
            if hasattr(raw_response, 'usage_metadata') and raw_response.usage_metadata:
                meta = raw_response.usage_metadata
                usage["input_tokens"] = getattr(meta, 'input_tokens', 0) or (meta.get('input_tokens', 0) if isinstance(meta, dict) else 0)
                usage["output_tokens"] = getattr(meta, 'output_tokens', 0) or (meta.get('output_tokens', 0) if isinstance(meta, dict) else 0)
                usage["total_tokens"] = getattr(meta, 'total_tokens', 0) or (meta.get('total_tokens', 0) if isinstance(meta, dict) else 0)
                if not usage["total_tokens"]:
                    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]

                # Extract cached/detailed token breakdowns
                input_details = getattr(meta, 'input_token_details', None) or (meta.get('input_token_details') if isinstance(meta, dict) else None)
                if input_details:
                    if isinstance(input_details, dict):
                        usage["input_token_details"]["cache_read"] = input_details.get('cache_read', 0) or 0
                        usage["input_token_details"]["cache_creation"] = input_details.get('cache_creation', 0) or 0
                    else:
                        usage["input_token_details"]["cache_read"] = getattr(input_details, 'cache_read', 0) or 0
                        usage["input_token_details"]["cache_creation"] = getattr(input_details, 'cache_creation', 0) or 0

                output_details = getattr(meta, 'output_token_details', None) or (meta.get('output_token_details') if isinstance(meta, dict) else None)
                if output_details:
                    if isinstance(output_details, dict):
                        usage["output_token_details"]["reasoning"] = output_details.get('reasoning', 0) or 0
                    else:
                        usage["output_token_details"]["reasoning"] = getattr(output_details, 'reasoning', 0) or 0
            elif hasattr(raw_response, 'response_metadata'):
                rm = raw_response.response_metadata or {}
                tu = rm.get('token_usage', {})
                usage['input_tokens'] = tu.get('prompt_tokens', 0)
                usage['output_tokens'] = tu.get('completion_tokens', 0)
                usage['total_tokens'] = tu.get('total_tokens', 0)
        except Exception as e:
            logger.warning(f"Failed to extract token usage: {e}")
        return usage

    def track_token_usage(self, token_usage: Dict, category: str, usage: Dict):
        if not usage:
            return
        if "categories" not in token_usage:
            token_usage["categories"] = {}
            token_usage["total_input_tokens"] = 0
            token_usage["total_output_tokens"] = 0
            token_usage["total_tokens"] = 0
            token_usage["total_llm_calls"] = 0
            token_usage["total_cache_read_tokens"] = 0
            token_usage["total_cache_creation_tokens"] = 0
            token_usage["total_reasoning_tokens"] = 0

        if category not in token_usage["categories"]:
            token_usage["categories"][category] = {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_count": 0,
                "cache_read_tokens": 0, "cache_creation_tokens": 0, "reasoning_tokens": 0,
            }

        cat = token_usage["categories"][category]
        cat["input_tokens"] += usage.get("input_tokens", 0)
        cat["output_tokens"] += usage.get("output_tokens", 0)
        cat["total_tokens"] += usage.get("total_tokens", 0)
        cat["call_count"] += 1

        # Cached / detailed token breakdowns
        input_details = usage.get("input_token_details", {})
        output_details = usage.get("output_token_details", {})
        cat["cache_read_tokens"] += input_details.get("cache_read", 0) or 0
        cat["cache_creation_tokens"] += input_details.get("cache_creation", 0) or 0
        cat["reasoning_tokens"] += output_details.get("reasoning", 0) or 0

        token_usage["total_input_tokens"] += usage.get("input_tokens", 0)
        token_usage["total_output_tokens"] += usage.get("output_tokens", 0)
        token_usage["total_tokens"] += usage.get("total_tokens", 0)
        token_usage["total_llm_calls"] += 1
        token_usage["total_cache_read_tokens"] = token_usage.get("total_cache_read_tokens", 0) + (input_details.get("cache_read", 0) or 0)
        token_usage["total_cache_creation_tokens"] = token_usage.get("total_cache_creation_tokens", 0) + (input_details.get("cache_creation", 0) or 0)
        token_usage["total_reasoning_tokens"] = token_usage.get("total_reasoning_tokens", 0) + (output_details.get("reasoning", 0) or 0)

    def generate_response(
        self,
        preferences: dict,
        user_profile: dict,
        messages: List[Dict[str, Any]],
        user_message: str,
        token_usage: Dict = None,
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Generate a conversational response given the student's preferences and message history."""
        if token_usage is None:
            token_usage = {}

        preferences_context = build_preferences_context(preferences)
        profile_context = format_user_profile_context(user_profile)

        system_prompt = CONVERSATION_SYSTEM_PROMPT.format(
            preferences_context=preferences_context,
            profile_context=profile_context,
        )

        if language == 'hi':
            system_prompt += (
                "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. "
                "Do NOT use English or Hinglish. Your response, including greetings, questions, comparison highlights, "
                "and acknowledgments, must be written in clear, warm, and natural Devanagari Hindi text. "
                "When returning the JSON object, ensure the 'response' key contains Hindi text while 'student_done' remains boolean.]"
            )

        langchain_messages = [SystemMessage(content=system_prompt)]
        for msg in messages:
            if msg.get('type') == MessageType.BOT or msg.get('role') == 'assistant':
                langchain_messages.append(AIMessage(content=msg['content']))
            else:
                langchain_messages.append(HumanMessage(content=msg['content']))
        langchain_messages.append(HumanMessage(content=user_message))

        try:
            raw_response = self.llm.invoke(langchain_messages)
            usage = self._extract_token_usage(raw_response)
            self.track_token_usage(token_usage, "conversation", usage)

            content = raw_response.content
            # Handle list-type content (e.g. Azure OpenAI content blocks)
            if isinstance(content, list):
                content = "".join(
                    block if isinstance(block, str) else block.get("text", "")
                    for block in content
                )
            # Try to parse JSON response
            import json
            # Strip markdown code fences if present
            stripped = content.strip()
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                stripped = "\n".join(lines).strip()
            try:
                parsed = json.loads(stripped)
                response_text = parsed.get("response", content)
                # Ensure response is always a string (LLM may nest objects)
                if not isinstance(response_text, str):
                    response_text = str(response_text) if response_text else content
                return {
                    "response": response_text,
                    "student_done": parsed.get("student_done", False),
                    "token_usage": token_usage,
                }
            except (json.JSONDecodeError, TypeError):
                return {
                    "response": content,
                    "student_done": False,
                    "token_usage": token_usage,
                }
        except Exception as e:
            logger.error(f"Error generating college selector response: {e}")
            raise

    def generate_recommendations(
        self,
        preferences: dict,
        user_profile: dict,
        messages: List[Dict[str, Any]],
        token_usage: Dict = None,
    ) -> Dict[str, Any]:
        """Generate 20 college recommendations based on preferences and conversation."""
        if token_usage is None:
            token_usage = {}

        preferences_context = build_preferences_context(preferences)
        profile_context = format_user_profile_context(user_profile)
        countries = ", ".join(preferences.get("countries", []))

        conversation_lines = []
        for msg in messages:
            role = "Student" if msg.get('type') == MessageType.USER else "Counselor"
            conversation_lines.append(f"{role}: {msg['content']}")
        conversation_context = "\n".join(conversation_lines) if conversation_lines else "No additional conversation."

        system_prompt = RECOMMENDATIONS_SYSTEM_PROMPT.format(
            session_learnings=COLLEGE_RECOMMENDATION_SESSION_LEARNINGS,
            preferences_context=preferences_context,
            profile_context=profile_context,
            conversation_context=conversation_context,
            countries=countries,
        )

        langchain_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate my personalized list of 20 college recommendations based on my preferences and our conversation."),
        ]

        try:
            structured_llm = self.recommendations_llm.with_structured_output(
                CollegeRecommendationsOutput, include_raw=True
            )
            raw_result = structured_llm.invoke(langchain_messages)

            if isinstance(raw_result, dict) and 'parsed' in raw_result:
                result = raw_result['parsed']
                raw_response = raw_result.get('raw')
                if raw_response:
                    usage = self._extract_token_usage(raw_response)
                    self.track_token_usage(token_usage, "recommendations", usage)
            else:
                result = raw_result

            if result is None:
                raise ValueError("Recommendations generation returned None")

            recommendations = [rec.model_dump() for rec in result.recommendations]
            return {
                "recommendations": recommendations,
                "token_usage": token_usage,
            }
        except Exception as e:
            logger.error(f"Error generating college recommendations: {e}")
            logger.error(traceback.format_exc())
            raise

    def build_voice_instructions(self, preferences: dict, user_profile: dict, session_info: dict, language: str = 'en') -> str:
        """Build system instructions for voice mode."""
        preferences_context = build_preferences_context(preferences)
        profile_context = format_user_profile_context(user_profile)

        current_step = session_info.get('current_step', 0)
        total_steps = session_info.get('total_steps', 20)
        is_completed = session_info.get('is_completed', False)

        # Build STATUS directive for session conclusion
        status_line = ''
        if is_completed:
            status_line = (
                '- STATUS: The session is complete. Thank the student warmly for the great conversation, '
                'let them know their personalized college recommendations are being prepared, and say goodbye. '
                'IMPORTANT: Maintain the exact same voice style, tone, pacing, and warmth you have been using throughout this conversation.'
            )
        instructions = f"""You are Ivy — a knowledgeable and warm college admissions counselor having a voice conversation with a student.

The student has filled out their college selection preferences:

<student_preferences>
{preferences_context}
</student_preferences>

<student_profile>
{profile_context}
</student_profile>

Current Progress:
- Current step: {current_step} of {total_steps}
- Phase: {session_info.get('current_phase', 'conversation')}

Follow this conversation flow step by step:

STEP 1 (first reply after student says "Yes"):
Say: "Great, you have selected [list countries]. Would you like to hear a comparison of these countries, or go directly to selecting colleges?"

STEP 2A (if student wants comparison):
Call the display_comparison_table tool to show a formatted comparison table of the countries in the chat. While the table is being displayed, briefly summarize the key differences verbally (2-3 sentences). Then ask: "Would you like to proceed with all these countries, or remove any from the list?"

STEP 2B (if student wants to skip):
Jump to STEP 4.

STEP 3 (if student removes countries):
Confirm the updated list, then proceed to STEP 4.

STEP 4 (final confirmation):
Say: "Your final selection is [countries]. I will shortlist 20 colleges from across these countries. Do you have any questions before I prepare your recommendations?"

STEP 5: Answer any questions concisely. After answering, ask if they have more questions.

STEP 6: When the student has no more questions, let them know recommendations are being prepared.

<voice_conversation_context>
{status_line}

VOICE-SPECIFIC GUIDELINES:
- The session starts with a static intro message from Ivy. If you are asked to announce the intro, speak it exactly as given, word for word. Do not paraphrase or add to it.
- Keep responses concise for voice (2-3 sentences per turn).
- One question at a time — do not bundle questions.
- Each response = A brief acknowledgment (1 sentence) + ONE question or statement.
- Do NOT use markdown formatting in your speech — speak naturally.
- Do NOT generate the final college list — that happens separately.
- Be warm, conversational, and genuine — not robotic.
- Speak in full, natural sentences as if talking face-to-face.
- Sound like a trusted advisor who's present and listening.
- When comparing countries, always use the display_comparison_table tool so the student can see the data in the chat.
- VOICE CONSISTENCY: Maintain the same voice style, tone, pacing, energy level, and expressiveness from the very first message through to the conclusion. Whether you are asking questions, acknowledging responses, presenting country comparisons, delivering the closing message, or resuming after a pause — your voice should sound like the same person throughout.
</voice_conversation_context>
"""
        if language == 'hi':
            instructions += (
                "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. "
                "Do NOT use English or Hinglish. Your response, including greetings, explanations, and questions, "
                "must be written in clear, warm, and natural Devanagari Hindi text. "
                "Keep responses concise and natural for voice conversation. Keep the voice query response under 30 words.]"
            )
        return instructions

    def evaluate_conclusion(
        self,
        current_step: int,
        messages: List[Dict[str, Any]],
        preferences: dict,
        user_profile: dict,
        min_questions: int = 4,
        max_questions: int = 20,
        token_usage: Dict = None,
    ) -> Dict[str, Any]:
        """Evaluate whether the college selector conversation should conclude.

        Designed to be called as a non-blocking background task after
        min_questions is reached. Uses simple text inferencing for speed.

        Returns:
            - should_conclude: bool
            - pending_topics: list of topics still worth exploring
        """
        try:
            preferences_context = build_preferences_context(preferences)
            profile_context = format_user_profile_context(user_profile)

            conversation_lines = []
            for msg in messages:
                role = "Counselor" if msg.get('type') == MessageType.BOT else "Student"
                conversation_lines.append(f"{role}: {msg.get('content', '')}")
            conversation_history = "\n".join(conversation_lines)

            system_prompt = CONCLUSION_CHECK_PROMPT.format(
                current_question_number=current_step,
                min_questions=min_questions,
                max_questions=max_questions,
                preferences_context=preferences_context,
                profile_context=profile_context,
                conversation_history=conversation_history,
            )

            response = self.llm.invoke([SystemMessage(content=system_prompt)])
            raw_content = response.content
            if isinstance(raw_content, list):
                response_text = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw_content
                ).strip()
            else:
                response_text = raw_content.strip()

            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "conclusion_check", usage)

            # Parse the simple text response
            should_conclude = False
            pending_topics: list[str] = []

            for line in response_text.split('\n'):
                line = line.strip()
                if line.upper().startswith('SHOULD_CONCLUDE:'):
                    value = line.split(':', 1)[1].strip().lower()
                    should_conclude = value == 'true'
                elif line.upper().startswith('PENDING_TOPICS:'):
                    topics_str = line.split(':', 1)[1].strip()
                    if topics_str.lower() != 'none':
                        pending_topics = [t.strip() for t in topics_str.split(',') if t.strip()]

            # Enforce hard boundaries
            if current_step < min_questions:
                should_conclude = False
            elif current_step >= max_questions:
                should_conclude = True

            logger.info(f"College selector conclusion check Q{current_step}: should_conclude={should_conclude}, pending={pending_topics}")

            return {
                'should_conclude': should_conclude,
                'pending_topics': pending_topics,
            }
        except Exception as e:
            logger.error(f"Error in college selector evaluate_conclusion: {e}", exc_info=True)
            raise


# Singleton instance
college_selector_langchain_service = CollegeSelectorLangChainService()
