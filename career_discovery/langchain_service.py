"""
LangChain-based AI Service for Career & Degree Selection using Azure OpenAI
Uses 10 specialized career evaluation agents for comprehensive career guidance.
"""
import os
import json
import uuid
import logging
from typing import List, Dict, Any, Literal, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# Import Django settings
from django.conf import settings
from utils.azure_openai import create_azure_chat_openai
from utils.profile_formatting import format_user_profile_context
from utils.message_constants import MessageType

# Import career evaluation agents
from .constants import (
    CAREER_AGENTS,
    AGENT_IDS,
    AGENT_CATEGORIES,
    DEFAULT_AGENT_WEIGHTS,
    QUESTION_CATEGORIES,
    DOMAIN_CAREER_MAPPING,
    CROSS_DOMAIN_CAREERS,
    get_agent_system_prompt,
    get_agent_questions,
    get_all_agent_questions,
)

# Import all predefined domains for Career & Degree Selection opening message
from domain_discovery.constants import DOMAIN_LIST as ALL_PREDEFINED_DOMAINS

logger = logging.getLogger(__name__)

# Import prompts (extracted to prompts.py for readability)
from .prompts import (
    CAREER_DISCOVERY_SYSTEM_PROMPT,
    RECOMMENDATIONS_SYSTEM_PROMPT,
    STATIC_AGENT_EVALUATION_CONTEXT,
)


# ================== Pydantic Models for Output Parsing ==================

class AgentScoreSchema(BaseModel):
    """Schema for individual agent evaluation scores"""
    psychologist: int = Field(description="Psychological fit score (0-100)", ge=0, le=100)
    market_reality: int = Field(description="Market viability score (0-100)", ge=0, le=100)
    skills_gap: int = Field(description="Skills feasibility score (0-100)", ge=0, le=100)
    constraint: int = Field(description="Constraint feasibility score (0-100)", ge=0, le=100)
    values: int = Field(description="Values alignment score (0-100)", ge=0, le=100)
    automation_risk: int = Field(description="Automation resistance score (0-100)", ge=0, le=100)
    trajectory: int = Field(description="Career trajectory clarity score (0-100)", ge=0, le=100)
    regret_minimization: int = Field(description="Optionality/flexibility score (0-100)", ge=0, le=100)
    black_swan: int = Field(description="Upside potential score (0-100)", ge=0, le=100)


class ProsAndConsSchema(BaseModel):
    """Schema for pros and cons of a career"""
    pros: List[str] = Field(description="List of 3-5 advantages/benefits of this career")
    cons: List[str] = Field(description="List of 3-5 disadvantages/challenges of this career")


class FeasibilitySchema(BaseModel):
    """Schema for the feasibility metric of a career recommendation"""
    level: Literal["High", "Medium", "Low"] = Field(
        description="Overall feasibility level: High (student can realistically pursue this with current profile), Medium (achievable with moderate effort/changes), Low (significant barriers exist)"
    )
    reason: str = Field(
        description="1-2 sentence explanation grounded in the student's actual profile — cite specific factors like current skills, education, location, finances, or constraints that drive this rating.",
        max_length=400,
    )


class DegreePathwaySchema(BaseModel):
    """Schema for a pathway within a degree"""
    rank: str = Field(description="Pathway rank: 'Core Path', 'Alternate Path', or 'Differentiated Path'")
    label: str = Field(description="Short label for the pathway, e.g. 'Strategy & Consulting Track'")
    why: str = Field(description="1-2 line explanation of why this pathway fits the student for this career", max_length=500)


class DegreeDecisionFilterSchema(BaseModel):
    """Schema for a degree decision rule"""
    condition: str = Field(description="Student trait or interest, e.g. 'you enjoy analysis, data, and economics thinking'")


class DegreeSchema(BaseModel):
    """Schema for a single degree with enrichment data"""
    degree: str = Field(description="Degree name, e.g. 'B.S. in Computer Science', 'MBA', 'B.A. in Psychology'")
    fit_score: int = Field(description="Fit score from 1 to 5 reflecting both career relevance and student profile alignment", ge=1, le=5)
    fit_reason: str = Field(description="5-8 word justification tied to user profile and career", max_length=100)
    pathway: DegreePathwaySchema = Field(description="Which pathway this degree belongs to (Core Path, Alternate Path, or Differentiated Path) with personalized reasoning")
    decision_filter: DegreeDecisionFilterSchema = Field(description="Decision rule: 'If you enjoy [trait/interest]' that points to choosing this degree")


class CareerRecommendationSchema(BaseModel):
    """Schema for a single career recommendation"""
    career_title: str = Field(description="Specific job title", max_length=200)
    match_percentage: int = Field(description="0-100 integer representing weighted match strength from all evaluation dimensions", ge=0, le=100)
    required_skills: List[str] = Field(description="List of required skills", max_length=10)
    next_steps: List[str] = Field(description="Actionable next steps to explore this career (hands-on activities, projects, networking, internships — NEVER degree or program recommendations)", max_length=5)
    description: str = Field(description="Clear day-to-day explanation for the role", max_length=2000)
    why_recommended: str = Field(description="Why this career fits, tied to student's responses and evaluation insights", max_length=2000)
    alignment_points: List[str] = Field(description="Specific mappings from student's words to career aspects, including evaluation insights", max_length=5)
    related_subjects: List[str] = Field(description="Academic subjects or fields of study most relevant to this career, e.g. Mathematics, Computer Science, Psychology", max_length=8)
    degrees: List[DegreeSchema] = Field(description="4-6 degree objects, each with fit score, pathway classification, and decision filter. Include both undergraduate and graduate degrees where relevant.")
    day_in_life: str = Field(description="A vivid description of a typical day in this career, from morning to evening, covering key activities, interactions, and what makes the day rewarding", max_length=2000)
    pros_and_cons: ProsAndConsSchema = Field(description="Pros and cons of this career")
    work_life_balance: str = Field(description="Honest assessment of work-life balance including typical working hours, remote work potential, stress levels, flexibility, and how it compares to similar careers", max_length=1000)
    agent_scores: Optional[AgentScoreSchema] = Field(description="Individual scores from each evaluation dimension", default=None)
    feasibility: FeasibilitySchema = Field(
        description="Feasibility rating (High/Medium/Low) for this career given the student's actual profile, skills, education, and constraints — with a brief evidence-based reason."
    )
    skill_gaps: List[str] = Field(
        description=(
            "Top 5 personalised skill gaps for THIS specific student for this career. "
            "Derived strictly as: (what this career requires day-to-day) MINUS (what this student already has based on their profile + conversation). "
            "Each gap must: (1) reference the student's actual situation where relevant (e.g. their degree, internship, projects they mentioned), "
            "(2) name the specific tool/method/knowledge they're missing — not a generic job description item, "
            "(3) be phrased so the student reads it and thinks 'yes, that IS my gap'. "
            "Format: short noun phrase (4-10 words). Ranked most-critical first. Exactly 5 items. "
            "Do NOT list skills the student already mentioned having. "
            "Bad example: 'Statistical inference skills'. "
            "Good example: 'Statistics depth beyond your BSBE core curriculum' or 'Production SQL experience beyond class projects'. "
            "For example, if they are studying BSBE, write 'Python coding depth beyond your BSBE coursework', not just 'Python coding'. "
            "If they have done a project in React, but the career requires backend, write 'Backend API integration beyond your frontend React project', not 'backend development'. "
            "Every gap must feel custom-written for this specific student's background so they immediately recognize it as their actual gap."
        ),
        min_length=5,
        max_length=5,
    )


class CareerRecommendationsOutput(BaseModel):
    """Schema for the full recommendations output"""
    recommendations: List[CareerRecommendationSchema] = Field(description="List of career recommendations (max 8)", max_length=8)


# Literal type covering the 12 canonical domains
DomainLiteral = Literal[
    "Pure Science",
    "Performing Arts",
    "Humanities",
    "Business / Entrepreneurship",
    "Statistics / Finance / Data Analytics",
    "Law",
    "Social Sciences",
    "Health & Life Science",
    "Sports/Athletics",
    "Engineering & Applied Technology",
    "Art & Aesthetics",
    "Public Policy, Governance & Impact",
]


class DomainChoicesOutput(BaseModel):
    """Structured output schema for extracting the student's chosen domains
    from the first two Q&A turns of the career-discovery conversation."""

    primary_domain: DomainLiteral = Field(
        description="The domain the student selected as their primary / top interest."
    )
    secondary_domain: Optional[DomainLiteral] = Field(
        default=None,
        description=(
            "The domain the student picked as their secondary interest. "
            "None / null if they chose 'None of the above'."
        ),
    )


# ================== LangChain Service Class ==================

