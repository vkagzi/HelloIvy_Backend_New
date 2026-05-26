"""
Career & Degree Selection Constants
Contains structured definitions for 10 career evaluation agents and related configurations.
"""

from typing import Dict, List, Any, TypedDict
from domain_discovery.constants import DomainEnum


# ================== COUNSELOR BEST PRACTICES SYSTEM PROMPT ==================
# Canonical source is now utils/prompt_templates.py.
# Re-exported here for backward compatibility.
from utils.prompt_templates import COUNSELOR_BEST_PRACTICES_PROMPT  # noqa: F401


# ================== CAREER EVALUATION AGENTS ==================
FUTURE_CAREERS = [
    {
        "title": "Prompt Engineer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Crafting and optimizing inputs for AI models to generate specific, high-quality outputs.",
    },
    {
        "title": "AI Trainer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Specialized role focused on teaching and refining AI models to improve accuracy and ethical alignment.",
    },
    {
        "title": "Systems Security Engineer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Focused on protecting organizational systems and networks from cyber threats; identified as a high-income generator.",
    },
    {
        "title": "Cloud Architect",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Designing and managing complex cloud computing strategies and environments.",
    },
    {
        "title": "Space Laboratory Technician",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Operating experiments in microgravity for pharmaceutical development or 3D-printing human organs.",
    },
    {
        "title": "Space Mining Specialist",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Strategizing the extraction of finite resources from space bodies to meet Earth's future resource needs.",
    },
    {
        "title": "Satellite Climate Analyst",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Analyzing data from satellites to monitor global climate changes, carbon levels, and environmental hazards.",
    },
    {
        "title": "Medical Virtualist",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Healthcare professionals specialized in delivering patient care exclusively through digital and virtual platforms.",
    },
    {
        "title": "Nocturnist",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "A specialized modern healthcare role managing hospital patient care during night shifts, often utilizing remote monitoring tech.",
    },
    {
        "title": "Cancer Immunologist",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Leveraging advanced biotechnology to develop personalized immune-based treatments for cancer.",
    },
    {
        "title": "AR Content Creator",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Designing interactive layers of digital information that overlay the physical world for education or commerce.",
    },
    {
        "title": "VR Experience Designer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Building entire virtual ecosystems and immersive environments using 3D design and spatial tools.",
    },
    {
        "title": "Specialized Hardware Engineer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Designing the next generation of physical tech wearables, such as AR glasses and VR headsets.",
    },
    {
        "title": "Gaming Programmer & Designer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Developing code and creative narratives for the video game industry.",
    },
    {
        "title": "Urban Air Mobility (UAM) Specialist",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Managing the systems and infrastructure for autonomous flying taxis and delivery drones.",
    },
    {
        "title": "MaaS (Mobility as a Service) Consultant",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Designing multi-modal, shared transportation systems that integrate public and private transit on demand.",
    },
    {
        "title": "Circular Economy Battery Analyst",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Monitoring the lifecycle of lithium batteries to support reuse, remanufacture, and recycling within the EV ecosystem.",
    },
    {
        "title": "Bio-plastic Researcher",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Developing sustainable, renewable alternatives to fossil-fuel-based plastics.",
    },
    {
        "title": "Solar Glass / Carbon Capture Engineer",
        "sector": "Science & Technology",
        "chapter": 3,
        "description": "Engineering materials that capture carbon or generate solar electricity from transparent surfaces.",
    },
    {
        "title": "Bot Counselor Developer",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Applying psychology and behavioral science to design AI bots with socio-emotional intelligence.",
    },
    {
        "title": "Biomimetic Architect",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Designing buildings and urban spaces that mimic natural biological systems for maximum sustainability.",
    },
    {
        "title": "Virtual Production Specialist",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Using real-time game engines and VR to manage the digital aspects of film and media production.",
    },
    {
        "title": "Impact Checker",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Utilizing data and statistics to measure the real-time social and developmental impact of non-profit projects.",
    },
    {
        "title": "Project / Field Director",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Leading the on-ground implementation of social innovations and development projects.",
    },
    {
        "title": "Mental Health Professional",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Counselors and clinicians focused on psychological well-being, utilizing both traditional and digital therapy tools.",
    },
    {
        "title": "Specialized Life Coach",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Providing guidance for specific, granular life challenges using humanities-based coaching techniques.",
    },
    {
        "title": "Artiste Management",
        "sector": "Liberal Arts",
        "chapter": 4,
        "description": "Managing talent and navigating the complexities of the creative industries.",
    },
    {
        "title": "Experiential Designer",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Creating immersive 'phygital' shopping journeys that blend physical stores with AI and AR technology.",
    },
    {
        "title": "E-commerce Expert",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Managing visibility platforms, logistics, and real-time tracking for the online retail supply chain.",
    },
    {
        "title": "Environmental Ethicist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Advising businesses on fair-trade, sustainable sourcing, and reducing ecological footprints.",
    },
    {
        "title": "Digital Transformation Expert",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Leading the integration of digital technologies and AI into traditional business operations.",
    },
    {
        "title": "Retail Influencer Manager",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Coordinating and analyzing brand partnerships with digital influencers to reach consumers.",
    },
    {
        "title": "Real Estate Transactioner",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Guiding buyers through the increasingly technical legal, financial, and policy landscape of property.",
    },
    {
        "title": "Techno-agent",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Real estate professionals using VR tours, AI valuations, and blockchain for modern property dealing.",
    },
    {
        "title": "Smart Developer",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Designing smart homes and digital infrastructure for highly connected urban smart cities.",
    },
    {
        "title": "Sustainable Developer",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Focusing on green building practices and the integration of renewable energy into real estate.",
    },
    {
        "title": "Infrastructure Resilience Expert",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Strengthening transportation and utility systems against climate disasters and cyberattacks.",
    },
    {
        "title": "Real Estate Data Technologist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Using data science and predictive modeling to evaluate property values and market trends.",
    },
    {
        "title": "Real Estate Blockchain Developer",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Creating secure, decentralized systems for property title management and transactions.",
    },
    {
        "title": "PR Professional",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Managing public perception across digital platforms and navigating fragmented media landscapes.",
    },
    {
        "title": "Behavioural Economist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Applying psychology to business and marketing to predict consumer behavior patterns.",
    },
    {
        "title": "Sustainability Accountant",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Auditing and managing a company's financial records relative to ESG (Environmental, Social, and Governance) criteria.",
    },
    {
        "title": "Forensic Accountant",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Utilizing cybersecurity and finance skills to investigate and mitigate financial crimes.",
    },
    {
        "title": "International Business Strategist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Managing geopolitical risks and cross-border regulations in the global economy.",
    },
    {
        "title": "Digital Asset Analyst",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Assessing and managing the value of cryptocurrencies and other blockchain-based digital assets.",
    },
    {
        "title": "Community Tourism Specialist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Designing travel experiences that focus on cultural preservation and benefit local communities.",
    },
    {
        "title": "Conservation Tourism Consultant",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Developing eco-friendly tourism strategies centered on environmental and wildlife protection.",
    },
    {
        "title": "Health & Wellness Hospitality Coach",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Designing specialized hospitality services like mental health retreats and wellness programs.",
    },
    {
        "title": "AR Hospitality Specialist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Creating immersive guest experiences, such as augmented reality menu previews and virtual concierge services.",
    },
    {
        "title": "Tourism Innovation Expert",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Curating highly customized, tech-enabled experiences for niche traveler segments.",
    },
    {
        "title": "Sports Data Science Specialist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Building predictive models for coaching, training, and player development using athletic performance data.",
    },
    {
        "title": "Motion Capture Specialist",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Analyzing athlete biomechanics through motion capture technology to maximize performance and prevent injury.",
    },
    {
        "title": "eSports Manager",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Managing competitive gaming events, professional players, and the digital broadcasting of eSports.",
    },
    {
        "title": "Sports Biotechnology Expert",
        "sector": "Professional Sectors",
        "chapter": 5,
        "description": "Applying biotechnology to develop customized nutrition and performance enhancement for extreme athletes.",
    },
]

