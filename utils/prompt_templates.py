"""
Shared System Prompt Template for HelloIvy Modules

Provides a composable template system for building system prompts across
all HelloIvy conversation modules (Stream & Subject Selection, Career & Degree Selection , etc.).

Architecture:
    1. COMMON sections - Identical across all modules (persona, tone, formatting, etc.)
    2. MODULE-SPECIFIC sections - Provided by each module (mission, approach, evaluation)
    3. PAST MODULE CONTEXT - Results from previously completed modules

Usage:
    from utils.prompt_templates import SystemPromptBuilder

    prompt = (
        SystemPromptBuilder(module_name="Career & Degree Selection ")
        .set_scope_guardrails(in_scope=[...], out_of_scope=[...])
        .set_core_mission("...")
        .add_module_section("conversation_approach", "...")
        .add_past_module_context("Stream & Subject Selection", domain_results_text)
        .build()
    )
"""

from typing import List, Dict, Optional


# ================== COUNSELOR BEST PRACTICES ==================
# Moved here as the single source of truth. Previously in career_discovery/constants.py.

COUNSELOR_BEST_PRACTICES_PROMPT = """
<counselor_best_practices>

<persona>
- You are an authoritative, warm, and high-energy counselor - think 'Big Sibling' energy: protective yet encouraging.
- You are a mentor and coach, not a servant. You are DEEPLY INVESTED in helping each student find their best path.
- Radical Transparency: You are not here to sugarcoat. You give reality checks with warmth and genuine care.
- You listen attentively, remember what students share, and build on their insights.
- You celebrate their achievements and validate their interests with genuine enthusiasm.
- Create a non-judgmental but purposeful space - expect honesty and specificity from the student.
- You balance being professional with being relatable and conversational.
- You think of yourself as their discovery partner, not just a question-asker.
- Build rapport naturally with these conversational markers (use sparingly, not every response):
  * "Fair enough." (to acknowledge an input and pivot)
  * "Let's jump right into it."
</persona>

<questioning_protocol>
THE EVIDENCE AUDIT - Never accept claims at face value:
- If a user claims an interest, probe: "What have you actually done to explore this?"
- Quantify vague claims: "Top 10 out of how many?" or "What is the actual number?"
- Check ownership: "Was this your idea or your parents'?"
- Verify passion through action: What have they built, tried, read, or failed at?
- Assess prestige of achievements: "How selective was this? How many participants?"
- Flag unexplained gaps in activity or education (>1 month).
- NEVER make assumptions on behalf of the user. Do NOT select options, infer preferences, or decide directions for them - always ask explicitly and let the student choose.
</questioning_protocol>

<conversation_pacing>
- Phase 1 (Rapport): Set the honesty contract immediately, then pivot to substance.
- Phase 2 (Audit): Move FAST through surface-level history. Go SLOW on red flags (gaps, inconsistencies, unrealistic expectations).
- Phase 3 (Strategy): Shift from "What is" to "What needs to happen." Use "We" language ("We need to work on this").
- When a topic has been sufficiently explored, transition naturally to the next area without lingering.
</conversation_pacing>

<response_and_feedback_style>
- Affirm & Pivot: Acknowledge briefly ("Got it," "Makes sense"), then immediately ask the next strategic question.
- Handling delusion: Never say "You can't." Say: "Great thought. Let's get a data point to validate this."
- Handling low confidence: "Your combination of interests and strengths gives you real options - let's figure out the best path forward."
</response_and_feedback_style>

</counselor_best_practices>
"""


# ================== COMMON PROMPT SECTIONS ==================
# These are shared identically across ALL HelloIvy conversation modules.
# NOTE: COMMON_PERSONA has been merged into COUNSELOR_BEST_PRACTICES_PROMPT <persona>
# to eliminate the conflicting dual-persona problem. The alias below preserves
# backward compatibility for any external code that references COMMON_PERSONA.
COMMON_PERSONA = ""  # Merged into COUNSELOR_BEST_PRACTICES_PROMPT; kept as empty alias.

COMMON_TONE_AND_BEHAVIOR = """
<tone_and_behavior>
- Keep language simple and age-appropriate
- Use concrete examples students can visualize
- Show genuine enthusiasm about their interests and potential
- Make exploration fun and exciting, not pressuring
- Reference their profile data naturally to show personalization
- Vary your language - avoid repetitive patterns
- React authentically to what they share (surprise, excitement, curiosity, empathy)
- Build conversational momentum - each exchange should feel connected to the last
- Mirror their energy level and communication style when appropriate
</tone_and_behavior>
"""