class CareerDiscoveryLangChainService:
    """
    LangChain-based service for Career & Degree Selection conversations using Azure OpenAI.
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
            # Main LLM for conversation (faster, lower cost)
            reasoning_effort = os.getenv("REASONING_EFFORT", None)

            self._llm = create_azure_chat_openai(temperature=0.7, max_tokens=800, reasoning_effort=reasoning_effort)

            # LLM for recommendations (higher token limit for full career recommendations)
            self._recommendations_llm = create_azure_chat_openai(temperature=0.7, max_tokens=8000, reasoning_effort=reasoning_effort)

            self._is_initialized = True
            print("[SUCCESS] Career & Degree Selection LangChain Service initialized with Azure OpenAI")

        except Exception as e:
            self._init_error = str(e)
            print(f"[ERROR] Failed to initialize Career & Degree Selection LangChain Service: {e}")
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

    @staticmethod
    def _extract_token_usage(response) -> dict:
        """Extract token usage from a LangChain LLM response.
        
        Works with ChatOpenAI responses.
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
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                meta = response.usage_metadata
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
        except Exception:
            pass
        return usage

    @staticmethod
    def track_token_usage(token_usage: dict, category: str, usage: dict):
        """Accumulate token usage into a tracker dict under a category."""
        if token_usage is None or not usage:
            return
        
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

    def _build_agent_evaluation_context(self) -> str:
        """Build context string describing all 10 career evaluation agents.
        
        DEPRECATED: Use module-level STATIC_AGENT_EVALUATION_CONTEXT instead
        for prompt cache optimization. This method is kept for backward compatibility.
        """
        return STATIC_AGENT_EVALUATION_CONTEXT

    def _get_agent_questions_for_step(self, current_step: int) -> List[str]:
        """Get relevant agent question themes based on conversation step.
        
        Uses a rotation pattern to ensure all 9 agents are covered across 20 questions,
        preventing deep diving into any single topic area.
        
        Steps 3-4 are reserved for domain motivation deep-dive (no agent guidance).
        """
        # Steps 3-4: domain motivation deep-dive — no agent guidance needed
        if current_step in (3, 4):
            return []

        # Define agent rotation order - cycles through all agents
        # Steps 0-2 are domain selection; steps 3-4 are motivation deep-dive
        # Agent guidance starts at step 5
        agent_rotation = [
            "psychologist",      # Step 0: Personality/stress
            "values",            # Step 1: Money vs meaning
            "skills_gap",        # Step 2: Current abilities
            "constraint",        # Step 3: (skipped — domain motivation)
            "market_reality",    # Step 4: (skipped — domain motivation)
            "trajectory",        # Step 5: Career path vision
            "regret_minimization", # Step 6: Flexibility/optionality
            "black_swan",        # Step 7: Unconventional paths
            # Cycle repeats with slight variations
            "psychologist",      # Step 8: Work environment
            "values",            # Step 9: Lifestyle preferences
            "skills_gap",        # Step 10: Learning potential
            "market_reality",    # Step 11: Industry awareness
            "constraint",        # Step 12: Geographic/budget
            "trajectory",        # Step 13: Leadership vs expertise
            "regret_minimization", # Step 14: Specialization
            "black_swan",        # Step 15: Risk tolerance
            "values",            # Step 16: Final values check
            "psychologist",      # Step 17: Final personality fit
            "skills_gap",        # Step 18: Skill depth
            "market_reality",    # Step 19: Industry trends
        ]
        
        # Get the primary agent for this step
        step_index = current_step % len(agent_rotation)
        primary_agent = agent_rotation[step_index]
        
        # Get questions from the primary agent
        questions = get_agent_questions(primary_agent)
        
        return questions

    def build_conversation_history(self, messages: List[Dict[str, Any]], max_turns: int = 8) -> str:
        """Build a formatted conversation history string"""
        recent_messages = messages[-max_turns:] if len(messages) > max_turns else messages
        history_lines = []
        for msg in recent_messages:
            role = "Student" if msg.get('type') == 'user' else "Coach"
            content = msg.get('content', '')
            history_lines.append(f"{role}: {content}")
        return "\n".join(history_lines)

    def build_profile_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Build a summary of student's profile answers"""
        user_messages = [m for m in messages if m.get('type') == MessageType.USER][:5]
        if not user_messages:
            return "No responses yet."
        
        summary_lines = []
        for i, msg in enumerate(user_messages, 1):
            content = msg.get('content', '')[:200]  # Truncate long responses
            summary_lines.append(f"- Answer {i}: {content}")
        return "\n".join(summary_lines)


    def format_domain_context_for_prompt(self, domain_context: Dict[str, Any]) -> str:
        """Format Stream & Subject Selection context for AI prompts"""
        if not domain_context or not domain_context.get('recommendations'):
            return "No Stream & Subject Selection session completed yet."
        
        context_parts = []
        context_parts.append("=== Stream & Subject Selection RESULTS ===")
        
        recommendations = domain_context.get('recommendations', [])
        if recommendations:
            context_parts.append(f"\nTop {len(recommendations)} Recommended Domains:")
            for i, rec in enumerate(recommendations, 1):
                title = rec.get('title', 'Unknown')
                match_pct = rec.get('match_percentage', 0)
                explanation = rec.get('explanation', '')
                context_parts.append(f"\n{i}. {title} ({match_pct}% match)")
                if explanation:
                    context_parts.append(f"   Reason: {explanation[:200]}")
        
        # Include some Q&A samples to show student's interests
        messages = domain_context.get('messages', [])
        if messages:
            context_parts.append("\n=== Stream & Subject Selection KEY INSIGHTS ===")
            user_responses = [m for m in messages if m.get('type') == 'user'][:5]
            for i, msg in enumerate(user_responses, 1):
                content = msg.get('content', '')[:150]
                context_parts.append(f"Response {i}: {content}")
        
        return "\n".join(context_parts)

    # ------------------------------------------------------------------ #
    #  Structured domain extraction (called once after Q2 is answered)    #
    # ------------------------------------------------------------------ #

    def extract_domain_choices(
        self,
        messages: List[Dict[str, Any]],
        domain_context: Dict[str, Any],
        token_usage: Dict = None,
    ) -> Dict[str, Any]:
        """Use a structured-output LLM call to reliably extract the
        student's primary and secondary domain choices from the first
        two Q&A turns.

        Returns a dict ready to be stored in ``session.metadata``:
        {
            "primary_domain": "Law",
            "secondary_domain": "Humanities",   # or None
            "career_references": ["Lawyer", …],
            "hybrid_career_references": ["Ethics Researcher", …],
        }
        """
        self._initialize_llm()

        # Build a concise transcript of Intro + A0 + Q1 + A1 + Q2 + A2
        # The first message is the static intro, so we need up to 6 messages
        # to capture both domain selection turns.
        transcript_lines: List[str] = []
        for msg in messages[:6]:
            role = "Coach" if msg.get('type') in (MessageType.BOT, 'bot') else "Student"
            transcript_lines.append(f"{role}: {msg.get('content', '')}")
        transcript = "\n".join(transcript_lines)

        # List all 12 domains so the LLM knows the valid options
        domain_list_str = "\n".join(
            f"- {d}" for d in ALL_PREDEFINED_DOMAINS
        )

        # Domain recommendations the student was shown (top 5)
        recs = domain_context.get('recommendations', [])
        shown_domains_str = ", ".join(
            rec.get('title', '') for rec in recs
        ) or "(none)"

        prompt = f"""You are a domain-choice extractor.  Read the transcript
of the first two career-discovery turns and determine which domains the
student chose.

Valid domains (pick ONLY from this list):
{domain_list_str}

The student's top-5 recommended domains were: {shown_domains_str}
The remaining domains were shown as a numbered list for the secondary pick.

--- Transcript ---
{transcript}
--- End Transcript ---

Return the primary_domain and secondary_domain the student selected.
If the student chose "None of the above" (or equivalent) for the secondary,
return secondary_domain as null."""

        structured_llm = self.llm.with_structured_output(
            DomainChoicesOutput, include_raw=True
        )
        raw_result = structured_llm.invoke([
            SystemMessage(content="Extract the student's domain choices."),
            HumanMessage(content=prompt),
        ])

        # Parse result
        if isinstance(raw_result, dict) and 'parsed' in raw_result:
            parsed: DomainChoicesOutput = raw_result['parsed']
            raw_response = raw_result.get('raw')
            if token_usage is not None and raw_response is not None:
                usage = self._extract_token_usage(raw_response)
                self.track_token_usage(token_usage, "domain_extraction", usage)
        else:
            parsed = raw_result  # type: ignore[assignment]

        primary = parsed.primary_domain
        secondary = parsed.secondary_domain

        # Derive career_references from DOMAIN_CAREER_MAPPING
        career_refs: List[str] = list(DOMAIN_CAREER_MAPPING.get(primary, []))
        if secondary:
            career_refs += [
                c for c in DOMAIN_CAREER_MAPPING.get(secondary, [])
                if c not in career_refs
            ]

        # Derive hybrid_career_references from CROSS_DOMAIN_CAREERS
        hybrid_refs: List[str] = []
        if secondary:
            for domain in (primary, secondary):
                other = secondary if domain == primary else primary
                for entry in CROSS_DOMAIN_CAREERS.get(domain, []):
                    if entry.get('secondary_domain') == other:
                        name = entry.get('career', '')
                        if name and name not in hybrid_refs:
                            hybrid_refs.append(name)

        result = {
            "primary_domain": primary,
            "secondary_domain": secondary,
            "career_references": career_refs,
            "hybrid_career_references": hybrid_refs,
        }
        print(f"[SUCCESS] Structured domain extraction: {primary} + {secondary} "
              f"| {len(career_refs)} careers | {len(hybrid_refs)} hybrid")
        return result

    # ------------------------------------------------------------------ #
    #  Build focused-domain context from pre-computed metadata            #
    # ------------------------------------------------------------------ #

    def _get_focused_domains_context(
        self,
        domain_context: Dict[str, Any],
        messages: List[Dict[str, Any]] = None,
        chosen_domains: Dict[str, Any] = None,
    ) -> Tuple[List[str], str]:
        """Build career-focused context from pre-computed domain metadata.

        ``chosen_domains`` should come from ``session.metadata['domain_choices']``
        which is populated by ``extract_domain_choices()`` after Q2.

        Keys expected in *chosen_domains*:
        - primary_domain, secondary_domain
        - career_references, hybrid_career_references

        Falls back to algorithm top-2 when metadata is absent.

        Returns:
            Tuple of (focused_domain_titles, career_context_string)
        """
        if not domain_context or not domain_context.get('recommendations'):
            return [], ""

        recommendations = domain_context.get('recommendations', [])

        # --- Resolve focused domains ------------------------------------- #
        if chosen_domains and chosen_domains.get('primary_domain'):
            top_domains = [chosen_domains['primary_domain']]
            if chosen_domains.get('secondary_domain'):
                top_domains.append(chosen_domains['secondary_domain'])
            career_refs: Optional[List[str]] = chosen_domains.get('career_references')
            hybrid_refs: Optional[List[str]] = chosen_domains.get('hybrid_career_references')
        else:
            # Fallback: algorithm top-2 (only used if extract_domain_choices wasn't called)
            top_domains = [rec.get('title', '') for rec in recommendations[:2]]
            career_refs = None
            hybrid_refs = None

        # --- Build context string ---------------------------------------- #
        context_parts: List[str] = []
        context_parts.append("=== FOCUSED DOMAINS & CAREER PATHS ===")
        context_parts.append(
            "The student has chosen the following domain(s). "
            "Focus ALL questions on exploring SPECIFIC CAREERS within these domains ONLY:"
        )

        # Use pre-computed career_references if available, else fall back to constant
        if career_refs is not None:
            # Group by domain for readability
            for domain in top_domains:
                domain_careers = DOMAIN_CAREER_MAPPING.get(domain, [])
                present = [c for c in domain_careers if c in career_refs]
                if present:
                    context_parts.append(f"\n**{domain}** - Example careers (not exhaustive):")
                    for career in present:
                        context_parts.append(f"  - {career}")
        else:
            for domain in top_domains:
                careers = DOMAIN_CAREER_MAPPING.get(domain, [])
                if careers:
                    context_parts.append(f"\n**{domain}** - Example careers (not exhaustive):")
                    for career in careers:
                        context_parts.append(f"  - {career}")

        # ---- Hybrid / cross-domain careers (from session metadata) ---- #
        if hybrid_refs:
            context_parts.append("\n=== HYBRID / CROSS-DOMAIN CAREERS ===")
            context_parts.append(
                "The following careers sit at the INTERSECTION of the student's "
                "two focused domains. Prioritise exploring these during the "
                "conversation and consider them strongly for recommendations:"
            )
            for career in hybrid_refs:
                context_parts.append(f"  - {career}")
            context_parts.append(
                "\nDive deep on these hybrid careers — ask questions that explore "
                "how the student's interests in BOTH domains could come together "
                "in these roles."
            )

        context_parts.append(
            "\nNOTE: The careers listed above are examples, not the complete list. "
            "You may recommend any legitimate career that falls within these domains, "
            "including niche, emerging, or interdisciplinary roles."
        )
        context_parts.append(
            "\nIMPORTANT: Ask questions that help determine which SPECIFIC CAREERS "
            "within these domains best fit the student. Focus on day-to-day work "
            "preferences, skills, and interests that differentiate between careers "
            "in these domains."
        )
        context_parts.append(
            "Do NOT ask generic questions unrelated to these domain careers. "
            "Every question should help narrow down the best career fit within "
            "these focused domains."
        )

        return top_domains, "\n".join(context_parts)

    def build_shared_instructions(
        self,
        user_profile: Dict[str, Any] = None,
        domain_context: Dict[str, Any] = None,
        current_step: int = None,
        agent_guidance: str = "",
        session_notes: str = "",
        messages: List[Dict[str, Any]] = None,
        user_name: str = "",
        language: str = 'en',
    ) -> Tuple[str, str]:
        """Build the canonical shared Career & Degree Selection instructions.

        Returns the same static prompt + dynamic context pair used by text and
        realtime voice flows so core reasoning stays in sync.
        """
        user_profile_context = format_user_profile_context(user_profile or {}, user_name=user_name)
        static_prompt = CAREER_DISCOVERY_SYSTEM_PROMPT.format(
            user_profile_context=user_profile_context,
        )

        dynamic_context = self._build_dynamic_context(
            domain_context=domain_context,
            current_step=current_step,
            agent_guidance=agent_guidance,
            session_notes=session_notes,
            messages=messages,
        )

        if language == 'hi':
            static_prompt += (
                "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. "
                "Do NOT use English or Hinglish. Your response, including questions and acknowledgments, "
                "must be written in clear, warm, and natural Devanagari Hindi text. Keep the question under 25 words.]"
            )

        return static_prompt, dynamic_context

    def _build_enhanced_system_prompt(
        self,
        user_profile: Dict[str, Any] = None,
        domain_context: Dict[str, Any] = None,
        current_step: int = None,
        agent_guidance: str = "",
        session_notes: str = "",
        debug_label: str = "ENHANCED SYSTEM PROMPT",
        messages: List[Dict[str, Any]] = None,
        user_name: str = "",
        language: str = 'en',
    ) -> Tuple[str, str]:
        """
        Build system prompt with user profile formatted in, plus a
        separate dynamic context SystemMessage for domain results,
        session notes, and step tracking.
        
        Args:
            user_profile: User profile data dictionary
            domain_context: Stream & Subject Selection results dictionary
            current_step: Current conversation step (0-indexed), if applicable
            agent_guidance: Additional agent-specific guidance text
            session_notes: AI-generated coaching notes about the student
            debug_label: Label for debug output
            messages: Conversation messages (used to detect domain overrides)
            
        Returns:
            Tuple of (system_prompt, dynamic_context):
            - system_prompt: Instructions with student profile formatted in
            - dynamic_context: Per-session domain context and coaching notes
        """
        return self.build_shared_instructions(
            user_profile=user_profile,
            domain_context=domain_context,
            current_step=current_step,
            agent_guidance=agent_guidance,
            session_notes=session_notes,
            messages=messages,
            user_name=user_name,
            language=language,
        )

    def _build_dynamic_context(
        self,
        domain_context: Dict[str, Any] = None,
        current_step: int = None,
        agent_guidance: str = "",
        session_notes: str = "",
        messages: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Build per-session dynamic context string.
        
        This content changes per user/session and is sent as a separate
        SystemMessage to avoid breaking the static prompt cache.
        Note: user profile is now formatted into the main system prompt
        via the <student_profile> section.
        """
        # Format domain context
        domain_ctx = self.format_domain_context_for_prompt(domain_context or {})
        
        dynamic_parts = []
        dynamic_parts.append(domain_ctx)
        
        # After step 2, add focused domain career context so questions target
        # specific careers within the student's chosen/top domains
        if current_step is not None and current_step >= 2 and domain_context:
            _, focused_ctx = self._get_focused_domains_context(
                domain_context, messages=messages,
                chosen_domains=domain_context.get('domain_choices'),
            )
            if focused_ctx:
                dynamic_parts.append(focused_ctx)
        
        # Add session notes if available
        if session_notes:
            dynamic_parts.append("\n=== COUNSELOR COACHING NOTES ===")
            dynamic_parts.append("Use these pre-analyzed observations to ask deeper, more targeted questions. Reference specific data points rather than asking generic questions.")
            dynamic_parts.append(session_notes)
        
        if agent_guidance:
            dynamic_parts.append(agent_guidance)
        
        if current_step is not None:
            dynamic_parts.append(f"\nCurrent Question Number: {current_step + 1} of 20")
        
        return "\n".join(dynamic_parts)

    def generate_session_notes(
        self,
        user_profile: Dict[str, Any],
        domain_context: Dict[str, Any],
        token_usage: Dict = None
    ) -> str:
        """Generate structured observations about the student for Career & Degree Selection .
        
        Combines profile data with Stream & Subject Selection results and conversation to produce
        actionable coaching notes that help the LLM ask deeper, more targeted questions.
        
        Args:
            user_profile: User profile data dictionary
            domain_context: Stream & Subject Selection session context (messages + recommendations)
            
        Returns:
            String of structured observations and career exploration notes
        """
        try:
            user_profile_context = format_user_profile_context(user_profile or {})
            domain_ctx = self.format_domain_context_for_prompt(domain_context or {})
            
            if user_profile_context == "No profile data available." and domain_ctx == "No Stream & Subject Selection session completed yet.":
                return ""
            
            # Extract conversation insights from Stream & Subject Selection
            domain_conversation_summary = ""
            if domain_context and domain_context.get('messages'):
                user_responses = [
                    m.get('content', '') for m in domain_context.get('messages', [])
                    if m.get('type') == 'user'
                ]
                if user_responses:
                    domain_conversation_summary = "\n".join([
                        f"- {resp[:200]}" for resp in user_responses[:10]
                    ])
            
            notes_prompt = f"""You are a senior career counselor preparing notes before a Career & Degree Selection session. This student has already completed Stream & Subject Selection. Analyze ALL available data and generate deep, actionable coaching notes.

=== STUDENT PROFILE ===
{user_profile_context}

{domain_ctx}

=== Stream & Subject Selection CONVERSATION HIGHLIGHTS ===
{domain_conversation_summary if domain_conversation_summary else "No conversation data available."}

Generate concise, actionable coaching notes covering these areas. Skip any section where you don't have enough data:

1. **PROFILE-TO-CAREER BRIDGES**: What specific profile data points (grades, activities, achievements) map to concrete career paths? Be specific.
   Example: "Math Olympiad participation + coding club = strong signal for quantitative roles like Data Scientist or Quant Analyst"

2. **Stream & Subject Selection INSIGHTS**: What did we learn from the domain session? What patterns emerged in their responses? What surprised us?
   - Which domain recommendation feels strongest vs. weakest?
   - Any contradictions between their stated interests and domain results?
   - Key quotes or responses that reveal deep preferences

3. **CAREER EXPLORATION ANGLES**: 5-7 specific career-related topics to probe during this session:
   - Work environment preferences (solo vs. team, structured vs. flexible)
   - Day-to-day activity preferences (building, analyzing, presenting, mentoring)
   - Risk tolerance and ambition level
   - Practical constraints (location, finances, family expectations)
   - Long-term vision vs. short-term interests

4. **POTENTIAL CAREER CLUSTERS**: Based on evidence, list 3-4 career clusters to explore with specific job titles:
   Example: "Tech-Creative cluster: UX Designer, Product Manager, Creative Technologist"

5. **SENSITIVE AREAS & ASSUMPTIONS TO AVOID**: 
   - Family expectations that might conflict with interests
   - Financial constraints that narrow options
   - Don't assume a student who likes science wants to be a doctor

6. **KNOWLEDGE GAPS TO FILL**: What do we still NOT know that's critical for good career recommendations?
   - Unasked questions about work style, values, or lifestyle preferences
   - Missing data about their awareness of specific careers

7. **PERSONALITY & WORK STYLE CLUES**: Based on how they communicated in Stream & Subject Selection:
   - Are their responses detailed or brief? (may indicate introversion/extroversion)
   - Do they show decisiveness or explore many options?
   - Do they lean practical or idealistic?

RULES:
- Reference SPECIFIC data points from the profile and domain conversation
- Be honest about what you DON'T know - flag gaps explicitly
- Note contradictions worth exploring (e.g., loves art but chose engineering domain)
- Each section: 2-4 bullet points max
- Total output: under 600 words
- Use plain text, no markdown headers
- Prioritize actionable insights over generic observations

Generate the coaching notes:"""

            response = self.llm.invoke([HumanMessage(content=notes_prompt)])
            
            # Track token usage
            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "session_notes", usage)
            
            # Handle case where response.content might be a list
            content = response.content
            if isinstance(content, list):
                notes = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content]).strip()
            else:
                notes = content.strip()
            
            # Cap at reasonable length
            if len(notes) > 2500:
                notes = notes[:2500]
            
            print(f"[SUCCESS] Generated career session notes ({len(notes)} chars)")
            return notes
            
        except Exception as e:
            logger.error(f"Error generating career session notes: {e}", exc_info=True)
            raise

    def build_domain_selection_payload(
        self,
        domain_context: Dict[str, Any] = None,
        user_response: str = "",
    ) -> Dict[str, Any]:
        """Build the shared Q1/Q2 domain-selection payload for text and voice.

        Returns pre-formatted option strings plus metadata needed by both the
        realtime instructions path and text question-generation path.
        """
        recommendations = (domain_context or {}).get('recommendations', [])
        has_recommendations = len(recommendations) > 0

        print(f"Building domain selection payload | {len(recommendations)} recommendations | user_response='{user_response}'")
        print(f"Recommendations: {[rec.get('title', '') for rec in recommendations]}")
        primary_options = "\n".join([
            f"{i}. {rec.get('title', 'Unknown')} [{rec.get('match_percentage', 0)}% match]"
            for i, rec in enumerate(recommendations, 1)
        ])

        rec_titles_set = {rec.get('title', '') for rec in recommendations}
        selected_primary = None
        user_response_lower = user_response.lower().strip()
        for i, rec in enumerate(recommendations):
            title = rec.get('title', '')
            if user_response_lower == str(i + 1):
                selected_primary = title
                break
            if title.lower() in user_response_lower:
                selected_primary = title
                break

        domain_match_pct = {
            rec.get('title', ''): rec.get('match_percentage', 0)
            for rec in recommendations
        }

        if selected_primary:
            remaining_domains = [d for d in ALL_PREDEFINED_DOMAINS if d != selected_primary]
        else:
            remaining_domains = [d for d in ALL_PREDEFINED_DOMAINS if d not in rec_titles_set]

        domains_with_pct = [d for d in remaining_domains if d in domain_match_pct]
        domains_without_pct = [d for d in remaining_domains if d not in domain_match_pct]
        domains_with_pct.sort(key=lambda d: domain_match_pct.get(d, 0), reverse=True)
        remaining_domains = domains_with_pct + domains_without_pct

        secondary_lines = []
        for i, d in enumerate(remaining_domains, 1):
            if d in domain_match_pct:
                secondary_lines.append(f"{i}. {d} [{domain_match_pct[d]}% match]")
            else:
                secondary_lines.append(f"{i}. {d}")

        secondary_options = "\n".join(secondary_lines)
        none_option_number = len(remaining_domains) + 1

        return {
            'has_recommendations': has_recommendations,
            'recommendations': recommendations,
            'primary_options': primary_options,
            'secondary_options': secondary_options,
            'none_option_number': none_option_number,
            'selected_primary': selected_primary,
        }

    def build_domain_selection_phase_instructions(
        self,
        current_step: int,
        domain_context: Dict[str, Any] = None,
        user_response: str = "",
    ) -> str:
        """Build explicit shared phase instructions for Q1, Q2, and post-selection flow."""
        payload = self.build_domain_selection_payload(
            domain_context=domain_context,
            user_response=user_response,
        )
        if not payload['has_recommendations']:
            return (
                "<domain_selection_phase>\n"
                "No Stream & Subject Selection recommendations are available. "
                "Proceed directly to career exploration questions.\n"
                "</domain_selection_phase>"
            )

        if current_step >= 3:
            return (
                "<domain_selection_phase>\n"
                "IMPORTANT: Domain selection is complete. Proceed with career exploration questions only.\n"
                "- Focus all questions on specific careers within the student's chosen domain(s)\n"
                "- Do NOT ask about domain selection again\n"
                "</domain_selection_phase>"
            )

        if current_step == 0:
            return (
                "<domain_selection_phase>\n"
                "IMPORTANT: The very next question must be Q2 - PRIMARY DOMAIN SELECTION.\n"
                "After the student responds to the intro, warmly greet them and present these top domain choices exactly as shown below.\n"
                "FOR VOICE: Read each domain as a separate numbered item on its own line. Speak each one slowly with a pause between them. READ EACH ON A SEPARATE LINE - DO NOT COMBINE INTO ONE SENTENCE. Do not say the word 'option'.\n"
                "Ask: \"Which one of these domains do you most relate to? You can say the number or the name.\"\n\n"
                f"{payload['primary_options']}\n"
                "</domain_selection_phase>"
            )

        return (
            "<domain_selection_phase>\n"
            "IMPORTANT: The very next question must be Q3 - SECONDARY DOMAIN SELECTION.\n"
            "Briefly acknowledge the student's primary domain choice, then ask: \"Is there another domain that you also relate to?\"\n"
            "FOR VOICE: Read each domain as a separate numbered item on its own line. Speak each one slowly with a pause between them. READ EACH ON A SEPARATE LINE - DO NOT COMBINE INTO ONE SENTENCE. Do not say the word 'option'.\n"
            "Present these remaining domains exactly as shown below, followed by None of the above.\n"
            "The student can answer with the number, the domain name, or None of the above.\n\n"
            f"{payload['secondary_options']}\n"
            f"{payload['none_option_number']}. None of the above\n"
            "</domain_selection_phase>"
        )

    def build_initial_question_prompt(
        self,
        user_name: str = "there",
        domain_context: Dict[str, Any] = None,
        step: int = 0,
        user_response: str = "",
        language: str = 'en',
    ) -> str:
        """Build the shared text-generation prompt for Q1 or Q2."""
        payload = self.build_domain_selection_payload(
            domain_context=domain_context,
            user_response=user_response,
        )
        has_domain_results = payload['has_recommendations']

        if step == 1 and has_domain_results:
            numbered_remaining = payload['secondary_options']
            none_option_number = payload['none_option_number']

            prompt = f"""The student named {user_name} just selected their PRIMARY domain in Q1. Their response was: "{user_response}"

Now generate Q2: Ask if there's another domain they also relate to.

SHOW THESE REMAINING DOMAINS (all domains except the one they already chose):
{numbered_remaining}
{none_option_number}. None of the above

CRITICAL REQUIREMENTS:
- Acknowledge their first domain choice warmly (1 short sentence)
- Ask: "Is there another domain that you also relate to?"
- Show the COMPLETE list of remaining domains exactly as numbered above
- Include "{none_option_number}. None of the above" as the last option
- Be warm and conversational
- Use regular hyphens (-) not em dashes
- Do NOT truncate or cut off the list. Output the COMPLETE list with ALL {none_option_number} options.
- OUTPUT ONLY the response text, no quotes or prefixes

Generate your response now:"""

        elif has_domain_results:
            numbered_top_domains = payload['primary_options']
            prompt = f"""Generate a warm, personalized opening message for a student named {user_name} who has just completed their Stream & Subject Selection session.

TOP DOMAIN RECOMMENDATIONS (show ALL with percentage matches):
{numbered_top_domains}

CRITICAL REQUIREMENTS:
- Start with a warm greeting: "Hey {user_name}!"
- Briefly mention that based on their Stream & Subject Selection, here are their top domains
- List ALL of their domain recommendations exactly as the numbered list above, INCLUDING the percentage matches
- Ask: "Which one of these domains do you most relate to?"
- Be warm and conversational
- Use regular hyphens (-) not em dashes
- Do NOT truncate or cut off any part of the message. Output the COMPLETE message.
- OUTPUT ONLY the greeting text, no quotes or prefixes

Generate your personalized opening:"""

        else:
            print("[WARNING] No domain results available for initial question generation.")
            prompt = f"""Generate a warm, personalized opening message for a student named {user_name} who is about to start their Career & Degree Selection journey.

RULES:
- Start with a warm greeting using their name
- Mention you'll help them discover careers that match their unique talents
- If profile data is available, mention 1 specific impressive thing (achievement, activity, interest)
- Ask an engaging question about their interests or goals
- Keep total message under 50 words
- Be warm, encouraging, and authentic
- OUTPUT ONLY the greeting and question text

Generate your personalized opening:"""

        if language == 'hi':
            prompt += (
                "\n\n[CRITICAL Hindi Instruction: You MUST generate this response in Hindi using Devanagari script only. "
                "Translate the greeting/acknowledgment, instructions and options into natural and warm Devanagari Hindi. "
                "Ensure NO English letters or Hinglish is used. Keep the message concise (under 80 words for the main body).]"
            )
        return prompt

    # ================== Unified Prompt Builder ==================

    def build_prompt_for_step(
        self,
        step: int,
        user_response: str = "",
        messages: List[Dict[str, Any]] = None,
        user_profile: Dict[str, Any] = None,
        user_name: str = "there",
        domain_context: Dict[str, Any] = None,
        session_notes: str = "",
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
            step: Current question number (1-indexed; 1=Q1 primary domain,
                  2=Q2 secondary domain, 3+=career exploration).
            user_response: Latest user response text.
            messages: Full conversation history.
            user_profile: User profile data dictionary.
            user_name: Student's first name for personalisation.
            domain_context: Stream & Subject Selection results + domain_choices.
            session_notes: AI-generated coaching notes.

        Returns:
            dict with:
            - ``system_prompt``  – static system instructions (used by voice as-is)
            - ``dynamic_context`` – per-session dynamic context string
            - ``domain_selection_instructions`` – domain selection phase instructions (for voice overlay)
        """
        # ── Build agent guidance for steps >= 3 ──────────────────
        agent_guidance = ""
        if step >= 3:
            agent_questions = self._get_agent_questions_for_step(step)
            if agent_questions:
                agent_guidance = (
                    "\n=== AGENT QUESTION GUIDANCE ===\n"
                    "For this step, consider asking questions that help evaluate:\n"
                    + "\n".join(["- " + q for q in agent_questions[:3]])
                )

        # ── Build system prompt (static + dynamic) ───────────────
        static_prompt, dynamic_context = self.build_shared_instructions(
            user_profile=user_profile,
            domain_context=domain_context,
            current_step=step if step >= 3 else None,
            agent_guidance=agent_guidance,
            session_notes=session_notes,
            messages=messages,
            user_name=user_name,
            language=language,
        )

        # Domain selection is now handled before the session starts,
        # so no domain selection phase instructions are needed.
        domain_selection_instructions = (
            "<domain_selection_phase>\n"
            "Domain selection is complete. The student's chosen domains are provided in the domain context.\n"
            "Proceed with career exploration questions only.\n"
            "- Focus all questions on specific careers within the student's chosen domain(s)\n"
            "- Do NOT ask about domain selection again\n"
            "</domain_selection_phase>"
        )

        return {
            "system_prompt": static_prompt,
            "dynamic_context": dynamic_context,
            "domain_selection_instructions": domain_selection_instructions,
        }

    def _build_degree_filter_constraint(self, degree_filter: str) -> str:
        """Build a degree-type constraint block to inject into the recommendations prompt."""
        if degree_filter == 'ug_only':
            return (
                "\n=== DEGREE TYPE CONSTRAINT (HIGH SCHOOL STUDENT) ===\n"
                "This student is currently in HIGH SCHOOL. The 'degrees' array for EACH career recommendation\n"
                "MUST contain ONLY undergraduate (UG) degrees — e.g. B.Tech, B.S., B.A., BBA, B.Sc., B.E., B.Com.\n"
                "Do NOT include any postgraduate degrees (Masters, MBA, M.S., M.Tech, PhD, etc.).\n"
                "The student is not yet ready to consider postgraduate options.\n"
            )
        elif degree_filter == 'career_only':
            return (
                "\n=== DEGREE TYPE CONSTRAINT (CAREER REPORT ONLY) ===\n"
                "The student has requested a CAREER REPORT ONLY. The report MUST NOT contain any degree suggestions.\n"
                "The 'degrees' array for EACH career recommendation MUST be completely empty: [].\n"
                "Do NOT include any undergraduate or postgraduate degrees. Keep the list empty.\n"
            )
        elif degree_filter == 'pg_only':
            return (
                "\n=== DEGREE TYPE CONSTRAINT (POSTGRAD OPTIONS FOR UG STUDENT) ===\n"
                "This student is already enrolled in an undergraduate degree. They do NOT need UG degree suggestions.\n"
                "The 'degrees' array for EACH career recommendation MUST contain ONLY postgraduate degrees:\n"
                "  — Masters (M.S., M.A., M.Tech, M.Sc.), MBA, M.Phil, PhD, PG Diploma, etc.\n"
                "Do NOT include any undergraduate degrees (B.Tech, B.S., B.A., BBA, etc.) — the student already has one or is doing one.\n"
                "Show the full range of PG pathways relevant to the career.\n"
            )
        return ""  # 'all' — no constraint


    def _build_domain_career_focus(
        self,
        domain_context: Dict[str, Any],
        messages: List[Dict[str, Any]] = None,
    ) -> str:
        """Build domain-focused career instruction for the LLM prompt."""
        if not domain_context or not domain_context.get('recommendations'):
            return ""
        focused_domains, _ = self._get_focused_domains_context(
            domain_context, messages=messages,
            chosen_domains=domain_context.get('domain_choices'),
        )
        if not focused_domains:
            return ""
        domain_names = ", ".join(focused_domains)
        return (
            f"\nDOMAIN CAREER FOCUS: The student's focused domains are: {domain_names}.\n"
            "Your question MUST relate to specific careers within these domains.\n"
            "Ask about preferences that help distinguish between different careers in these domains\n"
            "(e.g., day-to-day tasks, work style, skills, environment, team vs solo work).\n"
            "Do NOT ask generic questions unrelated to careers in these domains."
        )

    @staticmethod
    def _extract_disability_context(user_profile: Dict[str, Any]) -> str:
        """Return a short description of any learning/physical disability in the profile.

        Returns an empty string if no disability is present (or fields indicate
        no disability / prefer not to say).
        """
        if not user_profile:
            return ""
        # Navigate nested profile structure
        profile_data = user_profile.get("profile", user_profile)
        if isinstance(profile_data, dict) and "profile" in profile_data:
            profile_data = profile_data["profile"]
        personal = profile_data.get("personalDetails", {}) or {}

        _no_learning = {"no learning difficulties", "none", "no", "n/a", "na", ""}
        _no_disability = {
            "no, i do not have any physical disability",
            "no physical disability",
            "prefer not to say",
            "none",
            "no",
            "n/a",
            "na",
            "",
        }

        learning = (personal.get("learningDifficulties", "") or "").strip()
        physical = (personal.get("physicalDisabilities", "") or "").strip()

        parts = []
        if learning and learning.lower() not in _no_learning:
            parts.append(f"Learning difficulty: {learning}")
        if physical and physical.lower() not in _no_disability:
            parts.append(f"Physical disability: {physical}")
        return "; ".join(parts)

    def _build_llm_messages(
        self,
        prompt_data: Dict[str, Any],
        step: int,
        user_response: str = "",
        messages: List[Dict[str, Any]] = None,
        user_name: str = "there",
        domain_context: Dict[str, Any] = None,
        language: str = 'en',
        user_profile: Dict[str, Any] = None,
    ) -> list:
        """Assemble the LangChain message list for an LLM call.

        Uses the content pieces from ``build_prompt_for_step`` and adds
        conversation history + the latest user response.  This is only
        needed by the text flow — the voice flow uses
        ``prompt_data['system_prompt']`` directly.
        """
        llm_messages = [
            SystemMessage(content=prompt_data["system_prompt"]),
            SystemMessage(content=prompt_data["dynamic_context"]),
        ]

        # All steps: conversation history + latest response
        for msg in (messages or []):
            if msg.get('type') == MessageType.USER:
                llm_messages.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('type') == MessageType.BOT:
                llm_messages.append(AIMessage(content=msg.get('content', '')))

        # ── Detect disability for Phase 0 injection ─────────────
        disability_ctx = self._extract_disability_context(user_profile)

        # Build step-specific instruction
        step_instruction = ""
        if step in (1, 2) and domain_context:
            # Domain motivation deep-dive phase
            chosen = domain_context.get('domain_choices', {})
            primary = chosen.get('primary_domain', '')
            secondary = chosen.get('secondary_domain', '')

            if step == 1 and disability_ctx:
                # Phase 0: disability check-in comes first
                step_instruction = (
                    f"\nPHASE 0 — DISABILITY CHECK-IN: The student's profile shows: {disability_ctx}."
                    "\nThis is the very FIRST question of the conversation (after the intro)."
                    "\nOpen with a warm, matter-of-fact acknowledgment of their condition and ask ONE open question"
                    " about how it affects them in learning or work situations — so you can give more personalised career guidance."
                    "\nExample: 'I noticed from your profile that you have [condition]. I want to make sure I give you"
                    " the most relevant guidance — could you tell me a little about how it affects you day-to-day,"
                    " especially in learning or work situations?'"
                    "\nDo NOT present multiple-choice options. Do NOT ask about domain motivation yet — that comes after this check-in."
                    "\nBe warm and normalising. Never use words like 'limitation' or 'challenge' as the opener."
                )
            elif step == 1 and primary:
                step_instruction = (
                    f"\nDOMAIN MOTIVATION DEEP-DIVE: The student chose '{primary}' as their primary domain."
                    "\nAsk an open-ended question about WHY they chose this domain. Dig into the personal story — "
                    "was it a specific experience, a person who inspired them, a subject they loved, something they "
                    "built or tried, or just a strong gut feeling? Do NOT present multiple-choice options. "
                    "Let them express themselves freely."
                )
            elif step == 2 and disability_ctx:
                # Phase 0 Q2: follow-up on the disability (or skip to domain motivation if Q1 answer was positive)
                step_instruction = (
                    f"\nPHASE 0 — DISABILITY FOLLOW-UP: The student has {disability_ctx}."
                    "\nReview their Q1 response carefully:"
                    "\n- If they mentioned specific impacts on their work/learning style that could affect career fit"
                    " (e.g., concentration difficulties, reading challenges, mobility constraints) — ask ONE targeted"
                    " follow-up to understand how they currently manage it or what environments work best for them."
                    "\n- If their Q1 answer was brief, positive, or indicates the condition doesn't significantly affect"
                    " their career choices — SKIP the follow-up and transition directly into Phase 1 (domain motivation)."
                    f"\nAfter Phase 0 is done (max 2 turns), naturally transition to asking about their primary domain '{primary}'."
                )
            elif step == 2 and secondary:
                step_instruction = (
                    f"\nDOMAIN MOTIVATION DEEP-DIVE: The student chose '{secondary}' as their secondary domain "
                    f"(primary was '{primary}')."
                    "\nAsk an open-ended question about what draws them to this second domain. "
                    "Explore whether they see it as complementary to their primary domain, a backup plan, "
                    "a completely different passion, or something they're curious to explore. "
                    "Do NOT present multiple-choice options. Let them express themselves freely."
                )
            elif step == 2 and not secondary:
                # No secondary domain — skip motivation and go to career focus
                step_instruction = self._build_domain_career_focus(domain_context, messages)
        else:
            step_instruction = self._build_domain_career_focus(domain_context, messages)

            content_str = f"""{user_response}

1. Ask exactly ONE focused question that probes a SINGLE dimension or preference.
2. Do NOT ask multi-part questions.
{step_instruction}
Generate your response now:"""
            if language == 'hi':
                content_str += "\n\n[CRITICAL Hindi Instruction: You MUST respond in Hindi using the Devanagari script only. Keep it natural and warm.]"
            llm_messages.append(HumanMessage(content=content_str))

        return llm_messages

    def stream_question(
        self,
        step: int,
        user_response: str = "",
        messages: List[Dict[str, Any]] = None,
        user_profile: Dict[str, Any] = None,
        user_name: str = "there",
        domain_context: Dict[str, Any] = None,
        session_notes: str = "",
        token_usage: Dict = None,
        language: str = 'en',
    ):
        """Streaming version of generate_question that yields text chunks."""
        try:
            prompt_data = self.build_prompt_for_step(
                step=step,
                user_response=user_response,
                messages=messages,
                user_profile=user_profile,
                user_name=user_name,
                domain_context=domain_context,
                session_notes=session_notes,
                language=language,
            )

            llm_messages = self._build_llm_messages(
                prompt_data, step,
                user_response=user_response,
                messages=messages,
                user_name=user_name,
                domain_context=domain_context,
                language=language,
                user_profile=user_profile,
            )

            # Track token usage (note: streaming tokens are tracked differently,
            # but for simplicity we'll record the start of the call)
            token_category = "initial_question" if step <= 2 else "next_question"
            
            for chunk in self.llm.stream(llm_messages):
                content = chunk.content
                if isinstance(content, list):
                    content = "".join([
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    ])
                if content:
                    yield content

            logger.info(f"Q{step}: stream completed via unified stream_question")

        except Exception as e:
            logger.error(f"Error streaming question at step {step}: {e}", exc_info=True)
            raise

    def generate_question(
        self,
        step: int,
        user_response: str = "",
        messages: List[Dict[str, Any]] = None,
        user_profile: Dict[str, Any] = None,
        user_name: str = "there",
        domain_context: Dict[str, Any] = None,
        session_notes: str = "",
        token_usage: Dict = None,
        language: str = 'en',
    ) -> str:
        """Generate a question for any step number."""
        chunks = []
        for chunk in self.stream_question(
            step=step,
            user_response=user_response,
            messages=messages,
            user_profile=user_profile,
            user_name=user_name,
            domain_context=domain_context,
            session_notes=session_notes,
            token_usage=token_usage,
            language=language,
        ):
            chunks.append(chunk)
        
        question = "".join(chunks).strip().strip('"\'')
        return question

    def generate_initial_question(self, user_name: str = "there", user_profile: Dict[str, Any] = None, domain_context: Dict[str, Any] = None, session_notes: str = "", token_usage: Dict = None, step: int = 0, user_response: str = "", language: str = 'en') -> str:
        """Generate the first or second question (domain selection) to start the conversation.
        
        Args:
            step: 0 for Q1 (primary domain selection), 1 for Q2 (secondary domain selection)
            user_response: Student's response to Q1 (only used when step=1)
        """
        try:
            static_prompt, dynamic_context = self._build_enhanced_system_prompt(
                user_profile=user_profile,
                domain_context=domain_context,
                session_notes=session_notes,
                debug_label=f"ENHANCED SYSTEM PROMPT (generate_initial_question step={step})",
                user_name=user_name,
                language=language,
            )

            messages = [
                SystemMessage(content=static_prompt),
                SystemMessage(content=dynamic_context),
                HumanMessage(content=self.build_initial_question_prompt(
                    user_name=user_name,
                    domain_context=domain_context,
                    step=step,
                    user_response=user_response,
                    language=language,
                ))
            ]

            response = self.llm.invoke(messages)
            
            # Track token usage
            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "initial_question", usage)
            
            content = response.content
            if isinstance(content, list):
                content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
            question = content.strip()
            return question

        except Exception as e:
            logger.error(f"Error generating initial question (step={step}): {e}", exc_info=True)
            raise

    def generate_next_question(
        self,
        current_step: int,
        messages: List[Dict[str, Any]],
        user_response: str,
        user_profile: Dict[str, Any] = None,
        domain_context: Dict[str, Any] = None,
        session_notes: str = "",
        token_usage: Dict = None,
        user_name: str = "",
        language: str = 'en',
    ) -> str:
        """Generate the next question based on conversation context and agent evaluation needs"""
        try:
            # Get agent-specific question guidance for this step
            agent_questions = self._get_agent_questions_for_step(current_step)
            agent_guidance = ""
            if agent_questions:
                agent_guidance = f"""
=== AGENT QUESTION GUIDANCE ===
For this step, consider asking questions that help evaluate:
{chr(10).join(['- ' + q for q in agent_questions[:3]])}
"""
            
            # Build cache-optimized system prompt (static + dynamic split)
            # Pass messages so dynamic context can detect domain overrides
            static_prompt, dynamic_context = self._build_enhanced_system_prompt(
                user_profile=user_profile,
                domain_context=domain_context,
                current_step=current_step,
                agent_guidance=agent_guidance,
                session_notes=session_notes,
                debug_label="ENHANCED SYSTEM PROMPT (generate_next_question)",
                messages=messages,
                user_name=user_name,
                language=language,
            )
            
            # Build langchain messages with cache-optimized structure:
            # 1. Static system prompt (CACHED across all sessions)
            # 2. Dynamic per-session context (cached within session)
            # 3. Conversation history (grows with each turn)
            langchain_messages = [
                SystemMessage(content=static_prompt),       # CACHED by Azure OpenAI
                SystemMessage(content=dynamic_context),     # Per-session context
            ]
            
            # Add all previous messages as HumanMessage and AIMessage
            for msg in messages:
                if msg.get('type') == MessageType.USER:
                    langchain_messages.append(HumanMessage(content=msg.get('content', '')))
                elif msg.get('type') == MessageType.BOT:
                    langchain_messages.append(AIMessage(content=msg.get('content', '')))
            # Build domain-focused career instruction for questions after step 2
            domain_career_focus = ""
            if current_step >= 2 and domain_context and domain_context.get('recommendations'):
                focused_domains, _ = self._get_focused_domains_context(
                    domain_context, messages=messages,
                    chosen_domains=domain_context.get('domain_choices'),
                )
                if focused_domains:
                    domain_names = ", ".join(focused_domains)
                    domain_career_focus = f"""
DOMAIN CAREER FOCUS: The student's focused domains are: {domain_names}.
Your question MUST relate to specific careers within these domains.
Ask about preferences that help distinguish between different careers in these domains
(e.g., day-to-day tasks, work style, skills, environment, team vs solo work).
Do NOT ask generic questions unrelated to careers in these domains."""

            # Add the latest user response with explicit instruction for acknowledgment
            langchain_messages.append(HumanMessage(content=f"""{user_response}

1. Ask exactly ONE focused question that probes a SINGLE dimension or preference.
2. Do NOT ask multi-part questions.
{domain_career_focus}
Generate your response now:"""))

            response = self.llm.invoke(langchain_messages)
            
            # Track token usage
            if token_usage is not None:
                usage = self._extract_token_usage(response)
                self.track_token_usage(token_usage, "next_question", usage)
            
            content = response.content
            if isinstance(content, list):
                content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
            question = content.strip()
            
            # Clean up the response
            question = question.strip('"\'')
            if len(question) > 500:
                question = question[:500]
            
            return question

        except Exception as e:
            logger.error(f"Error generating next question: {e}", exc_info=True)
            raise

    def generate_recommendations(self, messages: List[Dict[str, Any]], user_profile: Dict[str, Any] = None, domain_context: Dict[str, Any] = None, token_usage: Dict = None, degree_filter: str = 'all') -> List[Dict[str, Any]]:
        """Generate career recommendations based on the full conversation, user profile, Stream & Subject Selection results, and 10-agent evaluation.
        
        Recommendations are constrained to careers within the student's top 2
        domains (or domains they explicitly chose/overrode during conversation).
        Careers the student explicitly expressed disinterest in are excluded via prompt instructions.
        """
        try:
            # Build conversation transcript
            transcript_lines = []
            for msg in messages:
                role = "Student" if msg.get('type') == MessageType.USER else "Coach"
                content = msg.get('content', '')
                transcript_lines.append(f"{role}: {content}")
            transcript = "\n".join(transcript_lines)
            
            # Format user profile for context
            user_profile_context = format_user_profile_context(user_profile or {})
            
            # Format domain context
            domain_ctx = self.format_domain_context_for_prompt(domain_context or {})
            
            # Use pre-computed static agent evaluation context (module-level constant)
            agent_context = STATIC_AGENT_EVALUATION_CONTEXT

            # Get focused domains (top 2 or student-overridden) and their career lists
            domain_choices = (domain_context or {}).get('domain_choices', {})
            focused_domains, focused_careers_ctx = self._get_focused_domains_context(
                domain_context or {}, messages=messages,
                chosen_domains=domain_choices,
            )
            
            # Build the domain constraint block for the prompt
            domain_constraint = ""
            if focused_domains:
                domain_names = ", ".join(focused_domains)

                # Use pre-computed career_references if available
                if domain_choices.get('career_references'):
                    career_examples_str = "\n".join(
                        f"  - {c}" for c in domain_choices['career_references'][:20]
                    )
                else:
                    career_examples = []
                    for domain in focused_domains:
                        careers = DOMAIN_CAREER_MAPPING.get(domain, [])
                        if careers:
                            career_examples.append(f"  {domain}: {', '.join(careers[:8])}")
                    career_examples_str = "\n".join(career_examples) if career_examples else "See domain career mapping above."

                # Use pre-computed hybrid_career_references if available
                hybrid_careers_str = ""
                hybrid_refs = domain_choices.get('hybrid_career_references', [])
                if hybrid_refs:
                    hybrid_careers_str = (
                        "\n\nHYBRID / CROSS-DOMAIN CAREERS (intersection of the student's two domains):\n"
                        + ", ".join(hybrid_refs)
                        + "\nThese hybrid careers are especially strong fits — prioritise them in recommendations."
                    )

                domain_constraint = f"""
=== CRITICAL DOMAIN CONSTRAINT ===
The student's focused domains are: {domain_names}

ALL 5 career recommendations MUST be specific careers within these domains.
Example careers in these domains (not exhaustive - you may suggest any career that belongs to these domains):
{career_examples_str}
{hybrid_careers_str}

Do NOT recommend careers outside these domains.
If the student explicitly chose or overrode domains during conversation, honour those choices.
Each recommendation must clearly tie back to one of these focused domains.
"""

            # Create the recommendations prompt with agent-based evaluation
            # Dynamic per-session data goes in a separate SystemMessage
            user_prompt = f"""=== USER PROFILE DATA ===
{user_profile_context}

{domain_ctx}
{domain_constraint}
{self._build_degree_filter_constraint(degree_filter)}
=== CAREER EVALUATION DIMENSIONS ===
{agent_context}

=== CONVERSATION TRANSCRIPT (Career & Degree Selection Session) ===
{transcript}

TASK:
Using the 10-dimensional evaluation framework, generate exactly 5 career recommendations in STRICT JSON format.
{"IMPORTANT: All recommendations MUST be careers within: " + ", ".join(focused_domains) + ". Do NOT recommend careers outside these domains." if focused_domains else ""}

IMPORTANT — EXCLUSION CHECK:
Before generating recommendations, carefully review the conversation transcript above. If the student has explicitly expressed disinterest in, reluctance toward, or rejection of any specific career or role (e.g., "I don't want to be a doctor", "accounting isn't for me", "I want to stay away from sales"), you MUST NOT include that career or closely similar roles in your 5 recommendations. Absence of mention is NOT rejection — only exclude careers the student clearly said they do not want.

For each career, you must:
1. Evaluate through ALL 10 assessment perspectives
2. Calculate weighted match_percentage using assessment weights
3. Include agent_scores with individual evaluations
4. Ground recommendations in domain results, profile data, and conversation
5. Personalize skill_gaps: The 5 skill gaps MUST NOT be generic. They must be highly personalized and derived from the student's PROFILE (e.g., current degree, projects, activities, school background) and the student's actual responses/silences in the CONVERSATION. For example, if they are studying BSBE, write 'Python coding depth beyond your BSBE coursework', not just 'Python coding'. If they have done a project in React, but the career requires backend, write 'Backend API integration beyond your frontend React project', not 'backend development'. Every gap must feel custom-written for this specific student's background so they immediately recognize it as their actual gap.


Each item MUST include:

{{
  "career_title": "Specific Job Title",
  "salary_range": "$XX,000 - $XX,000",
  "match_percentage": 0-100 (weighted average from all agents),
  "required_skills": ["skill1", "skill2", "skill3"],
  "next_steps": ["actionable exploration step (NO degree/program recommendations)", "hands-on activity or project", "networking or mentorship step"],
  "description": "Clear day-to-day explanation for the role",
  "why_recommended": "Synthesis of evaluation dimensions + domain results + conversation insights",
  "alignment_points": [
    "Personality fit: [personality/fit insight]",
    "Market viability: [market viability insight]",
    "Values alignment: [lifestyle alignment insight]",
    "Domain: [domain connection]",
    "Conversation: [quote/insight from student]"
  ],
  "feasibility": {{
    "level": "High | Medium | Low",
    "reason": "1-2 sentence explanation citing specific factors from this student's actual profile, education, location, skills, or constraints."
  }},
  "skill_gaps": [
    "Most critical gap — highly personalized (e.g., 'Python coding depth beyond your BSBE coursework')",
    "Second gap — specific tool/method missing (e.g., 'Backend API integration beyond your frontend React project')",
    "Third gap — derived from responses or silences in the conversation",
    "Fourth gap — tied to what career needs vs. their actual background",
    "Fifth gap — least critical but still career-relevant delta"
  ],
  "agent_scores": {{
    "psychologist": 0-100,
    "market_reality": 0-100,
    "skills_gap": 0-100,
    "constraint": 0-100,
    "values": 0-100,
    "automation_risk": 0-100,
    "trajectory": 0-100,
    "regret_minimization": 0-100,
    "black_swan": 0-100
  }},
  "degree_pathways": "REMOVED - now embedded in each degree object",
  "degree_fit_scores": "REMOVED - now embedded in each degree object",
  "degree_decision_filter": "REMOVED - now embedded in each degree object",
  "degrees": [
    {{"degree": "B.S. in Economics", "fit_score": 4, "fit_reason": "Matches analytical strengths and market interest", "pathway": {{"rank": "Core Path", "label": "Strategy & Analytics Track", "why": "Most direct route given your data and economics interests"}}, "decision_filter": {{"condition": "you enjoy analysis, data, and economics thinking"}}}},
    {{"degree": "BBA", "fit_score": 3, "fit_reason": "Strong for leadership-oriented students", "pathway": {{"rank": "Alternate Path", "label": "Business Leadership Track", "why": "Good option if you prefer management over analytics"}}, "decision_filter": {{"condition": "you prefer leadership and strategy"}}}},
    {{"degree": "B.A. in Psychology", "fit_score": 3, "fit_reason": "Unique edge for human-centered roles", "pathway": {{"rank": "Differentiated Path", "label": "Behavioral Science Track", "why": "Stands out for consulting and UX-adjacent careers"}}, "decision_filter": {{"condition": "you are fascinated by human behavior and decision-making"}}}}
  ]
}}

AGENT SCORING GUIDELINES:
- Psychological Fit: High if personality matches role demands, low burnout risk
- Market Reality: High if strong job demand, growing field
- Skills Gap: High if student has relevant skills or can realistically acquire them
- Constraints: High if financially/logistically feasible for the student
- Values: High if career aligns with stated values and lifestyle preferences
- Automation Risk: High if career has strong human moat, low AI exposure
- Trajectory: High if clear progression path, realistic timeline
- Regret Minimization: High if skills are portable, easy to pivot
- Black Swan: High if unconventional upside potential exists

Output ONLY a JSON object with a "recommendations" array. Ensure valid JSON."""

            # PROMPT CACHE OPTIMIZATION: Static recommendations prompt as first message
            # Dynamic per-session data (profile, transcript) as second message
            langchain_messages = [
                SystemMessage(content=RECOMMENDATIONS_SYSTEM_PROMPT),  # CACHED by Azure OpenAI
                HumanMessage(content=user_prompt)
            ]

            # Use structured output with Pydantic model
            structured_llm = self.recommendations_llm.with_structured_output(CareerRecommendationsOutput, include_raw=True)
            raw_result = structured_llm.invoke(langchain_messages)
            
            # Extract parsed result and track tokens from raw response
            if isinstance(raw_result, dict) and 'parsed' in raw_result:
                result = raw_result['parsed']
                raw_response = raw_result.get('raw')
                if token_usage is not None and raw_response is not None:
                    usage = self._extract_token_usage(raw_response)
                    self.track_token_usage(token_usage, "recommendations", usage)
            else:
                result = raw_result
            
            # Convert Pydantic models to dictionaries (validation already done by Pydantic)
            recommendations = [rec.model_dump() for rec in result.recommendations]
            
            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            raise

    async def astream_question(
        self,
        step: int,
        user_response: str,
        messages: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        user_name: str,
        domain_context: Dict[str, Any],
        session_notes: str = "",
        token_usage: Dict = None,
        language: str = 'en',
    ):
        """Async stream a conversational response for the next career discovery question."""
        self._initialize_llm()
        if token_usage is None:
            token_usage = {}

        system_prompt, dynamic_context = self.build_shared_instructions(
            user_profile=user_profile,
            domain_context=domain_context,
            current_step=step,
            session_notes=session_notes,
            messages=messages,
            user_name=user_name,
            language=language
        )

        history_msgs = []
        for m in messages:
            if m['type'] == 'user':
                history_msgs.append(HumanMessage(content=m['content']))
            else:
                history_msgs.append(AIMessage(content=m['content']))
        
        langchain_messages = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=dynamic_context),
            *history_msgs,
            HumanMessage(content=user_response)
        ]

        async for chunk in self.llm.astream(langchain_messages):
            if hasattr(chunk, 'content') and chunk.content:
                content = chunk.content
                if isinstance(content, list):
                    content = "".join([
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    ])
                yield content

    def stream_question(
        self,
        step: int,
        user_response: str,
        messages: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        user_name: str,
        domain_context: Dict[str, Any],
        session_notes: str = "",
        token_usage: Dict = None,
        language: str = 'en',
    ):
        """Stream a conversational response for the next career discovery question."""
        self._initialize_llm()
        if token_usage is None:
            token_usage = {}

        # 1. Build canonical instructions (static prompt + dynamic context)
        # This replaces the manual formatting that was causing KeyErrors
        system_prompt, dynamic_context = self.build_shared_instructions(
            user_profile=user_profile,
            domain_context=domain_context,
            current_step=step,
            session_notes=session_notes,
            messages=messages,
            user_name=user_name,
            language=language
        )

        # 2. Build conversation history
        history_msgs = []
        for m in messages:
            if m['type'] == 'user':
                history_msgs.append(HumanMessage(content=m['content']))
            else:
                history_msgs.append(AIMessage(content=m['content']))
        
        # 3. Build full message list for LangChain
        # We send the dynamic context as a separate system message to improve prompt caching consistency
        langchain_messages = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=dynamic_context),
            *history_msgs,
            HumanMessage(content=user_response)
        ]

        # 4. Stream from LLM
        for chunk in self.llm.stream(langchain_messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content

    def build_conversation_history(self, messages: List[Dict[str, Any]]) -> str:
        """Utility for non-streaming usage or prompt injection"""
        formatted = []
        for m in messages:
            role = "Student" if m['type'] == 'user' else "Coach"
            formatted.append(f"{role}: {m['content']}")
        return "\n".join(formatted)

# Global service instance
career_langchain_service = CareerDiscoveryLangChainService()
