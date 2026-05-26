"""
Simulated User Agent for Stream & Subject Selection Testing

This module provides an LLM-based agent that simulates a student responding to
Stream & Subject Selection questions. The agent maintains persona consistency throughout
the conversation while generating dynamic, varied responses each time.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Persona behavioral traits - ONLY personality and speaking style enhancements
# These are layered ON TOP of the actual user profile from the database
# They do NOT replace user's real interests, achievements, or background
PERSONA_ENHANCEMENTS = {
    "arts": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Expressive and emotionally intelligent
- You see beauty and creative potential in everyday things
- You're introspective and enjoy deep conversations about meaning and aesthetics
- You're curious about how technology and art intersect""",
        "speaking_style": "expressive, uses metaphors, emotionally authentic, reflective"
    },

    "engineering": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Analytical and systematic in your thinking
- You enjoy breaking down complex problems into smaller parts
- You're collaborative and enjoy working on team projects
- You believe in building things that have real-world impact""",
        "speaking_style": "logical, precise, uses technical terms appropriately, enthusiastic about problem-solving"
    },

    "entrepreneurship": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Driven, ambitious, and always thinking about scale
- You see opportunities where others see problems
- You're comfortable with ambiguity and calculated risk-taking
- You're a natural leader who inspires and motivates others""",
        "speaking_style": "confident, strategic, uses business vocabulary naturally, talks about impact and scale"
    },

    "science": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Deeply curious and driven by understanding "why" things work
- You find elegance and beauty in scientific concepts
- You're patient and persistent in your pursuits
- You enjoy discussing deeper implications of ideas""",
        "speaking_style": "thoughtful, uses scientific reasoning, philosophical, expresses wonder about nature"
    },

    "healthcare": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Empathetic and compassionate - you genuinely care about people's wellbeing
- You're detail-oriented and methodical
- You're a good listener who makes people feel comfortable
- You want to make a tangible difference in people's lives""",
        "speaking_style": "caring, attentive, talks about helping people"
    },

    "default": {
        "personality_traits": """Additional personality characteristics for this conversation:
- Genuine and thoughtful in your responses
- Curious about exploring your interests and future
- Open to discussing different possibilities""",
        "speaking_style": "natural, authentic, age-appropriate"
    }
}


class SimulatedUserAgent:
    """
    An LLM-powered agent that simulates a student responding to Stream & Subject Selection questions.

    The agent uses the ACTUAL user profile from the database as the foundation,
    and only adds persona-based personality traits on top. This ensures the simulated
    responses are consistent with the real user's background, interests, and achievements.
    """

    def __init__(self, persona: str = "arts", user_profile: Dict[str, Any] = None):
        """
        Initialize the simulated user agent.

        Args:
            persona: The persona type for personality enhancement (arts, engineering, entrepreneurship, science, healthcare)
            user_profile: The actual user profile data from the database - THIS IS THE PRIMARY SOURCE
        """
        self.persona = persona
        self.user_profile = user_profile or {}
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
            logger.info("SimulatedUserAgent initialized with Azure OpenAI")
        except Exception as e:
            logger.error(f"Failed to initialize SimulatedUserAgent LLM: {e}")
            raise

    @property
    def llm(self):
        """Get the LLM, initializing if needed."""
        if not self._is_initialized:
            self._initialize_llm()
        return self._llm

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the simulated user."""
        from utils.profile_formatting import format_user_profile_context
        user_profile_section = format_user_profile_context(self.user_profile)

        return f"""You are roleplaying as a student in a Stream & Subject Selection conversation. Stay completely in character. Answer in at maximum 3 sentences.

=== YOUR ACTUAL PROFILE (PRIMARY - USE THIS) ===
{user_profile_section}

=== PERSONALITY ENHANCEMENTS (SECONDARY - ONLY FOR CONVERSATION STYLE) ===
{self.persona_data['personality_traits']}