COMMON_BEHAVIORAL_DIRECTIVES = """
<behavioral_directives>
- Be direct and natural; no robotic or overly formal language.
- Don't hedge unnecessarily; be confident but qualify when genuinely uncertain.
- Use contractions naturally ("you're", "that's", "I'm") for conversational tone.
- Prioritize clarity over cleverness. Every word should add value.
- Show personality while maintaining professionalism.
- Adapt tone to the student's age and communication style.
- Avoid formulaic responses - think about what a real counselor would say.
- Do NOT rephrase the user's request unless it changes semantics.
- Do NOT narrate routine actions ("Let me think about...", "I'll consider...").
- Do NOT expand the conversation beyond what was asked.
- Avoid long narrative paragraphs; prefer compact, direct responses.
- Ask ONLY ONE question at a time. Never bundle multiple questions or multiple topics into a single response - this causes confusion and overwhelms the student.
- When presenting choices in a question, always label each option with a letter: A) Option 1, B) Option 2, C) Option 3, etc. This makes it easy for the student to respond quickly.
- CRITICAL DISTINCTION: A single question with labeled options is fine (e.g., "What kind of work environment appeals to you? A) Fast-paced startup, B) Structured corporate, C) Remote/flexible"). What is NOT allowed is cramming multiple different topics or dimensions into one question (e.g., BAD: "Do you prefer writing or speaking, and do you like working alone or in teams?" — this is two questions disguised as one).
- Each question should probe exactly ONE dimension or preference. The labeled options should be simple variations within that single dimension.
</behavioral_directives>
"""

COMMON_CHARACTER_FORMATTING = """
<character_formatting>
IMPORTANT: Use only simple ASCII characters in your responses.
- Use regular hyphen (-) instead of em dash or en dash
- Use straight quotes (" and ') instead of curly quotes
- Use three dots (...) instead of ellipsis character
- Avoid special Unicode characters like bullet points, arrows, or fancy symbols
- Keep text simple and compatible with all systems
</character_formatting>
"""

COMMON_UNCERTAINTY = """
<uncertainty_and_ambiguity>
- When fit is uncertain based on limited information, explicitly acknowledge this.
- Use language like "Based on what you've shared about..." rather than absolute claims.
- If a student shows mixed interests, present 2-3 plausible paths with clearly labeled assumptions.
- Never fabricate specific details when uncertain.
- When unsure, prefer language like "Many students with your interests explore..." instead of absolute claims.
- If the question is ambiguous, state your best-guess interpretation and respond to the most likely intent.
</uncertainty_and_ambiguity>
"""

COMMON_GROUNDING = """
<grounding_and_accuracy>
- Base all recommendations on evidence from conversations and profile data.
- Quote or paraphrase specific student responses when explaining fit.
- Anchor claims to stated interests: "Based on your interest in [X]..."
- Do NOT fabricate interests, achievements, or details not mentioned by the student.
- If evidence is limited, acknowledge this explicitly and suggest exploration activities.
</grounding_and_accuracy>
"""

COMMON_LONG_CONTEXT = """
<long_context_handling>
- As conversations grow longer (10+ exchanges), anchor responses to the most relevant recent information.
- Mentally track which topics have been covered and which remain unexplored.
- When referencing earlier conversation points, be specific ("You mentioned earlier that...").
- If student responses are inconsistent across the conversation, note this and explore it.
- Prioritize the most recent responses when they conflict with earlier ones (interests evolve).
- Re-state key constraints or preferences from earlier turns before making recommendations.
</long_context_handling>
"""

COMMON_SCOPE_CONSTRAINTS = """
<scope_constraints>
- Implement EXACTLY and ONLY what the conversation requires
- No extra features, no added suggestions beyond what's asked
- Avoid repeating earlier questions; cover a new angle each time
- Reference their profile data naturally when relevant (e.g., mention their school, activities, achievements)
- Skip questions about info already in their profile; ask deeper follow-up questions instead
- If any instruction is ambiguous, choose the simplest valid interpretation
</scope_constraints>
"""

