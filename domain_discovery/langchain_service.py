"""
LangChain-based AI Service for Stream & Subject Selection using Azure OpenAI
"""
import os
import json
import uuid
import logging
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from utils.profile_formatting import format_user_profile_context
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator

# Import Django settings
from django.conf import settings
from utils.azure_openai import create_azure_chat_openai
from utils.message_constants import MessageType

# Initialize logger
logger = logging.getLogger(__name__)

# Helpers for sanitized LLM logging
from .llm_logging import log_llm_messages
from .constants import DOMAIN_LIST, DOMAIN_CONFIG

# Import prompts (extracted to prompts.py for readability)
from .prompts import (
    DEEPDIVE_QUESTION_GENERATION_PROMPT,
    RECOMMENDATIONS_SYSTEM_PROMPT,
    CONCLUSION_CHECK_PROMPT,
    FORMATTED_DOMAINS_WITH_DESC,
    FORMATTED_DOMAINS_SIMPLE,
    FORMATTED_DOMAINS_BULLET_DESC,
)

# Always use Azure OpenAI for Stream & Subject Selection (matches Career & Degree Selection )


# ================== Pydantic Models for Output Parsing ==================

class SubjectCombinationPathwaySchema(BaseModel):
    """Schema for a subject combination pathway that includes this subject"""
    pathway_name: str = Field(description="Clear and intuitive pathway name, e.g. 'Business Analytics Track'")
    paired_with: List[str] = Field(description="Other subjects in this combination (excluding the current subject)")
    leads_to: List[str] = Field(description="2-3 career outcomes this combination enables")
    best_for: str = Field(description="1 line describing which student profile this pathway is best suited for", max_length=200)


class RelatedSubjectSchema(BaseModel):
    """Schema for a single related subject with enrichment data"""
    subject: str = Field(description="Subject name")
    relevance: str = Field(description="Personalized reason why this subject matters for THIS student, connecting to their interests, strengths, and career goals (max 20 words)", max_length=150)
    importance: str = Field(description="Importance level: 'core' (must-have), 'supporting' (important but not mandatory), or 'optional' (exploratory)")
    importance_reason: str = Field(description="Reason for the importance classification (max 10 words)", max_length=80)
    combination_pathways: List[SubjectCombinationPathwaySchema] = Field(description="1-2 subject combination pathways this subject participates in, tailored to student's board/curriculum", default_factory=list, max_length=2)


class DomainRecommendationSchema(BaseModel):
    """Schema for a single domain recommendation"""
    domain_title: str = Field(description=f"Domain name - must be one of: {', '.join(DOMAIN_LIST)}")

    @field_validator('domain_title')
    @classmethod
    def validate_domain_title(cls, v: str) -> str:
        if v not in DOMAIN_LIST:
            raise ValueError(f"domain_title must be one of: {DOMAIN_LIST}")
        return v
    category: str = Field(description="Category like 'STEM', 'Arts', 'Business', etc.")
    match_percentage: int = Field(description="0-100 integer representing match strength", ge=0, le=100)
    key_interests: List[str] = Field(description="Related interests identified from conversation (3-5 items)")
    sub_domains: List[str] = Field(description="Specific sub-areas to explore (3-5 items)")
    related_subjects: List[RelatedSubjectSchema] = Field(description="4-6 school subjects related to this domain, each with personalized relevance, importance level, and combination pathways")
    description: str = Field(description="Clear explanation of what this domain encompasses")
    why_recommended: str = Field(description="Why this domain fits, tied to student's responses")
    exploration_activities: List[str] = Field(description="Activities to explore this domain (3-5 items)")
    potential_careers: List[str] = Field(description="3-5 career paths in this domain")


class DomainRecommendationsOutput(BaseModel):
    """Schema for the full recommendations output"""
    recommendations: List[DomainRecommendationSchema] = Field(description="List of domain recommendations (exactly 5)", min_length=5, max_length=5)


class DeepDiveQuestionResponse(BaseModel):
    """Schema for the deep dive question generation response with conclusion signal"""
    question: str = Field(description="The personalized question to ask the student (under 30 words)")
    should_conclude: bool = Field(description="Whether the LLM has enough information to conclude the interview after this question is answered. True means this should be the last question.")


# ================== LangChain Service Class ==================

