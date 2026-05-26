# HelloIvy Discovery Modules - Documentation Index

## Overview

HelloIvy provides two interconnected AI-powered discovery modules that guide students through a comprehensive journey from broad interests to specific career paths.

## The Two Modules

### 1. Stream & Subject Selection
**Purpose:** Identify broad academic and interest domains  
**Questions:** 25 deep dive questions  
**Output:** Top 3 domain recommendations (from 13 predefined domains)  
**Prerequisites:** None (entry point for new users)

**Documentation:**
- 📘 [Product & Technical Docs](./domain-discovery.md)
- 📂 [Module README](../domain_discovery/README.md)

### 2. Career & Degree Selection 
**Purpose:** Identify specific career paths and jobs  
**Questions:** 20 questions (10 profile + 10 explorer)  
**Output:** Up to 8 specific career recommendations with actionable steps  
**Prerequisites:** Completed Stream & Subject Selection session

**Documentation:**
- 📘 [Product & Technical Docs](./career-discovery.md)
- 📂 [Module README](../career_discovery/README.md)

---

## The Complete User Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEW USER STARTS HERE                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Stream & Subject Selection                                       │
│  ─────────────────────────────────────────────────────────────  │
│  • 25 AI-generated personalized questions                       │
│  • Explores interests, strengths, preferences                   │
│  • Uses user profile data for personalization                   │
│  • AI analyzes responses to identify domain fit                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: Top 3 Domains                                          │
│  ─────────────────────────────────────────────────────────────  │
│  Example:                                                        │
│  1. Engineering & Applied Technology (92% match)                │
│  2. Design & Aesthetics (85% match)                             │
│  3. Entrepreneurship (78% match)                                │
│                                                                  │
│  Each with:                                                      │
│  • Match percentage                                              │
│  • Key interests identified                                      │
│  • Sub-domains                                                   │
│  • Why recommended                                               │
│  • Exploration activities                                        │
│  • Potential career previews                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Career & Degree Selection                                       │
│  ─────────────────────────────────────────────────────────────  │
│  OPENING MESSAGE REFERENCES DOMAIN RESULTS:                     │
│  "Hey [Name]! In our last session, we discovered that           │
│   Engineering, Design, and Entrepreneurship are your            │
│   top-suited domains. Let's explore specific careers!"          │
│                                                                  │
│  • Phase 1: Profile Builder (10 questions)                      │
│    - Validates domain insights                                   │
│    - Explores career-relevant preferences                        │
│                                                                  │
│  • Phase 2: Career Explorer (10 questions)                      │
│    - Dives into specific career paths                           │
│    - Assesses job activity alignment                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: Up to 8 Specific Career Recommendations               │
│  ─────────────────────────────────────────────────────────────  │
│  Example:                                                        │
│  1. UX Designer (94% match)                                     │
│     • Salary: $70K-$120K                                        │
│     • Skills: User Research, Figma, Wireframing                 │
│     • Next Steps: Take UX course, build portfolio               │
│     • Why: Combines design domain + problem-solving             │
│                                                                  │
│  2. Product Manager (91% match)                                 │
│  3. Software Engineer (88% match)                               │
│  ... (up to 8 total)                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## How the Modules Work Together

### Data Flow

```
Stream & Subject Selection Session
  ├── Top 3 Domains
  ├── Match Percentages
  ├── Full Q&A History
  └── Domain Explanations
          ↓
     (passed to)
          ↓
Career & Degree Selection Session
  ├── References domain results in opening
  ├── Uses domain context for career suggestions
  ├── Validates domain insights with deeper questions
  └── Recommends careers aligned with domains
```

### Technical Integration

**Database Relationship:**
```python
# CareerSession has foreign key to DomainSession
CareerSession.domain_session → DomainSession
```

**Context Passed to AI:**
```python
domain_context = {
    'recommendations': [
        {'title': 'Engineering', 'match_percentage': 92, ...},
        {'title': 'Design', 'match_percentage': 85, ...},
        {'title': 'Entrepreneurship', 'match_percentage': 78, ...}
    ],
    'messages': [
        # Full Stream & Subject Selection conversation
    ]
}
```

### Initial Question Strategy

**Stream & Subject Selection:**
> "Hi there! I'm excited to help you figure out the perfect domain that aligns with your unique strengths and interests. Let's start by understanding what fascinates you..."

**Career & Degree Selection :**
> "Hey Sarah! In our last session, we discovered that Engineering & Applied Technology, Design & Aesthetics, and Entrepreneurship are your top-suited domains. I noticed you're captain of your robotics team—amazing! I'm excited to dive deeper and help you explore specific careers in these areas. What excites you most about building and creating?"

---

## API Endpoints Overview

### Stream & Subject Selection
| Endpoint | Purpose |
|----------|---------|
| `POST /api/domain-discovery/` | Create new session |
| `POST /api/domain-discovery/<id>/messages/` | Send message, get next question |
| `POST /api/domain-discovery/<id>/recommendations/generate/` | Generate domain recommendations |
| `GET /api/domain-discovery/<id>/recommendations/` | Get recommendations |

### Career & Degree Selection 
| Endpoint | Purpose |
|----------|---------|
| `POST /api/career-discovery/` | Create new session (requires domain session) |
| `POST /api/career-discovery/<id>/messages/` | Send message, get next question |
| `POST /api/career-discovery/<id>/recommendations/generate/` | Generate career recommendations |
| `GET /api/career-discovery/<id>/recommendations/` | Get recommendations |

---

## The 13 Predefined Domains

