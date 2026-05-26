"""
Simulated User Agent for Career & Degree Selection Testing

This module provides an LLM-based agent that simulates a student responding to
Career & Degree Selection questions. The agent maintains persona consistency throughout
the conversation while generating dynamic, varied responses each time.

The agent is aware of the student's Stream & Subject Selection results so it can
realistically answer the first two domain-selection questions (Q1: primary
domain, Q2: secondary domain) before moving into career exploration.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Persona behavioral traits — personality and speaking style enhancements
# layered ON TOP of the actual user profile from the database.
PERSONA_ENHANCEMENTS = {
    "arts": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Expressive and emotionally intelligent
- You see beauty and creative potential in everyday things
- You're introspective and enjoy deep conversations about meaning and aesthetics
- You're curious about how technology and art intersect
- You care about meaningful work that lets you express ideas""",
        "speaking_style": "expressive, uses metaphors, emotionally authentic, reflective, talks about creative fulfillment"
    },

    "engineering": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Analytical and systematic in your thinking
- You enjoy breaking down complex problems into smaller parts
- You're collaborative and enjoy working on team projects
- You believe in building things that have real-world impact
- You're excited about emerging technologies and innovations""",
        "speaking_style": "logical, precise, uses technical terms appropriately, enthusiastic about problem-solving and building things"
    },

    "entrepreneurship": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Driven, ambitious, and always thinking about scale
- You see opportunities where others see problems
- You're comfortable with ambiguity and calculated risk-taking
- You're a natural leader who inspires and motivates others
- You think about career paths in terms of impact and freedom""",
        "speaking_style": "confident, strategic, uses business vocabulary naturally, talks about impact, scale, and independence"
    },

    "science": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Deeply curious and driven by understanding "why" things work
- You find elegance and beauty in scientific concepts
- You're patient and persistent in your pursuits
- You enjoy discussing deeper implications of ideas
- You think about careers that let you explore and discover""",
        "speaking_style": "thoughtful, uses scientific reasoning, philosophical, expresses wonder about nature and discovery"
    },

    "healthcare": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Empathetic and compassionate — you genuinely care about people's wellbeing
- You're detail-oriented and methodical
- You're a good listener who makes people feel comfortable
- You want to make a tangible difference in people's lives
- You think about career paths with direct human impact""",
        "speaking_style": "caring, attentive, talks about helping people, mentions patient care and community health"
    },

    "default": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Genuine and thoughtful in your responses
- Curious about exploring your interests and future career
- Open to discussing different career possibilities""",
        "speaking_style": "natural, authentic, age-appropriate"
    }
}


class SimulatedCareerUserAgent:
    """
    An LLM-powered agent that simulates a student responding to Career & Degree Selection questions.

    The agent uses the ACTUAL user profile from the database as the foundation,
    Stream & Subject Selection results for realistic domain-selection answers,
    and only adds persona-based personality traits on top.
    """

    def __init__(
        self,
        persona: str = "arts",
        user_profile: Dict[str, Any] = None,
        domain_context: Dict[str, Any] = None,
    ):
        """
        Initialize the simulated career user agent.

        Args:
            persona: The persona type for personality enhancement
            user_profile: The actual user profile data from the database
            domain_context: Stream & Subject Selection results (recommendations, messages)
                            so the agent can answer Q1/Q2 domain-selection questions
        """
        self.persona = persona
        self.user_profile = user_profile or {}
        self.domain_context = domain_context or {}
        self.conversation_history: List[Dict[str, str]] = []
        self._llm = None
        self._is_initialized = False

        # Get persona enhancements (only personality traits, not background)
        if persona not in PERSONA_ENHANCEMENTS:
            logger.warning(f"Unknown persona '{persona}', using default")
            persona = "default"

        self.persona_data = PERSONA_ENHANCEMENTS.get(persona, PERSONA_ENHANCEMENTS["default"])

    def _initialize_llm(self):
        """Initialize the LLM for generating responses."""
        if self._is_initialized:
            return

        try:
            from utils.azure_openai import create_azure_chat_openai
            self._llm = create_azure_chat_openai(temperature=0.8, max_tokens=500)
            self._is_initialized = True
            logger.info("SimulatedCareerUserAgent initialized with Azure OpenAI")
        except Exception as e:
            logger.error(f"Failed to initialize SimulatedCareerUserAgent LLM: {e}")
            raise

    @property
    def llm(self):
        """Get the LLM, initializing if needed."""
        if not self._is_initialized:
            self._initialize_llm()
        return self._llm

    def _format_domain_results_for_prompt(self) -> str:
        """Format Stream & Subject Selection results for the system prompt so the agent
        can realistically answer domain-selection questions (Q1/Q2)."""
        recs = self.domain_context.get("recommendations", [])
        if not recs:
            return "No Stream & Subject Selection recommendations available yet."

        lines = ["Your Stream & Subject Selection results (domains recommended for you):"]
        for i, rec in enumerate(recs, 1):
            title = rec.get("title", "Unknown")
            match = rec.get("match_percentage", "?")
            explanation = rec.get("explanation", "")
            lines.append(f"  {i}. {title} ({match}% match) — {explanation[:120]}")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the simulated career-discovery student."""
        from utils.profile_formatting import format_user_profile_context
        user_profile_section = format_user_profile_context(self.user_profile)
        domain_results_section = self._format_domain_results_for_prompt()

        return f"""You are roleplaying as a student in a Career & Degree Selection conversation. Stay completely in character. Answer in at maximum 3 sentences.