CAREER_AGENTS = {
    "psychologist": {
        "id": "psychologist",
        "name": "Psychologist Agent",
        "role": "Career Psychologist and Behavioral Analyst",
        "description": "Evaluates psychological fit between a student and potential careers",
        "reasoning_inputs": [
            "personality_traits",
            "interests",
            "motivation",
            "stress_tolerance",
            "social_preferences",
        ],
        "evaluation_criteria": [
            "personality_role_alignment",
            "burnout_risk",
            "cognitive_load_tolerance",
            "preferred_working_style",
        ],
        "must_ignore": ["salary", "market_demand", "financial_constraints", "prestige"],
        "core_mission": "Protect the student from psychological mismatch",
        "question_themes": [
            "How do you handle stress when deadlines are tight?",
            "Do you prefer working alone or collaborating with others?",
            "What type of work environment makes you feel most energized?",
            "How important is work-life balance to you?",
            "What activities make you lose track of time?",
        ],
        "output_schema": {
            "psychological_fit_score": "0-100",
            "burnout_risk_level": "low|medium|high",
            "personality_alignment": "description",
            "working_style_match": "description",
        },
    },
    "market_reality": {
        "id": "market_reality",
        "name": "Market Reality Agent",
        "role": "Labor Market Economist",
        "description": "Evaluates careers based on economic and hiring reality",
        "reasoning_inputs": [
            "career_dataset",
            "salary_tables",
            "demand_metrics",
            "geographic_filters",
        ],
        "evaluation_criteria": [
            "salary_realism",
            "demand_vs_supply",
            "competition",
            "growth_trajectory",
        ],
        "must_ignore": ["student_personality", "interests", "motivation"],
        "core_mission": "Kill unrealistic or fantasy career choices",
        "question_themes": [
            "Are you aware of the typical salary range for this career?",
            "Have you researched job availability in your preferred location?",
            "Do you understand the competition level in this field?",
            "Are you prepared for the job market realities in this industry?",
        ],
        "output_schema": {
            "market_viability_score": "0-100",
            "salary_expectations": "realistic|optimistic|unrealistic",
            "job_demand": "high|medium|low",
            "growth_outlook": "growing|stable|declining",
        },
    },
    "skills_gap": {
        "id": "skills_gap",
        "name": "Skills Gap Agent",
        "role": "Hiring Manager and Talent Evaluator",
        "description": "Evaluates whether the student can realistically reach a career",
        "reasoning_inputs": [
            "academic_history",
            "current_skills",
            "learning_speed",
            "discipline_indicators",
        ],
        "evaluation_criteria": [
            "skill_gap_severity",
            "learning_curve",
            "time_to_employability",
            "dropout_risk",
        ],
        "must_ignore": ["money", "family_pressure", "job_availability"],
        "core_mission": "Protect the student from infeasible paths",
        "question_themes": [
            "What relevant skills or experience do you already have?",
            "How quickly do you typically learn new subjects or skills?",
            "What's your track record with challenging academic subjects?",
            "How much time are you willing to invest in skill development?",
            "Have you completed any projects or courses in this field?",
        ],
        "output_schema": {
            "feasibility_score": "0-100",
            "skill_gap_level": "minimal|moderate|significant",
            "estimated_time_to_ready": "months/years",
            "dropout_risk": "low|medium|high",
        },
    },
    "constraint": {
        "id": "constraint",
        "name": "Constraint Agent",
        "role": "Real-World Constraint Enforcer",
        "description": "Behaves like a strict financial auditor enforcing practical limitations",
        "reasoning_inputs": [
            "family_income",
            "education_budget",
            "geography",
            "visa_eligibility",
            "legal_requirements",
        ],
        "evaluation_criteria": [
            "affordability",
            "eligibility",
            "logistical_feasibility",
        ],
        "must_ignore": ["happiness", "passion", "ambition"],
        "core_mission": "Ensure the recommendation is physically and financially possible",
        "question_themes": [
            "What's your education budget for pursuing this career?",
            "Are there geographic constraints on where you can study or work?",
            "Do you have any visa or legal requirements to consider?",
            "What financial support is available to you?",
            "Are there any family obligations that affect your career choices?",
        ],
        "output_schema": {
            "feasibility_score": "0-100",
            "financial_viability": "viable|challenging|infeasible",
            "geographic_constraints": "none|some|significant",
            "legal_eligibility": "eligible|conditional|ineligible",
        },
    },
    "values": {
        "id": "values",
        "name": "Values Agent",
        "role": "Life Coach and Values Analyst",
        "description": "Focuses on long-term lifestyle alignment",
        "reasoning_inputs": [
            "money_vs_meaning_preference",
            "risk_appetite",
            "prestige_need",
            "autonomy_preference",
        ],
        "evaluation_criteria": [
            "value_alignment",
            "lifestyle_compatibility",
            "intrinsic_satisfaction",
        ],
        "must_ignore": ["market_demand", "salary", "constraints"],
        "core_mission": "Maximize long-term life satisfaction",
        "question_themes": [
            "What matters more to you: financial success or meaningful work?",
            "How important is having autonomy in your work?",
            "Do you value prestige and recognition in your career?",
            "What kind of lifestyle do you envision for yourself?",
            "Would you prefer stability or the excitement of risk?",
        ],
        "output_schema": {
            "values_alignment_score": "0-100",
            "money_vs_meaning": "money|balanced|meaning",
            "lifestyle_fit": "excellent|good|poor",
            "long_term_satisfaction": "high|medium|low",
        },
    },
    "automation_risk": {
        "id": "automation_risk",
        "name": "Automation Risk Agent",
        "role": "Future-of-Work and AI Risk Analyst",
        "description": "Assesses automation exposure for career paths",
        "reasoning_inputs": [
            "career_skill_types",
            "task_composition",
            "human_vs_machine_components",
        ],
        "evaluation_criteria": [
            "ai_replaceability",
            "long_term_relevance",
            "human_moat_strength",
        ],
        "must_ignore": ["personal_fit", "passion", "salary"],
        "core_mission": "Protect the student from dying careers",
        "question_themes": [
            "How do you feel about working alongside AI and automation?",
            "Are you interested in roles that require uniquely human skills?",
            "How adaptable are you to learning new technologies?",
            "Do you prefer creative/strategic work over routine tasks?",
            "How important is job security against technological changes?",
        ],
        "output_schema": {
            "automation_risk_score": "0-100",
            "ai_exposure": "low|medium|high",
            "future_relevance": "10+ years|5-10 years|uncertain",
            "human_advantage": "strong|moderate|weak",
        },
    },
    "trajectory": {
        "id": "trajectory",
        "name": "Trajectory Agent",
        "role": "Career Systems Simulator",
        "description": "Simulates realistic career progression paths",
        "reasoning_inputs": [
            "career_ladders",
            "industry_structures",
            "market_transitions",
        ],
        "evaluation_criteria": [
            "typical_role_progression",
            "time_to_seniority",
            "ceiling_potential",
        ],
        "must_avoid": ["unrealistic_jumps", "unicorn_stories", "rare_exceptions"],
        "core_mission": "Model what most people experience, not best cases",
        "question_themes": [
            "Where do you see yourself in 5, 10, and 20 years?",
            "Are you comfortable with a slow, steady progression?",
            "Do you aspire to leadership roles or prefer expertise paths?",
            "How important is reaching a senior position quickly?",
            "Are you okay with industry-standard career timelines?",
        ],
        "output_schema": {
            "trajectory_clarity_score": "0-100",
            "typical_timeline": "description",
            "ceiling_potential": "high|medium|limited",
            "progression_realism": "realistic|optimistic|unrealistic",
        },
    },
    "regret_minimization": {
        "id": "regret_minimization",
        "name": "Regret Minimization Agent",
        "role": "Stoic Philosopher for Regret Avoidance",
        "description": "Minimizes irreversible life decisions",
        "reasoning_inputs": ["reversibility", "skill_portability", "optionality"],
        "evaluation_criteria": [
            "lock_in_risk",
            "exit_flexibility",
            "future_pivot_ability",
        ],
        "must_ignore": ["short_term_rewards", "hype", "trends"],
        "core_mission": "Ensure the student can change their mind later",
        "question_themes": [
            "How important is keeping your options open?",
            "Would you prefer a career with transferable skills?",
            "How do you feel about committing to a specialized path?",
            "What if you want to change careers in 10 years?",
            "Do you value flexibility over specialization?",
        ],
        "output_schema": {
            "optionality_score": "0-100",
            "lock_in_risk": "low|medium|high",
            "skill_portability": "high|medium|low",
            "pivot_flexibility": "easy|moderate|difficult",
        },
    },
    "black_swan": {
        "id": "black_swan",
        "name": "Black Swan Agent",
        "role": "Nonlinear Opportunity Scout and Startup Founder",
        "description": "Identifies rare high-upside paths",
        "reasoning_inputs": ["interests", "skills", "risk_tolerance"],
        "evaluation_criteria": [
            "unconventional_opportunities",
            "asymmetric_payoff_potential",
            "personal_leverage",
        ],
        "must_avoid": ["lottery_careers", "fame_based_paths", "gambling"],
        "core_mission": "Surface optional high-risk, high-reward alternatives",
        "question_themes": [
            "Are you drawn to unconventional career paths?",
            "How comfortable are you with calculated risks?",
            "Do you have unique skills that could give you an edge?",
            "Are you interested in entrepreneurship or startups?",
            "Would you trade stability for potential high rewards?",
        ],
        "output_schema": {
            "opportunity_score": "0-100",
            "risk_reward_ratio": "favorable|neutral|unfavorable",
            "unique_leverage": "description",
            "unconventional_paths": ["list of opportunities"],
        },
    },
    "judge": {
        "id": "judge",
        "name": "Judge Agent",
        "role": "Chief Decision Intelligence System",
        "description": "Receives conclusions from all other agents and makes final decision",
        "reasoning_inputs": [
            "all_agent_outputs",
            "weighted_priorities",
            "conflict_resolution_rules",
        ],
        "evaluation_criteria": [
            "weighted_agent_scores",
            "conflict_resolution",
            "constraint_prioritization",
            "long_term_optimization",
        ],
        "must_never": [
            "override_constraints",
            "ignore_automation_risk",
            "favor_single_agent",
        ],
        "core_mission": "Produce the final career decision by weighing all agents rationally",
        "output_schema": {
            "final_recommendations": ["list of careers"],
            "agent_weight_distribution": "dict",
            "conflict_resolutions": ["list of resolved conflicts"],
            "confidence_score": "0-100",
        },
    },
}

