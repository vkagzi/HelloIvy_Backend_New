from enum import StrEnum


class DomainEnum(StrEnum):
    """Enumeration of all supported career/interest domains.

    Values match the canonical domain strings used throughout the app.
    Because DomainEnum subclasses str, existing code that compares or
    indexes with plain strings continues to work unchanged.
    """

    PURE_SCIENCE = "Pure Science"
    PERFORMING_ARTS = "Performing Arts"
    HUMANITIES = "Humanities"
    BUSINESS_ENTREPRENEURSHIP = "Business / Entrepreneurship"
    STATISTICS_FINANCE_DATA_ANALYTICS = "Statistics / Finance / Data Analytics"
    LAW = "Law"
    SOCIAL_SCIENCES = "Social Sciences"
    HEALTH_LIFE_SCIENCE = "Health & Life Science"
    SPORTS_ATHLETICS = "Sports/Athletics"
    ENGINEERING_APPLIED_TECHNOLOGY = "Engineering & Applied Technology"
    ART_AESTHETICS = "Art & Aesthetics"
    PUBLIC_POLICY_GOVERNANCE_IMPACT = "Public Policy, Governance & Impact"


DOMAIN_CONFIG: dict[DomainEnum, str] = {
    DomainEnum.PURE_SCIENCE: "Enjoying scientific research in biology, chemistry or physics, lab work, publishing research, conducting experiments, logic, and problem-solving",
    DomainEnum.PERFORMING_ARTS: "Enjoying creative expression through art, music, dance, theatre or performance",
    DomainEnum.HUMANITIES: "Enjoying reading, writing, ideas, culture, and understanding people",
    DomainEnum.BUSINESS_ENTREPRENEURSHIP: "Enjoying leadership, creating something new, decision-making, teamwork, taking initiative and strategy",
    DomainEnum.STATISTICS_FINANCE_DATA_ANALYTICS: "Enjoying numbers, analysis, patterns, and structured thinking",
    DomainEnum.LAW: "Enjoying debate, reasoning, rules, justice, and critical thinking",
    DomainEnum.SOCIAL_SCIENCES: "Enjoying understanding human behaviour, society, research, and impact",
    DomainEnum.HEALTH_LIFE_SCIENCE: "Enjoying biology, health, human life, and helping people through science",
    DomainEnum.SPORTS_ATHLETICS: "Enjoying playing a sport competitively, physical activity, competition, and improving performance through training, strategy, and measurable goals",
    DomainEnum.ENGINEERING_APPLIED_TECHNOLOGY: "Enjoying designing systems, machines, software, infrastructure, circuit systems, physics",
    DomainEnum.ART_AESTHETICS: "Enjoying improving usability, elegance, and experience, drawing, sketching, designing, creativity",
    DomainEnum.PUBLIC_POLICY_GOVERNANCE_IMPACT: "Enjoying politics, history, ethics, economics, creating social impact, helping civil society",
}

DOMAIN_LIST: list[DomainEnum] = list(DOMAIN_CONFIG.keys())

