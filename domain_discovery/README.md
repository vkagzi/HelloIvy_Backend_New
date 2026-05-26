# Stream & Subject Selection Module

## Table of Contents
- [Product Overview](#product-overview)
- [Technical Architecture](#technical-architecture)
- [API Documentation](#api-documentation)
- [Data Models](#data-models)
- [AI/LLM Integration](#aillm-integration)
- [User Flow](#user-flow)
- [Configuration](#configuration)
- [Development Guide](#development-guide)
- [Troubleshooting](#troubleshooting)

---

## Product Overview

### What is Stream & Subject Selection?

The Stream & Subject Selection module is an AI-powered conversational tool that helps students identify their ideal academic and career domains through personalized questions and intelligent analysis. It guides users through a structured discovery process to match them with one or more of 13 predefined domains based on their interests, strengths, and aspirations.

### Key Features

- **Personalized Conversations**: AI-generated questions tailored to each student's profile
- **13 Predefined Domains**: Comprehensive coverage of academic and career paths
- **Intelligent Matching**: LLM-powered analysis to recommend best-fit domains
- **Progress Tracking**: Real-time progress indicators and phase tracking
- **Rich Recommendations**: Detailed domain insights with match percentages, sub-domains, exploration activities, and career paths
- **Multi-format Results**: PDF reports, conversation transcripts, and downloadable summaries
- **Voice Support**: Audio transcription and text-to-speech capabilities

### The 13 Predefined Domains

1. **Pure Science** - Research, experimentation, scientific discovery
2. **Arts** - Creative expression through art, music, design, performance
3. **Humanities** - Literature, philosophy, history, culture, critical thinking
4. **Business** - Leadership, strategy, management, entrepreneurship
5. **Finance** - Markets, investments, financial analysis, economics
6. **Entrepreneurship** - Building ventures, innovation, startup culture
7. **Law** - Justice, legal systems, policy, advocacy
8. **Social Sciences** - Psychology, sociology, human behavior research
9. **Health & Life Science** - Medicine, healthcare, biology, wellness
10. **Sports/Athletics** - Professional sports, coaching, sports management
11. **Engineering & Applied Technology** - Building systems, software, infrastructure
12. **Design & Aesthetics** - UX/UI, product design, creative problem-solving
13. **Public Policy, Governance & Impact** - Policy-making, government, social change

### User Categories

The system adapts questions and recommendations for three user segments:

- **School Students** (High School, 9th-12th grade)
- **Undergrad/Postgrad** (College and graduate students)
- **Working Professionals** (Post-college, employed individuals)

---

## Technical Architecture

### Technology Stack

- **Backend Framework**: Django REST Framework
- **AI/LLM**: LangChain with Azure OpenAI (GPT-4) or Google Gemini
- **Database**: PostgreSQL (via Django ORM)
- **Audio Processing**: Azure OpenAI Whisper API, Azure Text-to-Speech
- **Authentication**: JWT-based authentication
- **API Documentation**: drf-spectacular (OpenAPI/Swagger)

### Module Structure

```
domain_discovery/
├── models.py              # Database models (DomainSession, DomainMessage, DomainRecommendation)
├── views.py               # REST API endpoints
├── serializers.py         # DRF serializers for request/response
├── services.py            # Business logic layer
├── langchain_service.py   # LLM integration with LangChain
├── urls.py                # URL routing
├── constants.py           # Domain definitions and RIASEC config
├── llm_logging.py         # LLM request/response logging utilities
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
│  - Report Generation            │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Stream & Subject Selection Service      │
│  - Session lifecycle            │
│  - Message orchestration        │
│  - Recommendation generation    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   LangChain Service             │
│  - Deep Dive Questions          │
│  - RIASEC Scoring (optional)    │
│  - Domain Recommendations       │
│  - Profile Analysis             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Azure OpenAI / Google Gemini  │
│  - GPT-4 / Gemini Pro           │
│  - Whisper (audio transcription)│
│  - TTS (text-to-speech)         │
└─────────────────────────────────┘
```

---

## API Documentation

### Base URL
```
/api/domain-discovery/
```

### Authentication
All endpoints require JWT authentication via the `Authorization` header:
```
Authorization: Bearer <jwt_token>
```

### Endpoints

#### 1. Create New Session
**POST** `/`

Creates a new Stream & Subject Selection session and returns the first question.

**Response:**
```json
{
  "session_id": "domain_abc123456789",
  "current_step": 0,
  "total_steps": 25,
  "current_phase": "deepdive",
  "deepdive_questions_count": 25,
  "deepdive_completed": 0,
  "is_active": true,
  "created_at": "2026-02-03T10:00:00Z",
  "updated_at": "2026-02-03T10:00:00Z",
  "messages": [
    {
      "message_id": "msg_12345678",
      "type": "bot",
      "content": "Hi there! I'm excited to help you...",
      "question_type": "deepdive",
      "choices": [],
      "timestamp": "2026-02-03T10:00:00Z"
    }
  ]
}
```

#### 2. List Sessions
**GET** `/list/`

Returns all Stream & Subject Selection sessions for the authenticated user.

**Response:**
```json
[
  {
    "session_id": "domain_abc123456789",
    "current_step": 5,
    "total_steps": 25,
    "current_phase": "deepdive",
    "deepdive_completed": 5,
    "is_active": true,
    "created_at": "2026-02-03T10:00:00Z",
    "updated_at": "2026-02-03T10:15:00Z"
  }
]
```

#### 3. Get Current Active Session
**GET** `/current/`

Returns the user's currently active session.

#### 4. Send Message
**POST** `/<session_id>/messages/`

Sends a user message and receives the next question or completion message.

**Request:**
```json
{
  "content": "I love building things and solving technical problems"
}
```

**Response:**
```json
{
  "session_id": "domain_abc123456789",
  "bot_response": "That's interesting! Can you tell me more about...",
  "question_type": "deepdive",
  "choices": [],
  "current_step": 6,
  "deepdive_completed": 6,
  "is_complete": false,
  "phase": "deepdive",
  "progress_percentage": 24,
  "questions_completed": 6
}
```

#### 5. Get Message History
**GET** `/<session_id>/messages/history/`

Returns all messages in a session.

#### 6. Generate Recommendations
**POST** `/<session_id>/recommendations/generate/`

Generates AI-powered domain recommendations based on the conversation.

**Response:**
```json
[
  {
    "id": 1,
    "domain_title": "Engineering & Applied Technology",
    "category": "STEM",
    "match_percentage": 92,
    "key_interests": ["Problem-solving", "Building", "Technology"],
    "sub_domains": ["Software Engineering", "Robotics", "AI/ML"],
    "related_subjects": ["Mathematics", "Physics", "Computer Science"],
    "description": "Engineering focuses on applying scientific principles...",
    "why_recommended": "Based on your passion for building...",
    "exploration_activities": [
      "Join a coding bootcamp",
      "Participate in hackathons"
    ],
    "potential_careers": [
      "Software Engineer",
      "Data Scientist",
      "Robotics Engineer"
    ],
    "rank": 1,
    "created_at": "2026-02-03T10:30:00Z"
  }
]
```

#### 7. Get Recommendations
**GET** `/<session_id>/recommendations/`

Retrieves existing recommendations for a session.

#### 8. Generate PDF Report
**POST** `/<session_id>/report/`

Generates a comprehensive PDF report with recommendations.

#### 9. Download PDF Report
**GET** `/<session_id>/report/download/?token=<jwt_token>`

Downloads the generated PDF report.

#### 10. Get Results Summary
**GET** `/<session_id>/results/`

Returns a summary of session results including progress and recommendations.

#### 11. Get Transcript
**GET** `/<session_id>/transcript/`

Returns the full conversation transcript.

#### 12. Download Transcript
**GET** `/<session_id>/transcript/download/?token=<jwt_token>`

Downloads the conversation transcript as a text file.

#### 13. Transcribe Audio
**POST** `/<session_id>/transcribe/`

Transcribes audio input to text using Azure Whisper API.

**Request:** (multipart/form-data)
```
audio: <audio_file>
```

#### 14. Generate Speech
**POST** `/<session_id>/speech/`

Converts text to speech using Azure TTS.

#### 15. End Session
**POST** `/<session_id>/end/`

Manually ends an active session.

#### 16. Health Check
**GET** `/health/`

System health check endpoint.

---

## Data Models

### DomainSession

Represents a Stream & Subject Selection conversation session.

**Fields:**
- `user` (ForeignKey): User who owns the session
- `session_id` (CharField): Unique session identifier
- `current_step` (IntegerField): Current question number
- `total_steps` (IntegerField): Total questions (default: 25)
- `riasec_scores` (JSONField): RIASEC personality scores (optional)
- `is_active` (BooleanField): Whether session is ongoing
- `created_at` (DateTimeField): Session creation timestamp
- `updated_at` (DateTimeField): Last update timestamp

**Properties:**
- `current_phase`: Returns 'riasec' or 'deepdive'
- `riasec_completed`: Count of completed RIASEC questions
- `deepdive_completed`: Count of completed deep dive questions

**Constants:**
- `RIASEC_QUESTIONS_COUNT = 0` (currently disabled)
- `DEEPDIVE_QUESTIONS_COUNT = 25`

### DomainMessage

Stores individual conversation messages.

**Fields:**
- `session` (ForeignKey): Associated session
- `message_id` (CharField): Unique message identifier
- `type` (CharField): 'bot' or 'user'
- `content` (TextField): Message text
- `question_type` (CharField): 'riasec', 'deepdive', or 'general'
- `choices` (JSONField): Multiple choice options (for RIASEC)
- `timestamp` (DateTimeField): Message timestamp

**Indexes:**
- `(session, timestamp)`
- `(session, type)`

### DomainRecommendation

Stores generated domain recommendations.

**Fields:**
- `session` (ForeignKey): Associated session
- `domain_title` (CharField): One of the 13 predefined domains
- `category` (CharField): Domain category (e.g., STEM, Arts)
- `match_percentage` (IntegerField): Match score (0-100)
- `key_interests` (JSONField): List of identified interests
- `sub_domains` (JSONField): Specific sub-areas
- `related_subjects` (JSONField): Relevant school subjects
- `description` (TextField): Domain description
- `why_recommended` (TextField): Personalized explanation
- `exploration_activities` (JSONField): Suggested activities
- `potential_careers` (JSONField): Career path previews
- `rank` (IntegerField): Recommendation ranking
- `created_at` (DateTimeField): Creation timestamp

**Ordering:** By rank, then match_percentage (descending)

### PredefinedDomain

Master list of available domains.

**Fields:**
- `title` (CharField): Domain name (unique)
- `description` (TextField): Domain description
- `is_active` (BooleanField): Whether domain is available
- `order` (IntegerField): Display order
- `created_at` / `updated_at` (DateTimeField)

---

## AI/LLM Integration

### LangChain Service Architecture

The `langchain_service.py` module provides AI-powered functionality using LangChain with Azure OpenAI or Google Gemini.

### Key AI Functions

#### 1. Deep Dive Question Generation
```python
generate_deepdive_question(
    current_step: int,
    messages: List[Dict],
    user_response: str,
    user_profile: Dict,
    riasec_scores: Optional[Dict],
    total_questions: int
) -> str
```

Generates personalized questions based on:
- Conversation history
- User profile (academic level, interests, achievements)
- Progress through the questionnaire
- Strategic theme diversity to avoid repetition

**Prompt Strategy:**
- Under 30 words per question
- Rotates between different profile aspects
- Focuses on Topics, Verbs, and Environment
- Ensures diverse coverage across all questions

#### 2. Domain Recommendation Generation
```python
generate_recommendations(
    messages: List[Dict],
    user_profile: Dict
) -> List[Dict]
```

Analyzes the entire conversation to generate top 3 domain recommendations with:
- Match percentage (0-100)
- Key interests identified
- Sub-domains
- Related subjects
- Personalized explanation
- Exploration activities
- Potential careers

**Output Format:** JSON array of recommendation objects

#### 3. RIASEC Scoring (Optional)
```python
_calculate_riasec_scores_with_llm(
    messages: List[Dict],
    user_profile: Dict
) -> Dict[str, int]
```

Calculates RIASEC personality scores:
- **R**ealistic
- **I**nvestigative
- **A**rtistic
- **S**ocial
- **E**nterprising
- **C**onventional

Each dimension scored 0-100 based on conversation analysis.

### LLM Provider Configuration

The module supports two LLM providers:

**Azure OpenAI** (default):
```python
LLM_PROVIDER = 'azure'
# Uses GPT-4 via Azure OpenAI Service
```

**Google Gemini**:
```python
LLM_PROVIDER = 'google'
# Uses Gemini Pro model
```

### Prompt Engineering

All prompts follow best practices:
- Clear role definition ("HelloIvy Stream & Subject Selection Coach")
- Structured context sections (user profile, conversation progress)
- Explicit output specifications
- Few-shot examples where applicable
- Theme diversity requirements to prevent repetition

### LLM Logging

The `llm_logging.py` module provides sanitized logging:
- Removes sensitive PII (email, phone, location)
- Logs system prompts and LLM responses
- Tracks token usage and performance
- Aids in debugging and prompt optimization

---

## User Flow

### Complete User Journey

```
1. Session Creation
   ↓
2. Initial Greeting + First Question
   ↓
3. Conversation Loop (25 questions)
   │  - User responds
   │  - AI analyzes and generates next question
   │  - Progress tracked
   ↓
4. Session Complete
   ↓
5. Generate Recommendations
   │  - AI analyzes full conversation
   │  - Calculates match percentages
   │  - Creates 3 personalized recommendations
   ↓
6. View Results
   │  - Domain recommendations
   │  - Match percentages
   │  - Exploration activities
   │  - Career paths
   ↓
7. Download Report/Transcript (Optional)
```

### Phase Transitions

The system currently operates in a single phase:

**Deep Dive Phase** (Questions 1-25):
- AI-generated personalized questions
- Theme diversity enforcement
- Profile-based adaptations
- Progress tracking

*(Note: RIASEC phase is currently disabled but can be re-enabled)*

### Progress Tracking

Users can track progress via:
- `current_step`: Current question number
- `progress_percentage`: (current_step / total_steps) × 100
- `questions_completed`: Total answered questions
- `is_complete`: Boolean flag when all questions answered

---

## Configuration

### Environment Variables

```bash
# LLM Provider Selection
LLM_PROVIDER=azure  # or 'google'

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=<your_key>
AZURE_OPENAI_ENDPOINT=<your_endpoint>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment_name>

# Google Gemini Configuration (if using Google)
GOOGLE_API_KEY=<your_key>

# Azure Speech Services (for audio features)
AZURE_SPEECH_KEY=<your_key>
AZURE_SPEECH_REGION=<region>
```

### Django Settings

```python
# In settings.py
INSTALLED_APPS = [
    # ...
    'domain_discovery',
    # ...
]

# LLM Provider
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'azure')
```

### Database Configuration

The module uses standard Django models. Run migrations:

```bash
python manage.py makemigrations domain_discovery
python manage.py migrate domain_discovery
```

### Admin Configuration

Access Django admin to manage:
- Predefined domains
- View sessions and messages
- Monitor recommendations

```python
# Access at /admin/domain_discovery/
```

---

## Development Guide

### Setting Up Development Environment

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create Predefined Domains**
   ```bash
   python manage.py shell
   from domain_discovery.models import PredefinedDomain
   # Create domains from DOMAIN_CONFIG
   ```

5. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

### Testing

Run the test suite:
```bash
python manage.py test domain_discovery
```

### Adding New Domains

1. Update `DOMAIN_CONFIG` in `constants.py`
2. Create corresponding `PredefinedDomain` entries
3. Update LangChain prompts to include new domain
4. Run tests to validate

### Modifying Question Count

Edit the class constants in `models.py`:
```python
class DomainSession(models.Model):
    RIASEC_QUESTIONS_COUNT = 0  # Adjust as needed
    DEEPDIVE_QUESTIONS_COUNT = 25  # Adjust as needed
```

### Custom LLM Prompts

Prompts are defined in `langchain_service.py`. Key prompts:
- `DEEPDIVE_QUESTION_GENERATION_PROMPT`
- `RECOMMENDATION_GENERATION_PROMPT`
- `RIASEC_SCORING_PROMPT`

Edit these to fine-tune AI behavior.

### Debugging LLM Interactions

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check sanitized LLM logs:
```python
from domain_discovery.llm_logging import log_llm_messages
# Logs are automatically generated for each LLM call
```

---

## Troubleshooting

### Common Issues

#### 1. **Session Creation Fails**
**Symptom:** 500 error on POST `/`

**Solutions:**
- Check Azure OpenAI credentials
- Verify user profile exists
- Check database connectivity
- Review logs for LLM errors

#### 2. **Duplicate Recommendations Generated**
**Symptom:** Multiple sets of recommendations for same session

**Solution:** 
- Recommendations use `select_for_update()` to prevent race conditions
- Ensure database supports row-level locking (PostgreSQL recommended)

#### 3. **LLM Responses Timing Out**
**Symptom:** 504 Gateway Timeout

**Solutions:**
- Increase request timeout settings
- Use faster LLM model (e.g., GPT-4-turbo)
- Optimize prompt length
- Check Azure OpenAI quota limits

#### 4. **Questions Seem Repetitive**
**Symptom:** AI asks similar questions multiple times

**Solutions:**
- Review theme diversity enforcement in prompts
- Check that conversation history is being passed correctly
- Verify `current_step` is incrementing properly
- Adjust `DEEPDIVE_QUESTION_GENERATION_PROMPT`

#### 5. **Audio Transcription Fails**
**Symptom:** Error on `/transcribe/` endpoint

**Solutions:**
- Verify Azure Speech API credentials
- Check audio file format (supported: wav, mp3, m4a, ogg)
- Ensure file size is under limit
- Test with sample audio file

#### 6. **PDF Report Not Generating**
**Symptom:** Error on `/report/` endpoint

**Solutions:**
- Ensure recommendations exist for session
- Check PDF generation library installation
- Verify file write permissions
- Review report template formatting

### Performance Optimization

**For High Traffic:**
- Implement Redis caching for user profiles
- Use database connection pooling
- Cache predefined domains in memory
- Consider async task queue for LLM calls (Celery)

**For Faster Responses:**
- Use GPT-4-turbo instead of GPT-4
- Reduce prompt verbosity
- Implement response streaming for long answers
- Pre-generate common responses

### Monitoring and Observability

**Key Metrics to Track:**
- Session creation rate
- Average session completion time
- LLM API latency
- Recommendation generation success rate
- User drop-off points (which questions)

**Logging Best Practices:**
- Log all LLM interactions (sanitized)
- Track session state transitions
- Monitor API error rates
- Record response times for each endpoint

### Error Handling

The module implements comprehensive error handling:
- Graceful LLM failure fallbacks
- Transaction rollback on errors
- User-friendly error messages
- Detailed server-side logging

---

## Appendices

### A. RIASEC Personality Framework

**RIASEC** (Holland Codes) is a career aptitude framework:

- **Realistic (R)**: Practical, hands-on, physical work
- **Investigative (I)**: Analytical, research, problem-solving
- **Artistic (A)**: Creative, expressive, aesthetic
- **Social (S)**: Helping, teaching, interpersonal
- **Enterprising (E)**: Leading, persuading, competitive
- **Conventional (C)**: Organizing, detail-oriented, structured

Currently disabled in the module but can be re-enabled.

### B. LangChain Integration Details

The module uses:
- `AzureChatOpenAI` or `ChatGoogleGenerativeAI` for LLM
- `ChatPromptTemplate` for structured prompts
- `JsonOutputParser` with Pydantic models for structured outputs
- `SystemMessage`, `HumanMessage`, `AIMessage` for conversation history

### C. API Rate Limits

**Azure OpenAI:**
- Tokens per minute (TPM): Varies by deployment
- Requests per minute (RPM): Varies by deployment
- Monitor usage in Azure Portal

**Google Gemini:**
- Free tier: 60 requests per minute
- Paid tier: Higher limits based on plan

### D. Security Considerations

- All endpoints require JWT authentication
- User data is isolated by `user` foreign key
- LLM prompts sanitize PII before logging
- File downloads require valid token
- CORS configured for allowed origins

### E. Future Enhancements

**Planned Features:**
- Re-enable RIASEC assessment phase
- Multi-language support
- Real-time streaming responses
- Integration with career database
- Advanced analytics dashboard
- A/B testing for prompts
- Machine learning-based question selection

---

## Support and Contact

For technical support or questions:
- Review code comments in `langchain_service.py` and `services.py`
- Check Django logs for detailed error traces
- Consult LangChain documentation: https://python.langchain.com/
- Azure OpenAI docs: https://learn.microsoft.com/azure/ai-services/openai/

---

**Last Updated:** February 3, 2026  
**Module Version:** 1.0  
**Django Version:** 4.x  
**Python Version:** 3.10+