# List of agent IDs for iteration
AGENT_IDS = list(CAREER_AGENTS.keys())

# Agent categories for different evaluation phases
AGENT_CATEGORIES = {
    "fit_analysis": ["psychologist", "values", "skills_gap"],
    "reality_check": ["market_reality", "constraint", "automation_risk"],
    "future_planning": ["trajectory", "regret_minimization", "black_swan"],
    "final_decision": ["judge"],
}

# Agent weights for final recommendation scoring (can be adjusted)
DEFAULT_AGENT_WEIGHTS = {
    "psychologist": 0.15,
    "market_reality": 0.12,
    "skills_gap": 0.12,
    "constraint": 0.15,
    "values": 0.10,
    "automation_risk": 0.10,
    "trajectory": 0.08,
    "regret_minimization": 0.08,
    "black_swan": 0.05,
    "judge": 0.05,  # Judge acts as a meta-agent, lower direct weight
}


# ================== AGENT QUESTION BANK ==================


def get_agent_questions(agent_id: str) -> List[str]:
    """Get question themes for a specific agent"""
    agent = CAREER_AGENTS.get(agent_id)
    if agent:
        return agent.get("question_themes", [])
    return []


def get_all_agent_questions() -> Dict[str, List[str]]:
    """Get all questions organized by agent"""
    return {
        agent_id: agent.get("question_themes", [])
        for agent_id, agent in CAREER_AGENTS.items()
        if agent_id != "judge"  # Judge doesn't ask questions
    }