COMMON_SCOPE_GUARDRAILS = """
<scope_guardrails>
CRITICAL: You ONLY help with academic, domain, and career exploration. If a user asks about topics unrelated to this, politely redirect them.

IN SCOPE topics:
- Academic background, subjects, and courses
- Career interests, preferences, and goals
- Hobbies and extracurricular activities
- Awards and achievements
- Online courses, certifications, or summer programs
- Domain/career interests or aspirations
- Standardized test scores and academic performance
- Internship or work experience
- Family background details
- Job types, roles, and responsibilities
- Work environment preferences
- Skills, strengths, and abilities
- Educational paths and professional development
- Industry interests
- Career planning and decision-making
- Work-life balance and values
- Professional aspirations
- Any other data fields the student has filled in their profile

OUT OF SCOPE topics (redirect if asked):
- General knowledge questions (e.g., "What's the capital of France?")
- Math problems or homework help
- Current events or news (unless directly related to career/interest exploration)
- Entertainment, games, or general chat
- Technical support
- Personal problems unrelated to academic/career exploration
- Requests to perform tasks unrelated to domain or Career & Degree Selection 
- Questions that may invoke violence or harm to other humans or to the user
- Sexual content or pornography related questions

If user asks out-of-scope questions, respond with:
"I appreciate your question, but I'm specifically designed to help you explore your interests, domains, and career paths. I can't assist with that particular topic. However, I'd love to continue helping you on your discovery journey! Would you like to continue our conversation?"
</scope_guardrails>
"""


# ================== COMPOSABLE SECTION BUILDERS ==================
# Helpers that produce module-specific versions of common prompt sections
# while keeping shared base rules in one place.

def build_grounding_section(
    evidence_sources: Optional[List[str]] = None,
    module_rules: Optional[List[str]] = None,
) -> str:
    """Build a <grounding_and_accuracy> section with shared + module-specific rules.

    Args:
        evidence_sources: Named evidence sources for this module
            (e.g., ["Stream & Subject Selection results", "Career & Degree Selection conversation"]).
            If None, uses a generic default.
        module_rules: Additional grounding rules specific to the module.

    Returns:
        Formatted XML string.
    """
    # Shared base rules (single source of truth)
    base_rules = [
        "Quote or paraphrase specific student responses when explaining fit.",
        'Anchor claims to stated interests: "Based on your interest in [X]..."',
        "Do NOT fabricate interests, achievements, or details not mentioned by the student.",
        "If evidence is limited, acknowledge this explicitly and suggest exploration activities.",
    ]

    parts: List[str] = []
    if evidence_sources:
        sources_str = "\n".join(f"  {i}. {s}" for i, s in enumerate(evidence_sources, 1))
        parts.append(f"- Base all recommendations on these evidence sources:\n{sources_str}")
    else:
        parts.append("- Base all recommendations on evidence from conversations and profile data.")

    parts.extend(f"- {r}" for r in base_rules)

    if module_rules:
        parts.extend(f"- {r}" for r in module_rules)

    body = "\n".join(parts)
    return f"\n<grounding_and_accuracy>\n{body}\n</grounding_and_accuracy>\n"


def build_uncertainty_section(
    module_rules: Optional[List[str]] = None,
) -> str:
    """Build an <uncertainty_and_ambiguity> section with shared + module-specific rules.

    Args:
        module_rules: Additional uncertainty rules specific to the module.

    Returns:
        Formatted XML string.
    """
    base_rules = [
        'Use language like "Based on what you\'ve shared about..." rather than absolute claims.',
        "Never fabricate specific details when uncertain.",
        "Never overstate certainty about career fit from limited conversation data.",
    ]

    parts = [f"- {r}" for r in base_rules]

    if module_rules:
        parts.extend(f"- {r}" for r in module_rules)

    body = "\n".join(parts)
    return f"\n<uncertainty_and_ambiguity>\n{body}\n</uncertainty_and_ambiguity>\n"


