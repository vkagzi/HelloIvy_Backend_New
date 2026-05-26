# Career & Degree Selection Module

## Table of Contents
- [Product Overview](#product-overview)
- [Technical Architecture](#technical-architecture)
- [Relationship with Stream & Subject Selection](#relationship-with-domain-discovery)
- [API Documentation](#api-documentation)
- [Data Models](#data-models)
- [AI/LLM Integration](#aillm-integration)
- [User Flow](#user-flow)
- [Configuration](#configuration)
- [Development Guide](#development-guide)
- [Troubleshooting](#troubleshooting)

---

## Product Overview

### What is Career & Degree Selection ?

Career & Degree Selection is an AI-powered conversational tool that helps students identify specific career paths that align with their interests, strengths, and aspirations. **It's designed as a natural follow-up to Stream & Subject Selection**, building on the user's identified domains to provide detailed, actionable career recommendations.

### Key Features

- **Domain-Aware**: Leverages Stream & Subject Selection results to provide contextual career guidance
- **Two-Phase Conversation**: 10 Profile Builder questions + 10 Career Explorer questions
- **Profile-Driven**: Integrates comprehensive user profile data for personalized questions
- **Specific Career Paths**: Recommends concrete job titles with salary ranges and next steps
- **Detailed Recommendations**: Includes required skills, alignment points, and actionable guidance
- **Age-Appropriate**: Tailored conversations for students aged 10-22
- **Contextual Intelligence**: References domain recommendations and profile achievements naturally

### How It Differs from Stream & Subject Selection

| Feature | Stream & Subject Selection | Career & Degree Selection |
|---------|-----------------|------------------|
| **Focus** | Broad academic/interest areas | Specific job titles and career paths |
| **Questions** | 25 deep dive questions | 20 questions (10 profile + 10 explorer) |
| **Output** | 3 domain recommendations | Up to 8 career recommendations |
| **Prerequisites** | None (entry point) | Requires completed Stream & Subject Selection |
| **Context** | User profile only | User profile + Stream & Subject Selection results |
| **Granularity** | High-level (e.g., "Engineering") | Specific (e.g., "Software Engineer", "Robotics Engineer") |

### Workflow Integration

```
User Journey Flow:
1. Complete Stream & Subject Selection (25 questions) → Get top 3 domains
2. Start Career & Degree Selection (builds on domain results)
3. Answer 20 career-focused questions
4. Receive up to 8 specific career recommendations
```

### The Two Phases

#### Phase 1: Profile Builder (Questions 1-10)
- Explores interests, strengths, and preferences
- Validates and deepens understanding from Stream & Subject Selection
- Connects profile data to career potential
- Builds rapport and gathers nuanced insights

#### Phase 2: Career Explorer (Questions 11-20)
- Dives into specific career paths
- Explores day-to-day job activities
- Assesses alignment with student's goals
- Refines understanding of career preferences

---

## Technical Architecture

### Technology Stack

- **Backend Framework**: Django REST Framework
- **AI/LLM**: LangChain with Azure OpenAI (GPT-4)
- **Database**: PostgreSQL (via Django ORM)
- **Authentication**: JWT-based authentication
- **API Documentation**: drf-spectacular (OpenAPI/Swagger)

### Module Structure

```
career_discovery/
├── models.py              # Database models (CareerSession, CareerMessage, CareerRecommendation)
├── views.py               # REST API endpoints
├── serializers.py         # DRF serializers for request/response
├── services.py            # Business logic layer
├── langchain_service.py   # LLM integration with LangChain
├── urls.py                # URL routing
├── admin.py               # Django admin configuration
└── migrations/            # Database migrations
```

### System Components

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│     Django REST API Views       │
│  - Session Management           │
│  - Message Processing           │
│  - Recommendations              │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Career & Degree Selection Service      │
│  - Session lifecycle            │
│  - Message orchestration        │
│  - Domain context integration   │
│  - Recommendation generation    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   LangChain Service             │
│  - Initial Question (w/ domain) │
│  - Next Question Generation     │
│  - Career Recommendations       │
│  - Profile + Domain Analysis    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Azure OpenAI (GPT-4)          │
│  - Conversation Model           │
│  - Recommendations Model        │
└─────────────────────────────────┘
```

---

## Relationship with Stream & Subject Selection

### How Career & Degree Selection Uses Stream & Subject Selection Data

Career & Degree Selection is **tightly integrated** with Stream & Subject Selection. It uses:

1. **Domain Recommendations**: Top 3 domains from Stream & Subject Selection
2. **Conversation History**: All Q&A from the domain session
3. **Match Percentages**: How well each domain matched
4. **Domain Explanations**: Why each domain was recommended

### Domain Context Structure

The system passes this context to the AI:

```python
domain_context = {
    'session_id': 'domain_abc123',
    'recommendations': [
        {
            'title': 'Engineering & Applied Technology',
            'match_percentage': 92,
            'explanation': 'Strong alignment with technical interests...'
        },
        # Top 3 domains
    ],
    'messages': [
        {'type': 'user', 'content': 'I love building robots...'},
        {'type': 'bot', 'content': 'That's fascinating! Tell me more...'},
        # Conversation history
    ],
    'completed_at': '2026-02-03T10:30:00Z'
}
```

### Session Linking

Each `CareerSession` has a foreign key to `DomainSession`:

```python
domain_session = models.ForeignKey(
    'domain_discovery.DomainSession',
    on_delete=models.SET_NULL,
    related_name='career_sessions',
    null=True
)
```

This enables:
- Querying all career sessions for a domain session
- Tracking the user's complete discovery journey
- Providing context-aware recommendations

### Initial Question Strategy

The first question in Career & Degree Selection :
1. Greets the user by name
2. **References their top domain recommendations**
3. Acknowledges their achievements/profile highlights
4. Sets the stage for career exploration

Example:
> "Hey Sarah! In our last session, we discovered that Engineering & Applied Technology, Design & Aesthetics, and Entrepreneurship are your top-suited domains. I'm excited to dive deeper and help you explore specific careers in these areas. What excites you most about building and creating things?"

---

## API Documentation

### Base URL
```
/api/career-discovery/
```

### Authentication
All endpoints require JWT authentication via the `Authorization` header:
```
Authorization: Bearer <jwt_token>
```

### Endpoints

#### 1. Create New Session
**POST** `/`

Creates a new Career & Degree Selection session linked to the user's most recent Stream & Subject Selection session.

**Requirements:**
- User must have at least one Stream & Subject Selection session
- Automatically links to the most recent Stream & Subject Selection session

**Response:**
```json
{
  "session_id": "career_xyz789012345",
  "domain_session_id": "domain_abc123456789",
  "current_step": 0,
  "total_steps": 20,
  "current_phase": "profile",
  "is_active": true,
  "created_at": "2026-02-03T11:00:00Z",
  "updated_at": "2026-02-03T11:00:00Z",
  "messages": [
    {
      "message_id": "msg_12345678",
      "type": "bot",
      "content": "Hey there! In our last session, we discovered that Engineering & Applied Technology...",
      "step_number": 0,
      "phase": "profile",
      "timestamp": "2026-02-03T11:00:00Z"
    }
  ]
}
```

**Error Responses:**
```json
// No Stream & Subject Selection session found
{
  "error": "Stream & Subject Selection required",
  "message": "Please complete Stream & Subject Selection before starting Career & Degree Selection .",
  "action_required": "explore_domain_discovery"
}
```

#### 2. List Sessions
**GET** `/list/`

Returns all Career & Degree Selection sessions for the authenticated user.

**Response:**
```json
[
  {
    "session_id": "career_xyz789012345",
    "domain_session_id": "domain_abc123456789",
    "current_step": 5,
    "total_steps": 20,
    "current_phase": "profile",
    "is_active": true,
    "created_at": "2026-02-03T11:00:00Z",
    "updated_at": "2026-02-03T11:15:00Z"
  }
]
```

#### 3. Get Current Active Session
**GET** `/current/`

Returns the user's currently active career session.

#### 4. Send Message
**POST** `/<session_id>/messages/`

Sends a user message and receives the next question or completion message.

**Request:**
```json
{
  "content": "I love working with people and solving their problems"
}
```

**Response:**
```json
{
  "session_id": "career_xyz789012345",
  "user_message": "I love working with people and solving their problems",
  "bot_response": "That's wonderful! What kind of problems do you find most satisfying to solve?",
  "current_step": 6,
  "total_steps": 20,
  "is_complete": false,
  "phase": "profile"
}
```

#### 5. Get Message History
**GET** `/<session_id>/messages/history/`

Returns all messages in a session.

**Response:**
```json
{
  "session_id": "career_xyz789012345",
  "messages": [
    {
      "message_id": "msg_12345678",
      "type": "bot",
      "content": "Hey there!...",
      "step_number": 0,
      "phase": "profile",
      "timestamp": "2026-02-03T11:00:00Z"
    },
    {
      "message_id": "msg_23456789",
      "type": "user",
      "content": "I love working with people...",
      "step_number": 1,
      "phase": "profile",
      "timestamp": "2026-02-03T11:05:00Z"
    }
  ]
}
```

#### 6. Generate Recommendations
**POST** `/<session_id>/recommendations/generate/`

Generates AI-powered career recommendations based on the conversation and domain context.

**Response:**
```json
[
  {
    "id": 1,
    "career_title": "UX Designer",
    "salary_range": "$70,000 - $120,000",
    "match_percentage": 94,
    "required_skills": [
      "User Research",
      "Wireframing",
      "Prototyping",
      "Figma/Sketch",
      "Empathy"
    ],
    "next_steps": [
      "Take an online UX design course (Coursera, Udemy)",
      "Build a portfolio with 3-5 design projects",
      "Learn Figma or Adobe XD",
      "Join design communities on Dribbble or Behance",
      "Apply for UX internships"
    ],
    "description": "UX Designers create intuitive, user-friendly digital experiences by researching user needs, designing interfaces, and testing prototypes to ensure products are easy and enjoyable to use.",
    "why_recommended": "Based on your passion for solving people's problems and your interest in Design & Aesthetics from Stream & Subject Selection, UX Design is perfect. You mentioned loving creative problem-solving and understanding others' perspectives—these are core UX skills.",
    "alignment_points": [
      "Your interest in 'helping people' aligns with user-centered design",
      "Your creative thinking matches the design aspect",
      "Your analytical mindset fits user research requirements",
      "Domain match: Design & Aesthetics (92%)",
      "Your profile shows strong communication skills needed for UX"
    ],
    "rank": 1,
    "created_at": "2026-02-03T11:30:00Z"
  }
]
```

#### 7. Get Recommendations
**GET** `/<session_id>/recommendations/`

Retrieves existing recommendations for a session.

#### 8. End Session
**POST** `/<session_id>/end/`

Manually ends an active session.

#### 9. Health Check
**GET** `/health/`

System health check endpoint.

---

## Data Models

### CareerSession

Represents a Career & Degree Selection conversation session.

**Fields:**
- `user` (ForeignKey): User who owns the session
- `domain_session` (ForeignKey): Linked Stream & Subject Selection session (nullable)
- `session_id` (CharField): Unique session identifier
- `current_step` (IntegerField): Current question number (0-20)
- `total_steps` (IntegerField): Total questions (default: 20)
- `current_phase` (CharField): 'profile' or 'explorer'
- `is_active` (BooleanField): Whether session is ongoing
- `created_at` (DateTimeField): Session creation timestamp
- `updated_at` (DateTimeField): Last update timestamp

**Methods:**
- `get_current_phase()`: Returns 'profile' for steps 0-9, 'explorer' for 10-19

**Relationships:**
- **One-to-Many** with `CareerMessage`
- **One-to-Many** with `CareerRecommendation`
- **Many-to-One** with `DomainSession`

### CareerMessage

Stores individual conversation messages.

**Fields:**
- `session` (ForeignKey): Associated session
- `message_id` (CharField): Unique message identifier
- `type` (CharField): 'bot' or 'user'
- `content` (TextField): Message text
- `step_number` (IntegerField): Question number
- `phase` (CharField): 'profile' or 'explorer'
- `timestamp` (DateTimeField): Message timestamp

**Ordering:** By timestamp (ascending)

### CareerRecommendation

Stores generated career recommendations.

**Fields:**
- `session` (ForeignKey): Associated session
- `career_title` (CharField): Specific job title (e.g., "Software Engineer")
- `salary_range` (CharField): Expected salary range (e.g., "$80,000 - $130,000")
- `match_percentage` (IntegerField): Match score (0-100)
- `required_skills` (JSONField): List of required skills
- `next_steps` (JSONField): Actionable steps to pursue this career
- `description` (TextField): Day-to-day role description
- `why_recommended` (TextField): Personalized explanation tied to student's responses
- `alignment_points` (JSONField): Specific mappings from student's words to career aspects
- `rank` (IntegerField): Recommendation ranking
- `created_at` (DateTimeField): Creation timestamp

**Ordering:** By rank, then match_percentage (descending)

**Example Data:**
```python
{
    "career_title": "Data Scientist",
    "salary_range": "$85,000 - $140,000",
    "match_percentage": 88,
    "required_skills": ["Python", "Statistics", "Machine Learning", "SQL", "Data Visualization"],
    "next_steps": [
        "Learn Python programming",
        "Take statistics and calculus courses",
        "Complete Kaggle competitions",
        "Build 3-5 data projects for portfolio",
        "Apply for data analytics internships"
    ],
    "description": "Data Scientists analyze large datasets to extract insights...",
    "why_recommended": "Your engineering background and analytical thinking...",
    "alignment_points": [
        "Engineering domain match (92%)",
        "Mentioned loving problem-solving with data",
        "Strong math background from profile"
    ]
}
```

---

## AI/LLM Integration

### LangChain Service Architecture

The `langchain_service.py` module provides AI-powered functionality using LangChain with Azure OpenAI.

### Key AI Functions

#### 1. Generate Initial Question
```python
generate_initial_question(
    user_name: str,
    user_profile: Dict[str, Any],
    domain_context: Dict[str, Any]
) -> str
```

Creates a personalized opening message that:
- Greets the user by name
- **References top domain recommendations from Stream & Subject Selection**
- Acknowledges profile highlights (school, achievements, interests)
- Asks an engaging first question
- Keeps message under 50 words

**Example Output:**
> "Hey Alex! In our last session, we discovered that Engineering & Applied Technology and Entrepreneurship are your top domains. I noticed you're captain of your robotics team—that's awesome! What do you love most about building and leading projects?"

#### 2. Generate Next Question
```python
generate_next_question(
    current_step: int,
    messages: List[Dict],
    user_response: str,
    user_profile: Dict[str, Any],
    domain_context: Dict[str, Any]
) -> str
```

Generates personalized follow-up questions based on:
- Full conversation history
- User profile data
- Stream & Subject Selection insights
- Current phase (Profile Builder vs Career Explorer)
- Progress (question number)

**Question Guidelines:**
- Exactly ONE question at a time
- ≤18 words
- No multiple questions, lists, or numbering
- References profile data naturally
- Avoids repetition
- Blends interest discovery with career exploration

**Phase-Specific Focus:**

**Profile Builder (Q1-10):**
- Explore interests, strengths, preferences
- Validate Stream & Subject Selection findings
- Build rapport and gather nuanced insights

**Career Explorer (Q11-20):**
- Dive into specific careers
- Explore day-to-day activities
- Assess alignment with goals

#### 3. Generate Career Recommendations
```python
generate_recommendations(
    messages: List[Dict],
    user_profile: Dict[str, Any],
    domain_context: Dict[str, Any]
) -> List[Dict]
```

Analyzes the complete conversation (20 questions) plus profile and domain data to generate up to 8 career recommendations.

**Output Schema:**
```python
{
    "career_title": str,           # Specific job title
    "salary_range": str,           # "$XX,000 - $XX,000"
    "match_percentage": int,       # 0-100
    "required_skills": List[str],  # Max 10 skills
    "next_steps": List[str],       # Max 5 actionable steps
    "description": str,            # Day-to-day explanation
    "why_recommended": str,        # Personalized explanation
    "alignment_points": List[str]  # Max 5 specific alignments
}
```

**Recommendation Quality:**
- Specific and practical
- Directly tied to conversation responses
- Informed by full profile data
- Aligned with Stream & Subject Selection results
- Age-appropriate and actionable
- Tailored to educational stage

### Context Integration

The AI receives three layers of context:

1. **User Profile Context** (from `apps.profiles`)
   - Personal details (name, school, grade)
   - Educational background (courses, GPA, test scores)
   - Achievements and awards
   - Extracurricular activities
   - Interests and goals

2. **Stream & Subject Selection Context** (from `domain_discovery`)
   - Top 3 domain recommendations
   - Match percentages
   - Explanations for each domain
   - Key conversation insights

3. **Career Conversation History**
   - All messages in current session
   - User responses
   - Bot questions

### Prompt Engineering

#### System Prompt Strategy

```
Role: "HelloIvy Career Co-Pilot"
Audience: Students aged 10-22
Tone: Warm, encouraging, authentic
Approach: Safe space for discovery, emphasis on unique talents
```

#### Context Formatting

**User Profile:**
```
Name: Sarah Johnson
School: Lincoln High School
Grade: 11th
Achievements: Science Fair Winner (2025), Robotics Team Captain
Interests: Programming, AI, Helping Others
GPA: 3.9
```

**Stream & Subject Selection Results:**
```
Top 3 Recommended Domains:
1. Engineering & Applied Technology (92% match)
   Reason: Strong technical interests and problem-solving abilities
2. Design & Aesthetics (85% match)
   Reason: Creative approach to solving problems
3. Social Sciences (78% match)
   Reason: Interest in understanding human behavior
```

#### Output Specifications

- Questions: ≤18 words
- Initial greeting: ≤50 words
- No quotes, prefixes, or explanations
- Natural, conversational language
- Age-appropriate vocabulary

### LLM Configuration

**Conversation LLM:**
```python
temperature=0.7        # Balanced creativity
max_tokens=200         # Short, focused responses
```

**Recommendations LLM:**
```python
temperature=0.7        # Balanced creativity
max_tokens=2500        # Detailed recommendations
```

---

## User Flow

### Complete User Journey

```
Prerequisites:
✓ User has completed Stream & Subject Selection
✓ Domain recommendations generated

1. Start Career & Degree Selection 
   ↓
2. Initial Greeting (references domain results)
   ↓
3. Profile Builder Phase (Questions 1-10)
   │  - Explore interests and strengths
   │  - Validate domain findings
   │  - Build deeper understanding
   ↓
4. Career Explorer Phase (Questions 11-20)
   │  - Dive into specific careers
   │  - Explore day-to-day activities
   │  - Assess career alignment
   ↓
5. Session Complete
   ↓
6. Generate Career Recommendations
   │  - AI analyzes full conversation
   │  - Integrates profile + domain data
   │  - Creates up to 8 career recommendations
   ↓
7. View Career Recommendations
   │  - Specific job titles
   │  - Salary ranges
   │  - Required skills
   │  - Next steps
   │  - Why recommended
```

### Phase Transition

**Phase 1 → Phase 2 Transition (Step 10):**
- System automatically transitions at question 10
- No explicit user action required
- Questions become more career-specific
- AI maintains context from Phase 1

### Progress Tracking

Track progress via:
- `current_step`: Current question (0-20)
- `current_phase`: 'profile' or 'explorer'
- `is_complete`: Boolean when all 20 questions answered

**Progress Calculation:**
```python
progress_percentage = (current_step / total_steps) * 100

# Phase determination
if current_step < 10:
    current_phase = 'profile'
else:
    current_phase = 'explorer'
```

---

## Configuration

### Environment Variables

```bash
# Azure OpenAI Configuration (required)
AZURE_OPENAI_API_KEY=<your_key>
AZURE_OPENAI_ENDPOINT=<your_endpoint>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment_name>
```

### Django Settings

```python
# In settings.py
INSTALLED_APPS = [
    # ...
    'domain_discovery',  # Required prerequisite
    'career_discovery',
    'apps.profiles',     # For user profile data
    # ...
]
```

### Database Configuration

Run migrations in order:

```bash
# Stream & Subject Selection first (prerequisite)
python manage.py migrate domain_discovery

# Then Career & Degree Selection 
python manage.py migrate career_discovery
```

### Admin Configuration

Access Django admin to:
- View career sessions
- Monitor messages
- Review recommendations
- Check domain session linkage

```python
# Access at /admin/career_discovery/
```

---

## Development Guide

### Setting Up Development Environment

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add Azure OpenAI credentials
   ```

3. **Run Migrations**
   ```bash
   python manage.py migrate domain_discovery
   python manage.py migrate career_discovery
   ```

4. **Create Test Data**
   ```bash
   # Create a test user and domain session first
   python manage.py shell
   ```

5. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

### Testing Workflow

**Complete User Journey Test:**

```bash
# 1. Create domain session
POST /api/domain-discovery/

# 2. Complete domain questions (25 times)
POST /api/domain-discovery/<session_id>/messages/

# 3. Generate domain recommendations
POST /api/domain-discovery/<session_id>/recommendations/generate/

# 4. Create career session (should reference domain results)
POST /api/career-discovery/

# 5. Complete career questions (20 times)
POST /api/career-discovery/<session_id>/messages/

# 6. Generate career recommendations
POST /api/career-discovery/<session_id>/recommendations/generate/
```

### Modifying Question Count

Edit constants in `services.py`:
```python
class CareerDiscoveryService:
    def __init__(self):
        self.total_steps = 20  # Change as needed
```

And update phase logic in `models.py`:
```python
def get_current_phase(self):
    if self.current_step < 10:  # Adjust threshold
        return 'profile'
    return 'explorer'
```

### Custom Prompts

Prompts are in `langchain_service.py`:
- `CAREER_DISCOVERY_SYSTEM_PROMPT` - Main conversation guide
- `RECOMMENDATIONS_SYSTEM_PROMPT` - Recommendation generation

Edit these to fine-tune AI behavior.

### Adding New Career Fields

To add new recommendation fields:

1. **Update Model** (`models.py`):
   ```python
   class CareerRecommendation(models.Model):
       # Add new field
       work_life_balance = models.CharField(max_length=100, blank=True)
   ```

2. **Update Pydantic Schema** (`langchain_service.py`):
   ```python
   class CareerRecommendationSchema(BaseModel):
       work_life_balance: str = Field(...)
   ```

3. **Update Serializer** (`serializers.py`):
   ```python
   class CareerRecommendationSerializer(serializers.ModelSerializer):
       class Meta:
           fields = [..., 'work_life_balance']
   ```

4. **Run Migration**:
   ```bash
   python manage.py makemigrations career_discovery
   python manage.py migrate career_discovery
   ```

---

## Troubleshooting

### Common Issues

#### 1. **Cannot Create Career Session - Stream & Subject Selection Required**
**Symptom:** 400 error: "Stream & Subject Selection required"

**Solutions:**
- Ensure user has completed at least one Stream & Subject Selection session
- Check that Stream & Subject Selection session has `is_active=False` (completed)
- Verify user authentication is working
- Query: `DomainSession.objects.filter(user=user)` should return results

#### 2. **Domain Context Not Appearing in Questions**
**Symptom:** Initial question doesn't reference domain results

**Solutions:**
- Check `domain_session` foreign key is populated
- Verify domain session has recommendations
- Review `get_domain_discovery_context()` output in logs
- Check `format_domain_context_for_prompt()` is formatting correctly

**Debug:**
```python
# In services.py, add logging
domain_context = self.get_domain_discovery_context(session)
print("Domain context:", domain_context)
```

#### 3. **Recommendations Missing Alignment with Domain**
**Symptom:** Career recommendations don't align with domain results

**Solutions:**
- Ensure domain context is passed to `generate_recommendations()`
- Check that domain recommendations exist in database
- Review prompt to ensure domain alignment is emphasized
- Verify LLM is receiving domain context in system prompt

#### 4. **Questions Are Repetitive**
**Symptom:** AI asks similar questions multiple times

**Solutions:**
- Ensure full conversation history is passed to LLM
- Check that `messages` list is ordered correctly by timestamp
- Verify `current_step` is incrementing
- Review conversation history building in `generate_next_question()`

#### 5. **Phase Transition Not Working**
**Symptom:** Still in 'profile' phase after question 10

**Solutions:**
- Check `get_current_phase()` logic in model
- Verify `current_step` is updating correctly
- Ensure `session.save()` is called after updating step
- Review phase determination in `process_message()`

#### 6. **LLM Response Errors**
**Symptom:** 500 error when generating questions

**Solutions:**
- Verify Azure OpenAI credentials
- Check API quota and rate limits
- Review error logs for specific LLM errors
- Test with fallback questions
- Ensure token limits aren't exceeded

**Debug:**
```python
try:
    response = self.llm.invoke(messages)
except Exception as e:
    print(f"LLM Error: {str(e)}")
    print(f"Messages sent: {messages}")
```

#### 7. **Recommendations Generation Fails**
**Symptom:** Error on `/recommendations/generate/`

**Solutions:**
- Ensure 20 questions are completed
- Check that session has messages
- Verify domain context is available
- Review LLM token limits (recommendations need more tokens)
- Check JSON parsing errors in output

### Performance Optimization

**For Faster Responses:**
- Cache user profiles (Redis)
- Pre-format domain context
- Use database select_related for domain_session
- Implement response caching for common patterns

**For Better Quality:**
- Increase `max_tokens` for recommendations (currently 2500)
- Fine-tune temperature (0.7 balanced, lower for consistency)
- Add more context about user's goals
- Include more domain conversation samples

### Monitoring

**Key Metrics:**
- Session creation rate
- Average completion rate (20/20 questions)
- Phase 1 vs Phase 2 completion rates
- LLM response latency
- Recommendation generation success rate
- Domain-to-career conversion rate

**Health Checks:**
```bash
# Check system health
GET /api/career-discovery/health/

# Verify domain session linkage
SELECT cs.session_id, ds.session_id as domain_session
FROM career_careersession cs
LEFT JOIN domain_discovery_domainsession ds ON cs.domain_session_id = ds.id
WHERE cs.domain_session_id IS NULL;  -- Should be empty
```

---

## API Response Examples

### Successful Session Creation with Domain Reference

```json
{
  "session_id": "career_a1b2c3d4e5f6",
  "domain_session_id": "domain_x9y8z7w6v5u4",
  "current_step": 0,
  "total_steps": 20,
  "current_phase": "profile",
  "is_active": true,
  "created_at": "2026-02-03T14:30:00.000Z",
  "updated_at": "2026-02-03T14:30:00.000Z",
  "messages": [
    {
      "message_id": "msg_98765432",
      "type": "bot",
      "content": "Hey Alex! In our last session, we discovered that Engineering & Applied Technology, Design & Aesthetics, and Entrepreneurship are your top-suited domains. I noticed you're captain of your school's robotics team—that's incredible! What excites you most about building and creating?",
      "step_number": 0,
      "phase": "profile",
      "timestamp": "2026-02-03T14:30:00.000Z"
    }
  ]
}
```

### Complete Recommendation Example

```json
{
  "id": 42,
  "career_title": "Product Manager",
  "salary_range": "$90,000 - $150,000",
  "match_percentage": 91,
  "required_skills": [
    "Product Strategy",
    "User Research",
    "Data Analysis",
    "Communication",
    "Project Management",
    "Technical Understanding"
  ],
  "next_steps": [
    "Take a product management course (Coursera, Product School)",
    "Build a product from idea to launch (even a small app)",
    "Learn basic SQL and data analysis",
    "Read 'Inspired' by Marty Cagan",
    "Join product management communities (Product Hunt, Mind the Product)"
  ],
  "description": "Product Managers are the 'CEOs of the product.' They define what to build, why to build it, and work with engineering, design, and business teams to bring products to life. They balance user needs, business goals, and technical feasibility.",
  "why_recommended": "Your combination of technical understanding (Engineering domain, 92% match), creative problem-solving (Design domain, 85%), and leadership (robotics team captain) makes Product Management ideal. You mentioned loving to 'bring ideas to life and lead teams'—that's the essence of PM work.",
  "alignment_points": [
    "Engineering domain match (92%) provides technical foundation",
    "Design domain match (85%) shows user-centric thinking",
    "Leadership experience as robotics captain aligns with PM role",
    "You mentioned 'loving to coordinate between people and technology'",
    "Your analytical skills from advanced math courses support data-driven decisions"
  ],
  "rank": 1,
  "created_at": "2026-02-03T15:00:00.000Z"
}
```

---

## Integration Points

### With Stream & Subject Selection Module

**Required Data Flow:**
```
Stream & Subject Selection → Career & Degree Selection 
- Session reference (foreign key)
- Top 3 domain recommendations
- Match percentages
- Conversation insights
- Completion timestamp
```

**Code Reference:**
```python
# In services.py
domain_context = self.get_domain_discovery_context(session)

# Returns:
{
    'session_id': str,
    'recommendations': [{'title': str, 'match_percentage': int, ...}],
    'messages': [{'type': str, 'content': str, ...}],
    'completed_at': str (ISO timestamp)
}
```

### With User Profiles Module

**Profile Data Used:**
- Personal details (name, school, grade)
- Educational background
- Achievements and awards
- Extracurricular activities
- Test scores and GPA
- Stated interests and goals

**Code Reference:**
```python
from utils.profile_helpers import get_user_profile_data
user_profile = get_user_profile_data(user)
```

---

## Future Enhancements

**Planned Features:**
- Multi-language support
- Real-time streaming responses
- Career pathway visualization
- Integration with job/internship databases
- Salary data from live APIs
- Video career interviews
- Mentorship matching
- College major recommendations linked to careers
- Skills gap analysis with learning resources

**Advanced Analytics:**
- Track domain-to-career conversion patterns
- Identify most popular career paths by domain
- A/B test different question strategies
- Measure recommendation acceptance rates

---

## Support and Resources

**Related Documentation:**
- [Stream & Subject Selection Module](../docs/domain-discovery.md)
- [User Profiles Module](../apps/profiles/README.md)
- LangChain Docs: https://python.langchain.com/
- Azure OpenAI Docs: https://learn.microsoft.com/azure/ai-services/openai/

**Code Navigation:**
- Initial Question Logic: `langchain_service.py:638`
- Domain Context Formatting: `langchain_service.py:608`
- Session Creation: `services.py:74`
- Recommendation Generation: `langchain_service.py:750+`

---

**Last Updated:** February 3, 2026  
**Module Version:** 1.0  
**Prerequisites:** Stream & Subject Selection Module  
**Django Version:** 4.x  
**Python Version:** 3.10+