def get_agent_by_id(agent_id: str) -> Dict[str, Any]:
    """Get a specific agent configuration by ID"""
    return CAREER_AGENTS.get(agent_id, {})


def get_agents_for_category(category: str) -> List[Dict[str, Any]]:
    """Get all agents in a specific category"""
    agent_ids = AGENT_CATEGORIES.get(category, [])
    return [CAREER_AGENTS[aid] for aid in agent_ids if aid in CAREER_AGENTS]


# ================== AGENT PROMPT TEMPLATES ==================


def get_agent_system_prompt(agent_id: str) -> str:
    """Generate a system prompt for a specific agent"""
    agent = CAREER_AGENTS.get(agent_id)
    if not agent:
        return ""

    reasoning_inputs = "\n".join([f"- {r}" for r in agent.get("reasoning_inputs", [])])
    evaluation_criteria = "\n".join(
        [f"- {e}" for e in agent.get("evaluation_criteria", [])]
    )
    must_ignore = "\n".join(
        [
            f"- {m}"
            for m in agent.get(
                "must_ignore", agent.get("must_avoid", agent.get("must_never", []))
            )
        ]
    )

    return f"""You are a {agent['role']}.
Your sole responsibility is to {agent['description'].lower()}.

You must reason ONLY from:
{reasoning_inputs}

You evaluate:
{evaluation_criteria}

You must IGNORE:
{must_ignore}

Your core mission: {agent['core_mission']}

Be direct, analytical, and do not invent data or assume information not provided."""