1. **Pure Science** - Research, experimentation, scientific discovery
2. **Arts** - Creative expression through art, music, design, performance
3. **Humanities** - Literature, philosophy, history, culture
4. **Business** - Leadership, strategy, management
5. **Finance** - Markets, investments, financial analysis
6. **Entrepreneurship** - Building ventures, innovation, startups
7. **Law** - Justice, legal systems, policy, advocacy
8. **Social Sciences** - Psychology, sociology, human behavior
9. **Health & Life Science** - Medicine, healthcare, biology
10. **Sports/Athletics** - Professional sports, coaching, management
11. **Engineering & Applied Technology** - Building systems, software, infrastructure
12. **Design & Aesthetics** - UX/UI, product design, creative problem-solving
13. **Public Policy, Governance & Impact** - Policy-making, government, social change

---

## Technology Stack

Both modules share:
- **Backend:** Django REST Framework
- **AI/LLM:** LangChain + Azure OpenAI (GPT-4) or Google Gemini
- **Database:** PostgreSQL
- **Authentication:** JWT
- **API Docs:** drf-spectacular (OpenAPI/Swagger)

---

## Quick Start for Developers

### 1. Set Up Both Modules

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, etc.

# Run migrations (order matters!)
python manage.py migrate domain_discovery
python manage.py migrate career_discovery

# Start server
python manage.py runserver
```

### 2. Test the Complete Flow

```bash
# 1. Create Stream & Subject Selection Session
POST /api/domain-discovery/
# Response: session_id

# 2. Answer 25 questions
POST /api/domain-discovery/<session_id>/messages/
# Body: {"content": "I love building robots..."}

# 3. Generate Domain Recommendations
POST /api/domain-discovery/<session_id>/recommendations/generate/

# 4. Create Career & Degree Selection Session (auto-links to domain session)
POST /api/career-discovery/
# Initial question will reference domain results!

# 5. Answer 20 questions
POST /api/career-discovery/<session_id>/messages/

# 6. Generate Career Recommendations
POST /api/career-discovery/<session_id>/recommendations/generate/
```

---

## Configuration

### Required Environment Variables

```bash
# Azure OpenAI (or Google Gemini)
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Optional: LLM Provider Selection
LLM_PROVIDER=azure  # or 'google'
```

### Django Settings

```python
INSTALLED_APPS = [
    # ...
    'domain_discovery',
    'career_discovery',
    'apps.profiles',  # Required for user profile data
    # ...
]
```

---

## Common Integration Patterns

### Check if User Can Start Career & Degree Selection 

```python
from domain_discovery.models import DomainSession

# Check if user has completed Stream & Subject Selection
has_completed_domain = DomainSession.objects.filter(
    user=user,
    is_active=False  # Completed sessions
).exists()

if not has_completed_domain:
    return {
        'error': 'Please complete Stream & Subject Selection first',
        'action_required': 'explore_domain_discovery'
    }
```

### Retrieve Complete User Journey

```python
# Get all domain sessions
domain_sessions = DomainSession.objects.filter(user=user).order_by('-created_at')

# Get all career sessions
career_sessions = CareerSession.objects.filter(user=user).order_by('-created_at')

# Get latest domain session with its linked career sessions
latest_domain = domain_sessions.first()
linked_career_sessions = latest_domain.career_sessions.all()
```

---

## Troubleshooting

### "Stream & Subject Selection required" when creating Career session
**Cause:** User hasn't completed Stream & Subject Selection  
**Solution:** Direct user to complete Stream & Subject Selection first

### Career & Degree Selection doesn't reference domains
**Cause:** Domain recommendations weren't generated  
**Solution:** Ensure Stream & Subject Selection session has recommendations before starting Career & Degree Selection 

### Domain context not appearing in Career questions
**Cause:** Foreign key not set or domain_context retrieval error  
**Solution:** Check logs for errors in `get_domain_discovery_context()`

---

## Performance Considerations

### For High Traffic

- Cache user profiles (Redis)
- Pre-fetch domain recommendations when creating career session
- Use database connection pooling
- Consider async task queue for LLM calls (Celery)

### For Better Quality

- Ensure Stream & Subject Selection is completed fully (all 25 questions)
- Generate domain recommendations before Career & Degree Selection 
- Use higher token limits for complex recommendations
- Fine-tune prompts based on user feedback

---

## Monitoring Metrics

### Stream & Subject Selection
- Session creation rate
- Completion rate (25/25 questions)
- Average time to complete
- Recommendation generation success rate

### Career & Degree Selection 
- Domain-to-career conversion rate
- Session creation rate (with domain prerequisite)
- Completion rate (20/20 questions)
- Phase 1 vs Phase 2 completion
- Recommendation acceptance/usefulness

### Integration Health
- % of career sessions with valid domain link
- Average domain recommendations per user
- Domain diversity in career recommendations

---

## Additional Resources

### Documentation
- [Stream & Subject Selection Full Docs](./domain-discovery.md)
- [Career & Degree Selection Full Docs](./career-discovery.md)
- [Prompting Guidelines](./prompting-guidegpt-5.2.md)

### API Documentation
- Swagger UI: `/api/schema/swagger-ui/`
- ReDoc: `/api/schema/redoc/`
- OpenAPI Schema: `/api/schema/`

### External Resources
- [LangChain Documentation](https://python.langchain.com/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/ai-services/openai/)
- [Django REST Framework](https://www.django-rest-framework.org/)

---

## Support

For questions or issues:
1. Check the module-specific documentation
2. Review the code comments in `services.py` and `langchain_service.py`
3. Check Django logs for detailed error traces
4. Consult LangChain documentation for LLM-related issues

---

**Last Updated:** February 3, 2026  
**Version:** 1.0  
**Python:** 3.10+  
**Django:** 4.x