=== YOUR ACTUAL PROFILE (PRIMARY — USE THIS) ===
{user_profile_section}

=== YOUR Stream & Subject Selection RESULTS ===
{domain_results_section}

=== PERSONALITY ENHANCEMENTS (SECONDARY — ONLY FOR CONVERSATION STYLE) ===
{self.persona_data['personality_traits']}

CRITICAL RULES:
1. Your profile above is YOUR REAL background — use ONLY the information provided there
2. Do NOT invent achievements, awards, or experiences not in your profile
3. Do NOT confuse yourself with any famous person or celebrity
4. If asked about something not in your profile, say you haven't done that or are still exploring
5. The personality traits above only affect HOW you speak, not WHAT you've done

DOMAIN SELECTION RULES (for the first two questions):
1. When asked to choose your PRIMARY domain, pick the domain you're most excited about from your Stream & Subject Selection results above
2. When asked to choose a SECONDARY domain, pick a DIFFERENT domain from the results that also interests you
3. Refer to domains by their exact names from the results above
4. Be enthusiastic and explain briefly why you chose that domain

CAREER CONVERSATION RULES:
1. Respond naturally and authentically based on YOUR profile above
2. Keep responses concise (2-4 sentences typically)
3. Reference ONLY your actual background, interests, and achievements from the profile
4. Be consistent with previous answers in this conversation
5. Use the speaking style: {self.persona_data['speaking_style']}
6. When discussing career preferences, ground them in your actual profile interests
7. NEVER break character or mention that you're an AI
8. NEVER give meta-commentary about the conversation
9. Respond as if you're genuinely exploring your future career with a counselor

OUTPUT FORMAT:
- Just provide the student's response directly
- No quotation marks around the response
- No "Student:" or similar prefixes
- No explanations or meta-text"""

    def generate_response(self, question: str) -> str:
        """
        Generate a dynamic response to a Career & Degree Selection question.

        Args:
            question: The question from the Career & Degree Selection system

        Returns:
            A natural, persona-consistent response
        """
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            # Build messages for LLM
            messages = [SystemMessage(content=self._build_system_prompt())]

            # Add conversation history for context
            for exchange in self.conversation_history[-6:]:  # Last 6 exchanges for context
                if exchange.get("role") == "counselor":
                    messages.append(HumanMessage(content=f"Counselor asks: {exchange['content']}"))
                elif exchange.get("role") == "student":
                    messages.append(AIMessage(content=exchange["content"]))

            # Add current question
            messages.append(HumanMessage(content=f"Counselor asks: {question}\n\nRespond as the student:"))

            # Generate response
            response = self.llm.invoke(messages)

            # Extract content
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    [part.get("text", "") if isinstance(part, dict) else str(part) for part in content]
                )

            response_text = content.strip()

            # Clean up any accidental prefixes
            prefixes_to_remove = [
                "Student:",
                "Student Response:",
                '"',
                "'",
            ]
            for prefix in prefixes_to_remove:
                if response_text.startswith(prefix):
                    response_text = response_text[len(prefix) :].strip()

            # Remove trailing quotes if present
            if response_text.endswith('"'):
                response_text = response_text[:-1].strip()

            # Store in conversation history
            self.conversation_history.append({"role": "counselor", "content": question})
            self.conversation_history.append({"role": "student", "content": response_text})

            return response_text

        except Exception as e:
            logger.error(f"Error generating simulated career response: {e}")
            return self._fallback_response(question)

    def _fallback_response(self, question: str) -> str:
        """Generate a fallback response if LLM fails."""
        question_lower = question.lower()

        # Get interests from actual user profile
        interests = self.user_profile.get("interests") or self.user_profile.get("hobbies") or []
        if isinstance(interests, str):
            interests = [i.strip() for i in interests.split(",")]

        interest_1 = interests[0] if len(interests) > 0 else "my studies"
        interest_2 = interests[1] if len(interests) > 1 else "exploring new things"

        # Get top domain from domain context for domain-selection fallbacks
        recs = self.domain_context.get("recommendations", [])
        top_domain = recs[0].get("title", "the first domain") if recs else "the domain that interests me most"
        second_domain = recs[1].get("title", "another domain") if len(recs) > 1 else "a complementary field"

        fallbacks = {
            "primary domain": f"I'd like to choose {top_domain} as my primary domain — it aligns really well with my interests.",
            "secondary domain": f"For my secondary domain, I'll go with {second_domain}. I think it complements my primary choice nicely.",
            "which domain": f"I'm most drawn to {top_domain} because it connects with {interest_1}.",
            "career": f"I'm really interested in careers related to {interest_1}, maybe something that lets me combine different interests.",
            "work environment": "I think I'd thrive in an environment where I can collaborate with others but also have time to focus deeply.",
            "salary": "Salary is important, but I care more about doing meaningful work that I'm excited about every day.",
            "skills": f"I think my experience with {interest_1} and {interest_2} gives me a good foundation, but I'm always eager to learn more.",
            "day in the life": "I'd love a career where no two days are exactly the same — variety and challenge keep me engaged.",
            "five years": f"In five years I'd like to be well-established in my field, making a real impact with {interest_1}.",
        }

        for keyword, response in fallbacks.items():
            if keyword in question_lower:
                return response

        return "That's a great question. I think it really depends on the context, but I'm drawn to roles that let me apply my strengths and grow professionally."

    def reset_conversation(self):
        """Reset the conversation history for a new session."""
        self.conversation_history = []