def get_judge_agent_prompt(agent_outputs: Dict[str, Any]) -> str:
    """Generate the prompt for the Judge agent to synthesize all agent outputs"""
    agent = CAREER_AGENTS["judge"]

    outputs_text = "\n\n".join(
        [
            f"=== {CAREER_AGENTS[aid]['name']} ===\n{output}"
            for aid, output in agent_outputs.items()
            if aid != "judge"
        ]
    )

    return f"""You are the {agent['role']}.
You receive conclusions from all other agents and must produce the final career recommendation.

=== AGENT OUTPUTS ===
{outputs_text}

Your responsibilities:
1. Weigh each agent's assessment rationally based on their importance
2. Resolve any conflicts between agent recommendations
3. Prioritize constraints and feasibility (cannot override hard constraints)
4. Optimize for long-term student outcome

You must NEVER:
- Override hard constraints (financial, legal, eligibility)
- Ignore automation risk when it's significant
- Favor a single agent's opinion over the collective analysis

Produce a final, balanced career recommendation that accounts for all perspectives."""


# ================== QUESTION CATEGORIES FOR Career & Degree Selection ==================

QUESTION_CATEGORIES = {
    "psychological_profile": {
        "description": "Understanding personality, stress tolerance, and work preferences",
        "agents": ["psychologist"],
        "sample_questions": [
            "How do you typically handle high-pressure situations?",
            "Do you prefer collaborative or independent work?",
            "What work environment brings out your best?",
        ],
    },
    "values_and_lifestyle": {
        "description": "Understanding what matters most in life and career",
        "agents": ["values"],
        "sample_questions": [
            "What matters more: high income or work you find meaningful?",
            "How much autonomy do you need in your work?",
            "What lifestyle do you envision for yourself?",
        ],
    },
    "skills_and_capabilities": {
        "description": "Assessing current abilities and learning potential",
        "agents": ["skills_gap"],
        "sample_questions": [
            "What are you naturally good at?",
            "How quickly do you pick up new skills?",
            "What's your academic track record like?",
        ],
    },
    "practical_constraints": {
        "description": "Understanding real-world limitations",
        "agents": ["constraint"],
        "sample_questions": [
            "What's your budget for education/training?",
            "Are there geographic restrictions on where you can work?",
            "Any visa or legal considerations?",
        ],
    },
    "future_orientation": {
        "description": "Understanding risk tolerance and long-term thinking",
        "agents": [
            "automation_risk",
            "trajectory",
            "regret_minimization",
            "black_swan",
        ],
        "sample_questions": [
            "How important is job security to you?",
            "Where do you see yourself in 10-20 years?",
            "How do you feel about taking calculated risks?",
        ],
    },
}


# ================== DOMAIN-TO-CAREER MAPPING ==================
# Maps each predefined domain to EXAMPLE careers the student can pursue in that domain.
# This is a reference list, NOT exhaustive. The LLM may recommend any legitimate career
# within the domain, including roles not listed here.
# Used to focus questions and recommendations on specific careers within the student's chosen domains.