class DomainDiscoveryLangChainService:
    """
    LangChain-based service for Stream & Subject Selection conversations using Azure OpenAI.
    Handles the full conversation flow including question generation and recommendations.
    """

    def __init__(self):
        self._llm = None
        self._recommendations_llm = None
        self._is_initialized = False
        self._init_error = None

    def _initialize_llm(self):
        """Initialize Azure OpenAI LLM via LangChain"""
        if self._is_initialized:
            return

        try:
            logger.info("🔧 Setting up Azure OpenAI LLMs...")
            # Get reasoning_effort from environment variable with default value "low"
            reasoning_effort = os.getenv("REASONING_EFFORT", None)
            
            # Main LLM for conversation (faster, lower cost)
            self._llm = create_azure_chat_openai(temperature=0.7, max_tokens=800, reasoning_effort=reasoning_effort)
            logger.info(f"✅ Main LLM created: {type(self._llm).__name__}")

            # LLM for recommendations (higher token limit)
            self._recommendations_llm = create_azure_chat_openai(temperature=0.7, max_tokens=8000, reasoning_effort=reasoning_effort)
            logger.info(f"✅ Recommendations LLM created: {type(self._recommendations_llm).__name__}")

            self._is_initialized = True
            logger.info("✅ Stream & Subject Selection LangChain Service initialized with Azure OpenAI")

        except Exception as e:
            self._init_error = str(e)
            logger.error(f"❌ Failed to initialize Stream & Subject Selection LangChain Service: {e}")
            raise

    @property
    def llm(self) -> ChatOpenAI:
        """Get the main LLM, initializing if needed"""
        if not self._is_initialized:
            self._initialize_llm()
        return self._llm

    @property
    def recommendations_llm(self) -> ChatOpenAI:
        """Get the recommendations LLM, initializing if needed"""
        if not self._is_initialized:
            self._initialize_llm()
        return self._recommendations_llm

    def _get_structured_output(self, llm, schema, messages: List, token_usage: Dict = None, token_category: str = "structured_output"):
        """
        Get structured output from LLM using Azure OpenAI.
        
        Args:
            llm: The language model instance
            schema: Pydantic model schema for structured output
            messages: List of messages to send
            token_usage: Optional dict to accumulate token usage into
            token_category: Category name for token tracking
            
        Returns:
            The structured response matching the schema
        """
        logger.info(f"🔧 Getting structured output for schema: {schema.__name__}")
        logger.info(f"🔧 LLM type: {type(llm).__name__}")
        
        try:
            # Use with_structured_output with include_raw=True to get the raw AIMessage for token tracking
            logger.info(f"🔧 Using with_structured_output (default method)")
            structured_llm = llm.with_structured_output(schema, include_raw=True)
            raw_result = structured_llm.invoke(messages)
            
            # Extract parsed result and raw response
            if isinstance(raw_result, dict) and 'parsed' in raw_result:
                result = raw_result['parsed']
                raw_response = raw_result.get('raw')
                # Track token usage from raw response
                if token_usage is not None and raw_response is not None:
                    usage = self._extract_token_usage(raw_response)
                    self.track_token_usage(token_usage, token_category, usage)
            else:
                # Fallback if include_raw didn't work as expected  
                result = raw_result
            
            print(f"🔧 Structured output received: {result}")
            
            if result is None:
                raise ValueError("Structured output returned None")
            
            logger.info(f"✅ Structured output succeeded! Type: {type(result).__name__}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Structured output failed: {type(e).__name__}")
            logger.error(f"❌ Error message: {error_msg[:500]}")
            logger.error(f"❌ Traceback: {traceback.format_exc()[:1000]}")
            raise

    @staticmethod
    def _extract_token_usage(response) -> Dict[str, int]:
        """Extract token usage from a LangChain LLM response.
        
        Returns dict with input_tokens, output_tokens, total_tokens,
        and cached token details (cache_read, cache_creation) when available.
        """
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_token_details": {"cache_read": 0, "cache_creation": 0},
            "output_token_details": {"reasoning": 0},
        }
        try:
            # LangChain standardized usage_metadata
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                meta = response.usage_metadata
                usage["input_tokens"] = getattr(meta, 'input_tokens', 0) or (meta.get('input_tokens', 0) if isinstance(meta, dict) else 0)
                usage["output_tokens"] = getattr(meta, 'output_tokens', 0) or (meta.get('output_tokens', 0) if isinstance(meta, dict) else 0)
                usage["total_tokens"] = getattr(meta, 'total_tokens', 0) or (meta.get('total_tokens', 0) if isinstance(meta, dict) else 0)
                # Ensure total is at least sum if not provided
                if not usage["total_tokens"]:
                    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
                
                # Extract cached/detailed token breakdowns
                # LangChain exposes input_token_details and output_token_details
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

            # Fallback: response_metadata for Azure OpenAI
            elif hasattr(response, 'response_metadata') and response.response_metadata:
                meta = response.response_metadata
                token_usage = meta.get('token_usage', {})
                if token_usage:
                    usage["input_tokens"] = token_usage.get('prompt_tokens', 0)
                    usage["output_tokens"] = token_usage.get('completion_tokens', 0)
                    usage["total_tokens"] = token_usage.get('total_tokens', 0)
                    if not usage["total_tokens"]:
                        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
                    # Azure OpenAI prompt_tokens_details / completion_tokens_details
                    prompt_details = token_usage.get('prompt_tokens_details', {})
                    if prompt_details:
                        usage["input_token_details"]["cache_read"] = prompt_details.get('cached_tokens', 0) or 0
                    completion_details = token_usage.get('completion_tokens_details', {})
                    if completion_details:
                        usage["output_token_details"]["reasoning"] = completion_details.get('reasoning_tokens', 0) or 0
        except Exception as e:
            logger.warning(f"Could not extract token usage: {e}")
        return usage

    @staticmethod
    def track_token_usage(token_usage: Dict, category: str, usage: Dict[str, int]):
        """Accumulate token usage into a tracker dict under a category.
        
        Args:
            token_usage: Mutable tracker dict to accumulate into
            category: Category name (e.g., 'session_notes', 'deepdive_question')
            usage: Token usage dict from _extract_token_usage
        """
        if token_usage is None or not usage:
            return
        
        # Initialize structure if needed
        if "categories" not in token_usage:
            token_usage["categories"] = {}
        if "total_input_tokens" not in token_usage:
            token_usage["total_input_tokens"] = 0
            token_usage["total_output_tokens"] = 0
            token_usage["total_tokens"] = 0
            token_usage["total_llm_calls"] = 0
            token_usage["total_cache_read_tokens"] = 0
            token_usage["total_cache_creation_tokens"] = 0
            token_usage["total_reasoning_tokens"] = 0
        
        # Accumulate per category
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
        
        # Accumulate totals
        token_usage["total_input_tokens"] += usage.get("input_tokens", 0)
        token_usage["total_output_tokens"] += usage.get("output_tokens", 0)
        token_usage["total_tokens"] += usage.get("total_tokens", 0)
        token_usage["total_llm_calls"] += 1
        token_usage["total_cache_read_tokens"] = token_usage.get("total_cache_read_tokens", 0) + (input_details.get("cache_read", 0) or 0)
        token_usage["total_cache_creation_tokens"] = token_usage.get("total_cache_creation_tokens", 0) + (input_details.get("cache_creation", 0) or 0)
        token_usage["total_reasoning_tokens"] = token_usage.get("total_reasoning_tokens", 0) + (output_details.get("reasoning", 0) or 0)

    def generate_session_notes(self, user_profile: Dict[str, Any], token_usage: Dict = None) -> str:
        """Generate structured observations and insights about the student's profile.
        
        These notes provide the LLM with deeper context and specific talking points
        to ask more targeted, personalized questions during Stream & Subject Selection.
        
        Uses the recommendations LLM (higher token limit) since notes require
        longer output than typical conversation responses.
        
        Args:
            user_profile: User profile data dictionary
            
        Returns:
            String of structured observations and coaching notes
        """
        try:
            profile_context = format_user_profile_context(user_profile or {})
            
            if profile_context == "No profile data available.":
                logger.info("Skipping session notes generation - insufficient profile data")
                return ""
            
            notes_prompt = f"""You are a senior student counselor preparing notes before a Stream & Subject Selection session. Analyze this student's profile and generate structured observations that will help guide the conversation.

=== STUDENT PROFILE ===
{profile_context}

Generate concise, actionable coaching notes covering these areas. Skip any section where you don't have enough data:

1. PROFILE HIGHLIGHTS: What stands out? (achievements, unique experiences, impressive stats)
2. ACADEMIC PATTERNS: What do their grades, subjects, and courses reveal about their strengths and inclinations?
3. INTEREST SIGNALS: What activities, hobbies, or choices hint at potential domain preferences?
4. FAMILY & CULTURAL CONTEXT: How might family background, location, or financial situation influence domain choices?
5. GAPS & BLIND SPOTS: What's missing from the profile that we should explore? What assumptions should we NOT make?
6. SUGGESTED PROBING AREAS: 3-5 specific topics to dig into during conversation (based on profile clues)
7. POTENTIAL DOMAIN LEANINGS: Based on available evidence, which of the 13 domains might this student gravitate toward and why?

RULES:
- Be specific - reference actual profile data points
- Note contradictions or tensions worth exploring (e.g., science grades are strong but activities are all arts-related)
- Flag any red flags or sensitive areas to handle carefully
- Keep each section to 2-3 bullet points max
- Total output should be under 500 words
- Use plain text, no markdown headers
- Be honest about uncertainty - say "insufficient data" rather than guessing

Generate the coaching notes:"""

            # Use recommendations_llm which has higher max_tokens (2500) 
            # instead of main llm (500 max_tokens) since notes need longer output
            response = self.recommendations_llm.invoke([HumanMessage(content=notes_prompt)])
            
            # Track token usage
            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "session_notes", usage)
            
            content = response.content
            if isinstance(content, list):
                content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
            
            notes = content.strip()
            
            # Cap at reasonable length
            if len(notes) > 2000:
                notes = notes[:2000]
            
            logger.info(f"Generated session notes ({len(notes)} chars)")
            return notes
            
        except Exception as e:
            logger.error(f"Error generating session notes: {e}", exc_info=True)
            raise

    def format_conversation_history(self, messages: List[Dict[str, Any]], max_messages: int = 6) -> str:
        """Format recent conversation history for context"""
        if not messages:
            return "No previous conversation."
        
        recent = messages[-max_messages:]
        formatted = []
        for msg in recent:
            role = "Student" if msg.get('type') == 'user' else "AI"
            content = msg.get('content', '')[:500]
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)

    def build_shared_instructions(
        self,
        user_profile: Dict[str, Any] = None,
        current_question_number: int = 1,
        min_questions: int = 10,
        max_questions: int = 20,
        session_notes: str = "",
        user_name: str = "",
        language: str = 'en',
    ) -> str:
        """Build the shared Stream & Subject Selection system instructions.

        This is the canonical prompt builder used by both text and realtime
        voice flows so they stay aligned.
        """
        profile_context = format_user_profile_context(user_profile or {}, user_name=user_name)

        notes_context = ""
        if session_notes:
            notes_context = (
                "\n\n=== COUNSELOR COACHING NOTES ===\n"
                "Use these pre-analyzed observations to ask deeper, more targeted questions. "
                "Reference specific data points rather than asking generic questions.\n"
                f"{session_notes}"
            )

        instructions = DEEPDIVE_QUESTION_GENERATION_PROMPT.format(
            predefined_domains=FORMATTED_DOMAINS_WITH_DESC,
            current_question_number=current_question_number,
            min_questions=min_questions,
            max_questions=max_questions,
            user_profile_context=profile_context + notes_context,
        )

        if language == 'hi':
            instructions += (
                "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. "
                "Do NOT use English or Hinglish. Your response, including greetings, questions, and acknowledgments, "
                "must be written in clear, warm, and natural Devanagari Hindi text. Keep the question under 25 words.]"
            )
        return instructions

    # ================== Unified Prompt Builder ==================

    def _build_initial_question_prompt(self, user_profile: Dict[str, Any] = None, user_name: str = "", language: str = 'en') -> str:
        """Build the HumanMessage prompt for the first question (greeting + profile check)."""
        profile_context = format_user_profile_context(user_profile or {}, user_name=user_name)

        name_part = user_name if user_name else "there"

        prompt = f"""You are HelloIvy Stream & Subject Selection Coach — a warm, encouraging counselor helping a student discover their ideal academic domain.

The 13 predefined domains are:
{FORMATTED_DOMAINS_WITH_DESC}

<student_profile>
{profile_context}
</student_profile>

Generate the FIRST message the student will see to kick off their Stream & Subject Selection session.

REQUIREMENTS:
1. Start with "Hi {name_part}!" followed by a brief, genuine compliment (1 sentence) referencing something specific and impressive from their profile (an achievement, activity, subject strength, or interest). If profile data is limited, keep the compliment warm but generic.
2. Add a short transition expressing excitement to help them discover their perfect domain (1 sentence).
3. End by mentioning that you already have access to their profile information and asking if there's anything else they'd like to add or clarify about themselves before you begin (e.g., any interests, experiences, or goals not captured in their profile).
4. Total message: under 100 words.
5. Do not use em dashes (—). Replace all em dashes with commas, periods, or parentheses"
6. Output ONLY the message text — no quotes, prefixes, or explanations.

Generate the opening message:"""

        if language == 'hi':
            prompt += (
                "\n\n[CRITICAL Hindi Instruction: You MUST generate this opening message in Hindi using Devanagari script only. "
                "Translate the core meaning of the requirements (greeting, profile check, and warm transition) into natural and warm Devanagari Hindi. "
                "Ensure NO English letters or Hinglish is used. Keep the message under 100 words.]"
            )
        return prompt

    def build_prompt_for_step(
        self,
        step: int,
        user_profile: Dict[str, Any] = None,
        min_questions: int = 25,
        max_questions: int = 35,
        session_notes: str = "",
        user_name: str = "",
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Build prompt content for any question number.

        Centralises all step-based prompt routing so that both the text flow
        (``services.py``) and the voice flow (``realtime_handler.py``) share
        the same base prompt for every step.

        This method returns prompt *content pieces* only.  It does NOT
        assemble an ``llm_messages`` list — that is the caller's
        responsibility (``generate_question`` for text,
        ``realtime_handler`` for voice).

        Args:
            step: Current question number (1-indexed).
            user_profile: User profile data dictionary.
            min_questions: Minimum deepdive questions before LLM may stop.
            max_questions: Maximum deepdive questions (hard cap).
            session_notes: AI-generated coaching notes about the student.

        Returns:
            dict with:
            - ``system_prompt``  – base system instructions (used by voice
              as-is, used as SystemMessage by text flow)
            - ``user_prompt``    – step-specific HumanMessage content
              (only for step 1; ``None`` for step >= 2 where the latest
              user response is appended by the caller)
        """
        system_prompt = self.build_shared_instructions(
            user_profile=user_profile,
            current_question_number=step,
            min_questions=min_questions,
            max_questions=max_questions,
            session_notes=session_notes,
            user_name=user_name,
            language=language,
        )

        # Step 1 uses a special standalone greeting prompt
        user_prompt = None
        if step == 1:
            user_prompt = self._build_initial_question_prompt(user_profile, user_name=user_name, language=language)

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    def _build_llm_messages(
        self,
        prompt_data: Dict[str, Any],
        step: int,
        user_response: str = None,
        messages: List[Dict[str, Any]] = None,
    ) -> list:
        """Assemble the LangChain message list for an LLM call.

        Uses the content pieces from ``build_prompt_for_step`` and adds
        conversation history + the latest user response.  This is only
        needed by the text flow — the voice flow uses
        Prompt_data['system_prompt']`` directly.
        """
        if step == 1:
            # Step 1: standalone greeting prompt (no system message)
            return [HumanMessage(content=prompt_data["user_prompt"])]

        # Step >= 2: system prompt + conversation history + user response
        llm_messages = [SystemMessage(content=prompt_data["system_prompt"])]

        for msg in (messages or []):
            content = msg.get('content', '')
            msg_type = msg.get('type')
            question_type = msg.get('question_type', '')

            if msg_type == MessageType.BOT and question_type == 'riasec':
                continue

            if msg_type == MessageType.USER:
                llm_messages.append(HumanMessage(content=content))
            elif msg_type == MessageType.BOT:
                llm_messages.append(AIMessage(content=content))

        if user_response:
            llm_messages.append(HumanMessage(content=user_response))

        return llm_messages

    def generate_question(
        self,
        step: int,
        user_response: str = None,
        messages: List[Dict[str, Any]] = None,
        user_profile: Dict[str, Any] = None,
        min_questions: int = 25,
        max_questions: int = 35,
        session_notes: str = "",
        token_usage: Dict = None,
        user_name: str = "",
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Generate a question for any step number.

        Single entry point that replaces the previous
        ``generate_initial_question`` / ``generate_deepdive_question`` split.
        Calls ``build_prompt_for_step`` for prompt content, assembles the
        LLM message list, invokes the LLM, and returns the response.

        Returns:
            dict with ``question`` (str).
        """
        try:
            prompt_data = self.build_prompt_for_step(
                step=step,
                user_profile=user_profile,
                min_questions=min_questions,
                max_questions=max_questions,
                session_notes=session_notes,
                user_name=user_name,
                language=language,
            )

            llm_messages = self._build_llm_messages(
                prompt_data, step,
                user_response=user_response,
                messages=messages,
            )

            # Log LLM messages (sanitized)
            log_llm_messages(logger, llm_messages)

            response = self.llm.invoke(llm_messages)

            # Handle content being a list (content blocks) or plain string
            raw_content = response.content
            if isinstance(raw_content, list):
                question_text = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw_content
                ).strip()
            else:
                question_text = raw_content.strip()

            # Track token usage
            token_category = "initial_question" if step == 1 else "deepdive_question"
            if token_usage is not None and response is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, token_category, usage)

            # Strip any accidental JSON wrapper or quotes
            question_text = question_text.strip('"').strip("'").strip()

            logger.info(f"Q{step}: generated via unified generate_question")

            return {"question": question_text}

        except Exception as e:
            logger.error(f"Error generating question at step {step}: {e}", exc_info=True)
            raise

    def evaluate_conclusion(
        self,
        current_step: int,
        messages: List[Dict[str, Any]],
        user_profile: Dict[str, Any] = None,
        min_questions: int = 25,
        max_questions: int = 35,
        token_usage: Dict = None
    ) -> Dict[str, Any]:
        """Evaluate whether the interview should conclude and what topics are still pending.
        
        This is designed to be called as a non-blocking background task after min_steps is reached.
        Uses simple text inferencing (no structured output) for speed.
        
        Returns:
            - should_conclude: bool
            - pending_topics: list of topics still worth exploring
        """
        try:
            profile_context = format_user_profile_context(user_profile or {})
            
            # Build conversation history text
            conversation_lines = []
            for msg in messages:
                content = msg.get('content', '')
                msg_type = msg.get('type')
                question_type = msg.get('question_type', '')
                if msg_type == MessageType.BOT and question_type == 'riasec':
                    continue
                role = "Counselor" if msg_type == MessageType.BOT else "Student"
                conversation_lines.append(f"{role}: {content}")
            conversation_history = "\n".join(conversation_lines)
            
            system_prompt = CONCLUSION_CHECK_PROMPT.format(
                predefined_domains=FORMATTED_DOMAINS_WITH_DESC,
                current_question_number=current_step,
                min_questions=min_questions,
                max_questions=max_questions,
                user_profile_context=profile_context,
                conversation_history=conversation_history
            )
            
            llm_messages = [SystemMessage(content=system_prompt)]
            
            response = self.llm.invoke(llm_messages)
            raw_content = response.content
            if isinstance(raw_content, list):
                response_text = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw_content
                ).strip()
            else:
                response_text = raw_content.strip()
            
            # Track token usage
            if token_usage is not None and response is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "conclusion_check", usage)
            
            # Parse the simple text response
            should_conclude = False
            pending_topics = []
            
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
            
            logger.info(f"Conclusion check Q{current_step}: should_conclude={should_conclude}, pending={pending_topics}")
            
            return {
                'should_conclude': should_conclude,
                'pending_topics': pending_topics
            }
        
        except Exception as e:
            logger.error(f"Error in evaluate_conclusion: {e}", exc_info=True)
            raise

    def generate_recommendations(
        self,
        messages: List[Dict[str, Any]],
        user_profile: Dict[str, Any] = None,
        token_usage: Dict = None
    ) -> List[Dict[str, Any]]:
        """Generate domain recommendations based on the conversation using structured output.
        
        RIASEC scores are now calculated and stored at the session level (1:1 mapping),
        not in individual recommendations.
        
        Returns EXACTLY 5 recommendations. Raises exception on failure.
        """
        conversation_text = self.format_conversation_history(messages, max_messages=20)
        profile_context = format_user_profile_context(user_profile or {})
        
        prompt = f"""Based on this Stream & Subject Selection conversation and the student's profile, generate EXACTLY 5 personalized domain recommendations.

You MUST ONLY recommend from these 13 predefined domains:
{FORMATTED_DOMAINS_SIMPLE}

IMPORTANT — EXCLUSION CHECK:
Before generating recommendations, carefully review the conversation below. If the student has explicitly expressed disinterest in, reluctance toward, or rejection of any specific domain (e.g., "I don't like engineering", "law isn't for me", "I want to stay away from finance"), you MUST NOT include that domain in your 5 recommendations. Absence of mention is NOT rejection — only exclude domains the student clearly said they do not want.

=== USER PROFILE ===
{profile_context}

=== CONVERSATION ===
{conversation_text}

Generate EXACTLY 5 domain recommendations. Use ONLY the exact domain names from the list above.

CRITICAL: Each recommendation MUST include ALL of these fields:
- domain_title: Domain name from the list above (e.g., "Engineering & Applied Technology")
- category: Category (STEM, Arts, Humanities, Business, Social Sciences, Life Sciences, etc.)
- match_percentage: Integer 0-100 based on alignment with student's interests
- key_interests: Array of 3-5 specific interests from the conversation that align with this domain
- sub_domains: Array of 3-5 specific sub-areas within this domain
- related_subjects: Array of 4-6 subject objects. Each object MUST have:
    "subject": Subject name (e.g., "Economics")
    "relevance": Personalized reason why this subject matters for THIS student (max 20 words)
    "importance": One of "core", "supporting", or "optional"
    "importance_reason": Reason for the importance level (max 10 words)
    "combination_pathways": Array of 1-2 objects, each with:
        "pathway_name": Clear pathway name (e.g., "Business Analytics Track")
        "paired_with": Array of other subjects in this combination (excluding current subject)
        "leads_to": Array of 2-3 career outcomes
        "best_for": 1 line describing who this combination suits best
  Example:
  {{"subject": "Economics", "relevance": "Supports your interest in business strategy and markets", "importance": "core", "importance_reason": "Essential for business domain careers", "combination_pathways": [{{"pathway_name": "Business Analytics Track", "paired_with": ["Mathematics", "Business Studies"], "leads_to": ["Business Analyst", "Management Consultant"], "best_for": "Students who enjoy analytical problem-solving"}}]}}
- description: Clear 2-3 sentence explanation of what this domain encompasses
- why_recommended: 2-3 sentences explaining why this domain fits the student based on their specific responses
- exploration_activities: Array of 3-5 concrete activities the student can do to explore this domain
- potential_careers: Array of 3-5 career paths in this domain"""

        llm_messages = [
            SystemMessage(content=RECOMMENDATIONS_SYSTEM_PROMPT.format(domain_options=FORMATTED_DOMAINS_BULLET_DESC)),
            HumanMessage(content=prompt)
        ]
        
        # Use structured output - schema enforces exactly 5 recommendations
        result = self._get_structured_output(self.recommendations_llm, DomainRecommendationsOutput, llm_messages, token_usage=token_usage, token_category="recommendations")
        
        # Convert Pydantic models to dictionaries
        recommendations = [rec.model_dump() for rec in result.recommendations]
        
        return recommendations

    def generate_final_report(
        self,
        messages: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        user_profile: Dict[str, Any] = None,
        user_name: str = "Student",
        token_usage: Dict = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive final report for the Stream & Subject Selection session.
        Includes student snapshot, interests, strengths, RIASEC analysis, and recommendations.
        
        Returns a dict with:
        - report_html: HTML formatted report for display
        - report_pdf_data: PDF content (base64 encoded if needed)
        - report_json: JSON structured data for the report
        """
        try:
            # Extract user info
            profile_data = user_profile.get('profile', user_profile) if user_profile else {}
            personal_details = profile_data.get('personalDetails', {}) if isinstance(profile_data, dict) else {}
            educational = profile_data.get('educational', {}) if isinstance(profile_data, dict) else {}
            
            student_name = user_name or "Student"
            
            student_age = self._extract_age(personal_details, user_profile)
            student_grade = educational.get('academicLevel') if isinstance(educational, dict) else None
            
            # Extract interests from conversation
            interests_data = self._extract_interests_from_conversation(messages, token_usage=token_usage)
            
            # Calculate domain alignments
            domain_alignments = self._calculate_domain_alignments(
                interests_data,
                recommendations
            )
            
            # Build report structure
            report = {
                "student_snapshot": {
                    "name": student_name,
                    "age": student_age,
                    "grade": student_grade,
                    "opening_line": "This report highlights what you enjoy and the fields you may enjoy exploring."
                },
                "what_you_enjoy": {
                    "favorite_subjects": interests_data.get('favorite_subjects', []),
                    "activities_hobbies": interests_data.get('activities_hobbies', []),
                    "dislikes_drains": interests_data.get('dislikes_drains', [])
                },
                "natural_strengths": {
                    "skills": interests_data.get('skills', []),
                    "strengths_noted": interests_data.get('strengths_noted', []),
                    "areas_of_curiosity": interests_data.get('areas_of_curiosity', [])
                },
                "domains_recommendations": {
                    "primary_domains": self._filter_domains_by_rank(recommendations, 'primary'),
                    "secondary_domains": self._filter_domains_by_rank(recommendations, 'secondary'),
                    "full_recommendations": recommendations
                },
                "why_these_domains": self._generate_domain_explanations(
                    interests_data,
                    recommendations
                ),
                "important_reminder": {
                    "message": "This is a starting point, not a final decision. Your interests can grow and change as you explore more."
                },
                "next_steps": {
                    "message": "To explore specific subjects, courses, and career paths that match these interests, continue with the Career & Degree Selection module."
                }
            }
            
            return {
                "report_json": report,
                "student_name": student_name,
                "generated_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error generating final report: {e}", exc_info=True)
            raise

    def _extract_age(self, personal_details: Dict, user_profile: Dict) -> Optional[int]:
        """Extract age from profile data"""
        if isinstance(personal_details, dict):
            dob = personal_details.get('dob')
            if dob:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(dob, '%Y-%m-%d')
                    age = (datetime.now() - birth_date).days // 365
                    return age if 10 <= age <= 50 else None
                except:
                    pass
        
        if user_profile and user_profile.get('age'):
            return user_profile['age']
        return None

    def _extract_interests_from_conversation(self, messages: List[Dict[str, Any]], token_usage: Dict = None) -> Dict[str, Any]:
        """Extract interest signals from conversation using LLM analysis for better accuracy.
        
        Instead of simple keyword matching, this uses the LLM to understand student's interests,
        strengths, and curiosities in context.
        """
        try:
            conversation_text = self.format_conversation_history(messages, max_messages=30)
            
            if not conversation_text or conversation_text == "No previous conversation.":
                # Return defaults if no conversation
                return {
                    'favorite_subjects': ['Science', 'Technology', 'Creative Subjects'],
                    'activities_hobbies': ['Learning', 'Exploring', 'Creating'],
                    'dislikes_drains': [],
                    'skills': ['Curiosity', 'Adaptability', 'Communication'],
                    'strengths_noted': ['Shows interest in diverse topics'],
                    'areas_of_curiosity': ['Understanding how things work', 'Exploring new ideas']
                }
            
            extraction_prompt = f"""Analyze this student's conversation and extract their key interests, strengths, and areas of curiosity.

CONVERSATION:
{conversation_text}

Extract and return a JSON object with EXACTLY this format (no additional fields):
{{
  "favorite_subjects": ["<specific subjects/fields mentioned or implied>"],
  "activities_hobbies": ["<specific activities they enjoy>"],
  "dislikes_drains": ["<things that drain or demotivate them, if mentioned>"],
  "skills": ["<skills they mention having or imply they have>"],
  "strengths_noted": ["<strengths evident from how they speak about their interests>"],
  "areas_of_curiosity": ["<areas they express curiosity about>"]
}}

Rules:
- Extract directly from what the student said, not from assumptions
- Include only 3-5 items per category
- Use specific details (e.g., "robotics" not just "technology")
- If a category has nothing to extract, use empty array []
- Return ONLY valid JSON, no other text"""
            
            llm_messages = [
                SystemMessage(content="You are an expert at understanding students' interests and strengths from conversations. Extract key themes and patterns. Do NOT use separators like em dash (—), en dash (–), or similar formatting characters."),
                HumanMessage(content=extraction_prompt)
            ]
            
            response = self.recommendations_llm.invoke(llm_messages)
            
            # Track token usage
            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "interest_extraction", usage)
            
            # Parse JSON response
            import json
            import re
            
            content = response.content
            if isinstance(content, list):
                content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
            response_text = content.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                interests_data = json.loads(json_match.group())
                return {
                    'favorite_subjects': interests_data.get('favorite_subjects', []),
                    'activities_hobbies': interests_data.get('activities_hobbies', []),
                    'dislikes_drains': interests_data.get('dislikes_drains', []),
                    'skills': interests_data.get('skills', []),
                    'strengths_noted': interests_data.get('strengths_noted', []),
                    'areas_of_curiosity': interests_data.get('areas_of_curiosity', [])
                }
        
        except Exception as e:
            logger.error(f"Error extracting interests with LLM: {e}", exc_info=True)
            raise

    def _calculate_domain_alignments(
        self,
        interests_data: Dict[str, Any],
        recommendations: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate alignment scores for each recommended domain"""
        alignments = {}
        for rec in recommendations:
            domain = rec.get('domain_title', '')
            match_pct = rec.get('match_percentage', 50)
            alignments[domain] = match_pct
        return alignments

    def _filter_domains_by_rank(self, recommendations: List[Dict[str, Any]], rank: str) -> List[Dict[str, Any]]:
        """Filter recommendations by primary or secondary ranking"""
        if not recommendations:
            return []
        
        if rank == 'primary':
            # Return top 2 recommendations (ranks 1-2)
            return recommendations[:2]
        elif rank == 'secondary':
            # Return remaining 3 recommendations (ranks 3-5)
            return recommendations[2:5] if len(recommendations) > 2 else []
        
        return recommendations

    def _generate_domain_explanations(
        self,
        interests_data: Dict[str, Any],
        recommendations: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate explanations for why domains fit the student"""
        explanations = []
        favorite_subjects = interests_data.get('favorite_subjects', [])
        
        for rec in recommendations[:3]:  # Top 3 recommendations
            domain = rec.get('domain_title', '')
            why_rec = rec.get('why_recommended', '')
            
            # Build custom explanation
            explanation = f"{domain}: {why_rec}"
            
            if favorite_subjects:
                explanation += f" Your interest in {', '.join(favorite_subjects[:2])} connects directly to this field."
            
            explanations.append(explanation)
        
        return explanations


# Singleton instance
domain_langchain_service = DomainDiscoveryLangChainService()