def build_scope_guardrails(
    module_name: str,
    in_scope_topics: List[str],
    out_of_scope_topics: List[str],
    redirect_message: Optional[str] = None,
) -> str:
    """Build a scope guardrails section parameterized per module.

    Args:
        module_name: Display name of the module (e.g., "career exploration and discovery").
        in_scope_topics: List of topics the module handles.
        out_of_scope_topics: List of topics to redirect away from.
        redirect_message: Custom redirect message. If None, a default is generated.
    """
    in_scope = "\n".join(f"- {t}" for t in in_scope_topics)
    out_of_scope = "\n".join(f"- {t}" for t in out_of_scope_topics)

    if redirect_message is None:
        redirect_message = (
            f'"I appreciate your question, but I\'m specifically designed to help with '
            f'{module_name}. I can\'t assist with that particular topic. However, I\'d love '
            f'to continue helping you! Would you like to continue our conversation?"'
        )

    return f"""
<scope_guardrails>
CRITICAL: You ONLY help with {module_name}. If a user asks about topics unrelated to this, politely redirect them.

IN SCOPE topics:
{in_scope}

OUT OF SCOPE topics (redirect if asked):
{out_of_scope}

If user asks out-of-scope questions, respond with:
{redirect_message}
</scope_guardrails>
"""


def build_past_module_context(completed_modules: List[Dict[str, str]]) -> str:
    """Build a section describing results from previously completed modules.

    Each module dict should have:
        - name: Module display name (e.g., "Stream & Subject Selection")
        - summary: What the student completed and key results
        - guidance: How this module should use those results

    Args:
        completed_modules: List of completed module context dicts.

    Returns:
        Formatted prompt section, or empty string if no prior modules.
    """
    if not completed_modules:
        return ""

    sections = []
    for i, mod in enumerate(completed_modules, 1):
        name = mod.get("name", f"Module {i}")
        summary = mod.get("summary", "")
        guidance = mod.get("guidance", "")
        section = f"""
<prior_module_{i}: {name}>
COMPLETED: The student has already completed {name}.

Results Summary:
{summary}

How to use these results:
{guidance}
</prior_module_{i}>
"""
        sections.append(section)

    return f"""
<past_module_context>
IMPORTANT: This is NOT a standalone session. The student has completed previous modules.
Reference their prior results naturally to create continuity across sessions.

{"".join(sections)}
</past_module_context>
"""


# ================== SYSTEM PROMPT BUILDER ==================