DOMAIN_CAREER_MAPPING: Dict[DomainEnum, List[str]] = {
    DomainEnum.PURE_SCIENCE: [
        # Reference careers
        "Physicist (theoretical / experimental)", "Chemist", "Molecular Biologist",
        "Microbiologist", "Geneticist", "Neuroscientist (basic research)",
        "Astrophysicist", "Materials Scientist", "Computational Scientist",
        "Climate Scientist (research-focused)", "Biophysicist",
        "Research Fellow / Scientist", "Lab-based PhD Researcher",
        "Academic Professor (research-heavy)", "Scientific Journal Editor (technical)",
        # Additional careers
        "Research Scientist", "Data Scientist", "Marine Biologist", "Geologist",
        "Mathematician", "Environmental Scientist", "Biotechnologist", "Lab Director",
    ],
    DomainEnum.PERFORMING_ARTS: [
        # Reference careers
        "Actor (theatre / film / TV)", "Dancer", "Musician (instrumentalist)",
        "Singer", "Theatre Performer", "Stand-up Comedian", "Performance Artist",
        "Orchestra Member", "Opera Singer", "Choreographer", "Stage Performer",
        "Voice Actor", "Performance Poet", "Circus Artist",
        "Improvisational Performer",
        # Additional careers
        "Film Director", "Music Producer", "Performing Arts Manager",
    ],
    DomainEnum.HUMANITIES: [
        # Reference careers
        "Writer (fiction / non-fiction)", "Historian", "Philosopher",
        "Literary Critic", "Cultural Analyst", "Journalist (long-form, investigative)",
        "Editor (books, essays)", "Academic Scholar (humanities)", "Translator",
        "Linguist", "Essayist", "Archivist", "Ethics Researcher",
        "Comparative Literature Researcher", "Intellectual Historian",
        # Additional careers
        "Cultural Anthropologist", "Content Strategist", "Documentary Filmmaker",
        "Museum Studies Specialist", "Publishing Editor",
    ],
    DomainEnum.BUSINESS_ENTREPRENEURSHIP: [
        # Reference careers
        "Entrepreneur / Startup Founder", "CEO / Managing Director",
        "Product Manager", "Strategy Consultant", "Business Development Manager",
        "Operations Manager", "Sales Leader", "General Manager",
        "Venture Capitalist", "Private Equity Professional", "Corporate Strategist",
        "Chief of Staff", "Growth Manager", "Franchise Owner",
        "Family Business Operator",
        # Additional careers
        "Management Consultant", "Marketing Manager", "Business Analyst",
        "HR Manager", "Supply Chain Manager", "Brand Manager", "Project Manager",
        "Chief Operating Officer", "Business Intelligence Analyst", "Corporate Trainer",
        "Innovation Consultant", "Social Entrepreneur", "Angel Investor",
        "Growth Hacker", "Serial Entrepreneur", "Incubator Director",
        "E-commerce Entrepreneur", "Tech Startup CEO",
    ],
    DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS: [
        # Reference careers
        "Data Analyst", "Data Scientist", "Statistician", "Quantitative Analyst",
        "Actuary", "Economist (quantitative)", "Financial Analyst", "Risk Analyst",
        "Business Intelligence Analyst", "Operations Research Analyst",
        "Market Research Analyst", "Credit Analyst", "Pricing Analyst",
        "Investment Analyst", "Forecasting Specialist",
        # Additional careers
        "Investment Banker", "Portfolio Manager", "Chartered Accountant",
        "Tax Consultant", "Wealth Manager", "Equity Research Analyst", "CFO",
        "Fintech Product Manager", "Financial Planner", "Compliance Officer",
    ],
    DomainEnum.LAW: [
        # Reference careers
        "Lawyer (corporate / criminal / civil)", "Trial Attorney", "Judge",
        "Legal Counsel", "Prosecutor", "Public Defender", "Contract Lawyer",
        "Regulatory Lawyer", "Constitutional Lawyer", "IP Lawyer",
        "Compliance Officer", "Legal Policy Advisor", "Legal Researcher",
        "Arbitration Specialist", "Judicial Clerk",
        # Additional careers
        "Human Rights Advocate", "Patent Attorney", "Mediator",
        "Environmental Lawyer", "Cyber Law Specialist", "Legal Tech Specialist",
        "International Law Attorney", "Family Law Attorney", "Tax Attorney",
    ],
    DomainEnum.SOCIAL_SCIENCES: [
        # Reference careers
        "Sociologist", "Social Researcher", "Anthropologist",
        "Political Scientist", "Behavioral Scientist", "Development Economist",
        "Social Policy Researcher", "Demographer", "Survey Researcher",
        "Human Geography Researcher", "Population Studies Analyst",
        "Public Opinion Analyst", "Social Impact Analyst", "Migration Researcher",
        "Inequality Researcher",
        # Additional careers
        "Psychologist", "Social Worker", "Counselor", "Urban Planner",
        "Community Development Manager", "NGO Director", "Market Research Analyst",
        "Organizational Psychologist",
    ],
    DomainEnum.HEALTH_LIFE_SCIENCE: [
        # Reference careers
        "Medical Doctor", "Surgeon", "Psychiatrist", "Clinical Psychologist",
        "Biomedical Researcher", "Epidemiologist", "Public Health Specialist",
        "Pharmacologist", "Clinical Research Scientist", "Genetic Counselor",
        "Pathologist", "Immunologist", "Biostatistician (health-focused)",
        "Healthcare Researcher", "Translational Scientist",
        # Additional careers
        "Nurse Practitioner", "Pharmacist", "Physical Therapist",
        "Biomedical Engineer", "Nutritionist", "Health Informatics Specialist",
        "Veterinarian", "Dentist", "Occupational Therapist",
    ],
    DomainEnum.SPORTS_ATHLETICS: [
        # Reference careers
        "Professional Athlete", "Olympic Athlete", "Sports Coach",
        "Strength & Conditioning Coach", "Sports Trainer", "Sports Scientist",
        "Performance Analyst (sports)", "Athletic Director",
        "Sports Physiotherapist", "Competitive Swimmer / Runner / Player",
        "Martial Artist (professional)", "Esports Athlete",
        "Sports Academy Instructor", "Team Captain (professional)",
        "Fitness Competitor",
        # Additional careers
        "Sports Manager", "Sports Psychologist", "Sports Journalist",
        "Sports Marketing Manager", "Physical Education Teacher",
        "Sports Data Analyst", "Fitness Entrepreneur", "Team Manager",
        "Sports Agent", "Recreation Director",
    ],
    DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY: [
        # Reference careers
        "Software Engineer", "Mechanical Engineer", "Electrical Engineer",
        "Civil Engineer", "Chemical Engineer", "Robotics Engineer",
        "Aerospace Engineer", "Systems Engineer", "AI / ML Engineer",
        "Embedded Systems Engineer", "Hardware Engineer", "Network Engineer",
        "Infrastructure Engineer", "Automation Engineer",
        "Engineering Researcher (applied)",
        # Additional careers
        "DevOps Engineer", "Data Engineer", "Full Stack Developer",
        "Cybersecurity Engineer", "IoT Engineer",
    ],
    DomainEnum.ART_AESTHETICS: [
        # Reference careers
        "Graphic Designer", "UX / UI Designer", "Industrial Designer",
        "Product Designer", "Visual Artist", "Illustrator", "Fashion Designer",
        "Interior Designer", "Brand Designer", "Creative Director",
        "Interaction Designer", "Motion Graphics Designer", "Game Artist",
        "Exhibition Designer", "Design Researcher",
        # Additional careers
        "Service Designer", "Design Thinking Consultant", "Photographer",
        "Animator", "Art Director", "Museum Curator", "Art Therapist",
        "Screenwriter",
    ],
    DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT: [
        # Reference careers
        "Policy Analyst", "Civil Servant", "Diplomat", "Political Advisor",
        "Economist (policy-focused)", "Think Tank Researcher", "NGO Leader",
        "Development Policy Specialist", "Public Affairs Manager",
        "Government Program Manager", "International Relations Specialist",
        "Urban Policy Planner", "Climate Policy Analyst",
        "Social Impact Strategist", "Multilateral Organization Officer",
        # Additional careers
        "Government Administrator", "Campaign Manager", "Lobbyist",
        "International Development Specialist", "Legislative Aide",
        "Sustainability Officer", "Public Health Administrator",
    ],
}