CRITICAL RULES:
1. Your profile above is YOUR REAL background - use ONLY the information provided there
2. Do NOT invent achievements, awards, or experiences not in your profile
3. Do NOT confuse yourself with any famous person or celebrity
4. If asked about something not in your profile, say you haven't done that or are still exploring
5. The personality traits above only affect HOW you speak, not WHAT you've done

CONVERSATION RULES:
1. Respond naturally and authentically based on YOUR profile above
2. Keep responses concise (2-4 sentences typically)
3. Reference ONLY your actual background, interests, and achievements from the profile
4. Be consistent with previous answers in this conversation
5. Use the speaking style: {self.persona_data['speaking_style']}
6. NEVER break character or mention that you're an AI
7. NEVER give meta-commentary about the conversation
8. Respond as if you're genuinely exploring your future with a counselor

OUTPUT FORMAT:
- Just provide the student's response directly
- No quotation marks around the response
- No "Student:" or similar prefixes
- No explanations or meta-text"""

    def generate_response(self, question: str) -> str:
        """
        Generate a dynamic response to a Stream & Subject Selection question.

        Args:
            question: The question from the Stream & Subject Selection system

        Returns:
            A natural, persona-consistent response
        """
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            # Build messages for LLM
            messages = [SystemMessage(content=self._build_system_prompt())]

            # Add conversation history for context
            for exchange in self.conversation_history[-6:]:  # Last 6 exchanges for context
                if exchange.get('role') == 'counselor':
                    messages.append(HumanMessage(content=f"Counselor asks: {exchange['content']}"))
                elif exchange.get('role') == 'student':
                    messages.append(AIMessage(content=exchange['content']))

            # Add current question
            messages.append(HumanMessage(content=f"Counselor asks: {question}\n\nRespond as the student:"))

            # Generate response
            response = self.llm.invoke(messages)

            # Extract content
            content = response.content
            if isinstance(content, list):
                content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])

            response_text = content.strip()

            # Clean up any accidental prefixes
            prefixes_to_remove = [
                'Student:',
                'Student Response:',
                '"',
                "'",
            ]
            for prefix in prefixes_to_remove:
                if response_text.startswith(prefix):
                    response_text = response_text[len(prefix):].strip()

            # Remove trailing quotes if present
            if response_text.endswith('"'):
                response_text = response_text[:-1].strip()

            # Store in conversation history
            self.conversation_history.append({'role': 'counselor', 'content': question})
            self.conversation_history.append({'role': 'student', 'content': response_text})

            return response_text

        except Exception as e:
            logger.error(f"Error generating simulated response: {e}")
            # Fallback to a simple response
            return self._fallback_response(question)

    def _fallback_response(self, question: str) -> str:
        """Generate a fallback response if LLM fails."""
        question_lower = question.lower()
        
        # Get interests from actual user profile
        interests = self.user_profile.get('interests') or self.user_profile.get('hobbies') or []
        if isinstance(interests, str):
            interests = [i.strip() for i in interests.split(',')]
        
        interest_1 = interests[0] if len(interests) > 0 else "my studies"
        interest_2 = interests[1] if len(interests) > 1 else "exploring new things"

        fallbacks = {
            "favorite subject": f"I really enjoy {interest_1} because it challenges me to think differently.",
            "what do you enjoy": f"I spend a lot of time on {interest_1} and {interest_2}. They're both fascinating to me.",
            "how do you approach": "I usually like to understand the big picture first, then break things down into smaller parts.",
            "work environment": "I think I'd thrive in an environment where I can collaborate with others but also have time to focus deeply.",
            "career": f"I'm really interested in fields related to {interest_1}, maybe something that lets me combine different interests.",
        }

        for keyword, response in fallbacks.items():
            if keyword in question_lower:
                return response

        return "That's a great question. I think it really depends on the context, but generally I'm drawn to things that let me explore my interests deeply."

    def reset_conversation(self):
        """Reset the conversation history for a new session."""
        self.conversation_history = []