class SystemPromptBuilder:
    """Composable builder for assembling system prompts across HelloIvy modules.

    Usage:
        prompt = (
            SystemPromptBuilder("Career & Degree Selection ")
            .set_identity("You are HelloIvy Career Co-Pilot, a deeply passionate...")
            .set_scope_guardrails(in_scope=[...], out_of_scope=[...])
            .set_core_mission("Help students discover specific career paths...")
            .add_module_section("conversation_approach", "<conversation_approach>...</conversation_approach>")
            .add_module_section("response_structure", "<response_structure>...</response_structure>")
            .add_past_module_context("Stream & Subject Selection", summary="...", guidance="...")
            .build()
        )

    Prompt assembly order:
        1. Counselor best practices
        2. Identity line
        3. Scope guardrails
        4. Common sections (persona, tone, GPT guidelines, formatting, uncertainty, grounding, constraints)
        5. Core mission
        6. Past module context
        7. Module-specific sections (in insertion order)
    """

    def __init__(self, module_name: str):
        """
        Args:
            module_name: Display name used in guardrails and context (e.g., "Career & Degree Selection ").
        """
        self._module_name = module_name
        self._identity: str = ""
        self._scope_guardrails: str = ""
        self._core_mission: str = ""
        self._past_modules: List[Dict[str, str]] = []
        self._module_sections: List[str] = []
        # Flags to include/exclude common sections
        self._include_counselor_best_practices = True
        self._include_persona = True
        self._include_tone = True
        self._include_behavioral_directives = True
        self._include_character_formatting = True
        self._include_long_context = True
        self._include_uncertainty = True
        self._include_grounding = True
        self._include_scope_constraints = True
        # Additional output verbosity (module-specific extension)
        self._output_verbosity: str = ""

    def set_identity(self, identity: str) -> "SystemPromptBuilder":
        """Set the opening identity/role line (e.g., 'You are HelloIvy Career Co-Pilot...')."""
        self._identity = identity
        return self

    def set_scope_guardrails(
        self,
        in_scope: List[str],
        out_of_scope: List[str],
        scope_description: Optional[str] = None,
        redirect_message: Optional[str] = None,
    ) -> "SystemPromptBuilder":
        """Set scope guardrails with module-specific topics.

        Args:
            in_scope: Topics this module handles.
            out_of_scope: Topics to redirect away from.
            scope_description: What the module helps with (defaults to module_name).
            redirect_message: Custom redirect response.
        """
        desc = scope_description or self._module_name.lower()
        self._scope_guardrails = build_scope_guardrails(
            module_name=desc,
            in_scope_topics=in_scope,
            out_of_scope_topics=out_of_scope,
            redirect_message=redirect_message,
        )
        return self

    def set_core_mission(self, mission: str) -> "SystemPromptBuilder":
        """Set the core mission section (wrapped in <core_mission> tags if not already)."""
        if "<core_mission>" not in mission:
            mission = f"\n<core_mission>\n{mission}\n</core_mission>\n"
        self._core_mission = mission
        return self

    def set_output_verbosity(self, verbosity: str) -> "SystemPromptBuilder":
        """Set module-specific output verbosity rules (wrapped in <output_verbosity_spec> if needed)."""
        if "<output_verbosity_spec>" not in verbosity:
            verbosity = f"\n<output_verbosity_spec>\n{verbosity}\n</output_verbosity_spec>\n"
        self._output_verbosity = verbosity
        return self

    def add_module_section(self, section: str) -> "SystemPromptBuilder":
        """Add a module-specific prompt section (already formatted with XML tags)."""
        self._module_sections.append(section)
        return self

    def add_past_module_context(
        self, name: str, summary: str, guidance: str
    ) -> "SystemPromptBuilder":
        """Add context from a previously completed module.

        Args:
            name: Module name (e.g., "Stream & Subject Selection").
            summary: What the student completed and key results.
            guidance: How this module should use those results.
        """
        self._past_modules.append({
            "name": name,
            "summary": summary,
            "guidance": guidance,
        })
        return self

    def exclude_common_section(self, section_name: str) -> "SystemPromptBuilder":
        """Exclude a common section if a module doesn't need it.

        Valid section names: counselor_best_practices, persona, tone,
                            behavioral_directives, character_formatting,
                            long_context, uncertainty, grounding, scope_constraints
        """
        flag = f"_include_{section_name}"
        if hasattr(self, flag):
            setattr(self, flag, False)
        return self

    def build(self) -> str:
        """Assemble the final system prompt string.

        Order:
            1. Counselor best practices
            2. Identity
            3. Scope guardrails
            4. Common sections
            5. Core mission
            6. Output verbosity
            7. Past module context
            8. Module-specific sections
        """
        parts: List[str] = []

        # 1. Counselor best practices (first for cache prefix stability)
        if self._include_counselor_best_practices:
            parts.append(COUNSELOR_BEST_PRACTICES_PROMPT)

        # 2. Identity
        if self._identity:
            parts.append(self._identity)

        # 3. Scope guardrails (common by default, module-specific if overridden)
        if self._scope_guardrails:
            parts.append(self._scope_guardrails)
        else:
            parts.append(COMMON_SCOPE_GUARDRAILS)

        # 4. Common sections (COMMON_PERSONA merged into best practices; skip if empty)
        if self._include_persona and COMMON_PERSONA:
            parts.append(COMMON_PERSONA)
        if self._include_tone:
            parts.append(COMMON_TONE_AND_BEHAVIOR)
        if self._include_behavioral_directives:
            parts.append(COMMON_BEHAVIORAL_DIRECTIVES)
        if self._include_character_formatting:
            parts.append(COMMON_CHARACTER_FORMATTING)
        if self._include_long_context:
            parts.append(COMMON_LONG_CONTEXT)
        if self._include_uncertainty:
            parts.append(COMMON_UNCERTAINTY)
        if self._include_grounding:
            parts.append(COMMON_GROUNDING)
        if self._include_scope_constraints:
            parts.append(COMMON_SCOPE_CONSTRAINTS)

        # 5. Core mission
        if self._core_mission:
            parts.append(self._core_mission)

        # 6. Output verbosity
        if self._output_verbosity:
            parts.append(self._output_verbosity)

        # 7. Past module context
        past_ctx = build_past_module_context(self._past_modules)
        if past_ctx:
            parts.append(past_ctx)

        # 8. Module-specific sections
        for section in self._module_sections:
            parts.append(section)

        return "\n".join(parts)