# ================== CROSS-DOMAIN CAREER MAPPING ==================
# Maps each career to its primary domain and secondary domain (the intersection).
# Useful for recommending careers that bridge two domains a student is interested in.
# Keys match DOMAIN_CONFIG.


class CrossDomainEntry(TypedDict):
    career: str
    secondary_domain: DomainEnum


CROSS_DOMAIN_CAREERS: Dict[DomainEnum, List[CrossDomainEntry]] = {
    DomainEnum.PURE_SCIENCE: [
        # Pure Science careers appear as secondary in other domains;
        # no primary-Pure Science cross-domain entries provided.
    ],
    DomainEnum.PERFORMING_ARTS: [
        {"career": "Actor", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Dancer", "secondary_domain": DomainEnum.SPORTS_ATHLETICS},
        {"career": "Musician", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Singer", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Theatre Performer", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Stand-up Comedian", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Performance Artist", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Orchestra Member", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Opera Singer", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Choreographer", "secondary_domain": DomainEnum.ART_AESTHETICS},
        {"career": "Stage Performer", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Voice Actor", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Performance Poet", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Circus Artist", "secondary_domain": DomainEnum.SPORTS_ATHLETICS},
        {"career": "Improvisational Performer", "secondary_domain": DomainEnum.HUMANITIES},
    ],
    DomainEnum.HUMANITIES: [
        {"career": "Writer", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Historian", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Philosopher", "secondary_domain": DomainEnum.LAW},
        {"career": "Literary Critic", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Cultural Analyst", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Journalist (long-form)", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Editor", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Academic Scholar (humanities)", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Translator", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Linguist", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Essayist", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Archivist", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Ethics Researcher", "secondary_domain": DomainEnum.LAW},
        {"career": "Comparative Literature Researcher", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Intellectual Historian", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
    ],
    DomainEnum.BUSINESS_ENTREPRENEURSHIP: [
        {"career": "Entrepreneur / Startup Founder", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "CEO / Managing Director", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Product Manager", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Strategy Consultant", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Business Development Manager", "secondary_domain": DomainEnum.LAW},
        {"career": "Operations Manager", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Sales Leader", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "General Manager", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Venture Capitalist", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Private Equity Professional", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Corporate Strategist", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Chief of Staff", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Growth Manager", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Franchise Owner", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Family Business Operator", "secondary_domain": DomainEnum.HUMANITIES},
    ],
    DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS: [
        {"career": "Data Analyst", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Data Scientist", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Statistician", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Quantitative Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Actuary", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Economist (quantitative)", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Financial Analyst", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Risk Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "BI Analyst", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Operations Research Analyst", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Market Research Analyst", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Credit Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Pricing Analyst", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Investment Analyst", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Forecasting Specialist", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
    ],
    DomainEnum.LAW: [
        {"career": "Lawyer", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Trial Attorney", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Judge", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Legal Counsel", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Prosecutor", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Public Defender", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Contract Lawyer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Regulatory Lawyer", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Constitutional Lawyer", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "IP Lawyer", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Compliance Officer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Legal Policy Advisor", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Legal Researcher", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Arbitration Specialist", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Judicial Clerk", "secondary_domain": DomainEnum.HUMANITIES},
    ],
    DomainEnum.SOCIAL_SCIENCES: [
        {"career": "Sociologist", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Social Researcher", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Anthropologist", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Political Scientist", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Behavioral Scientist", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Development Economist", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Social Policy Researcher", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Demographer", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Survey Researcher", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Human Geography Researcher", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Population Studies Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Public Opinion Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Social Impact Analyst", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Migration Researcher", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Inequality Researcher", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
    ],
    DomainEnum.HEALTH_LIFE_SCIENCE: [
        {"career": "Medical Doctor", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Surgeon", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Psychiatrist", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Clinical Psychologist", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Biomedical Researcher", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Epidemiologist", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Public Health Specialist", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Pharmacologist", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Clinical Research Scientist", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Genetic Counselor", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Pathologist", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Immunologist", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Biostatistician", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Healthcare Researcher", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Translational Scientist", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
    ],
    DomainEnum.SPORTS_ATHLETICS: [
        {"career": "Professional Athlete", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Olympic Athlete", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Sports Coach", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Strength & Conditioning Coach", "secondary_domain": DomainEnum.HEALTH_LIFE_SCIENCE},
        {"career": "Sports Trainer", "secondary_domain": DomainEnum.HEALTH_LIFE_SCIENCE},
        {"career": "Sports Scientist", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Performance Analyst (sports)", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Athletic Director", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Sports Physiotherapist", "secondary_domain": DomainEnum.HEALTH_LIFE_SCIENCE},
        {"career": "Competitive Athlete", "secondary_domain": DomainEnum.SPORTS_ATHLETICS},
        {"career": "Martial Artist (professional)", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Esports Athlete", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Sports Academy Instructor", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Team Captain", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Fitness Competitor", "secondary_domain": DomainEnum.HEALTH_LIFE_SCIENCE},
    ],
    DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY: [
        {"career": "Software Engineer", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Mechanical Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Electrical Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Civil Engineer", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Chemical Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Robotics Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Aerospace Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Systems Engineer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "AI / ML Engineer", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Embedded Systems Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Hardware Engineer", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Network Engineer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Infrastructure Engineer", "secondary_domain": DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT},
        {"career": "Automation Engineer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Engineering Researcher", "secondary_domain": DomainEnum.PURE_SCIENCE},
    ],
    DomainEnum.ART_AESTHETICS: [
        {"career": "Graphic Designer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "UX / UI Designer", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Industrial Designer", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Product Designer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Visual Artist", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Illustrator", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Fashion Designer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Interior Designer", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Brand Designer", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Creative Director", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Interaction Designer", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Motion Graphics Designer", "secondary_domain": DomainEnum.PERFORMING_ARTS},
        {"career": "Game Artist", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Exhibition Designer", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Design Researcher", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
    ],
    DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT: [
        {"career": "Policy Analyst", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Civil Servant", "secondary_domain": DomainEnum.LAW},
        {"career": "Diplomat", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Political Advisor", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Economist (policy)", "secondary_domain": DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS},
        {"career": "Think Tank Researcher", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "NGO Leader", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Development Policy Specialist", "secondary_domain": DomainEnum.SOCIAL_SCIENCES},
        {"career": "Public Affairs Manager", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Government Program Manager", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "International Relations Specialist", "secondary_domain": DomainEnum.HUMANITIES},
        {"career": "Urban Policy Planner", "secondary_domain": DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY},
        {"career": "Climate Policy Analyst", "secondary_domain": DomainEnum.PURE_SCIENCE},
        {"career": "Social Impact Strategist", "secondary_domain": DomainEnum.BUSINESS_ENTREPRENEURSHIP},
        {"career": "Multilateral Organization Officer", "secondary_domain": DomainEnum.HUMANITIES},
    ],
}


# Key consistency is enforced statically: both DOMAIN_CAREER_MAPPING and
# CROSS_DOMAIN_CAREERS are typed Dict[DomainEnum, ...], so any key not present
# in DomainEnum (which mirrors DOMAIN_CONFIG exactly) is a type error.
