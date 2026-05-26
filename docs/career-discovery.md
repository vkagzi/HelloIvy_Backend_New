# Career & Degree Selection Module Documentation

> **Note:** For complete technical documentation, see [career_discovery/README.md](../career_discovery/README.md)

## Quick Overview

Career & Degree Selection is HelloIvy's AI-powered career exploration tool that helps students identify specific career paths aligned with their interests and strengths. **It builds directly upon Stream & Subject Selection** by using those insights to recommend concrete job titles and career paths.

## Key Relationship: Stream & Subject Selection → Career & Degree Selection 

### Prerequisites
- User must complete **Stream & Subject Selection** first
- Stream & Subject Selection provides the top 3 domain recommendations
- Career & Degree Selection uses this context to provide specific career suggestions

### Workflow Integration

```
Step 1: Stream & Subject Selection (25 questions)
   ↓
   Output: Top 3 Domains (e.g., "Engineering", "Design", "Entrepreneurship")
   ↓
Step 2: Career & Degree Selection (20 questions)
   ↓
   Output: Up to 8 Specific Careers (e.g., "UX Designer", "Software Engineer")
```

### Initial Question Strategy

When Career & Degree Selection starts, the AI:
1. **References Stream & Subject Selection results**: "Hey [Name]! In our last session, we discovered that [Domain 1], [Domain 2], and [Domain 3] are your top-suited domains."
2. **Acknowledges profile highlights**: Mentions achievements, school, or activities from their profile
3. **Sets career exploration context**: Explains that this session will explore specific careers
4. **Asks engaging first question**: Related to their domain interests

**Example Opening:**
> "Hey Sarah! In our last session, we discovered that Engineering & Applied Technology, Design & Aesthetics, and Entrepreneurship are your top-suited domains. I noticed you're captain of your robotics team—that's awesome! I'm excited to help you explore specific careers in these areas. What excites you most about building and creating things?"

## Two-Phase Conversation

### Phase 1: Profile Builder (Questions 1-10)
- Explores interests, strengths, and preferences
- Validates and deepens Stream & Subject Selection insights
- Gathers nuanced career-relevant information

### Phase 2: Career Explorer (Questions 11-20)
- Dives into specific career paths
- Explores day-to-day job activities
- Assesses alignment with student's goals

## Output: Career Recommendations

Each career recommendation includes:
- **Career Title**: Specific job (e.g., "Product Manager")
- **Salary Range**: Expected earnings (e.g., "$90,000 - $150,000")
- **Match Percentage**: 0-100% fit score
- **Required Skills**: Key competencies needed
- **Next Steps**: Actionable steps to pursue this career
- **Description**: Day-to-day responsibilities
- **Why Recommended**: Personalized explanation
- **Alignment Points**: Specific connections to student's responses and domain results

## API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/career-discovery/` | POST | Create new career session (requires domain session) |
| `/api/career-discovery/<session_id>/messages/` | POST | Send user response, get next question |
| `/api/career-discovery/<session_id>/recommendations/generate/` | POST | Generate career recommendations |
| `/api/career-discovery/<session_id>/recommendations/` | GET | Retrieve recommendations |

## Integration with Stream & Subject Selection

### Technical Implementation

```python
# CareerSession model has foreign key to DomainSession
class CareerSession(models.Model):
    domain_session = models.ForeignKey(
        'domain_discovery.DomainSession',
        on_delete=models.SET_NULL,
        null=True
    )
```

### Domain Context Passed to AI

```python
domain_context = {
    'recommendations': [
        {
            'title': 'Engineering & Applied Technology',
            'match_percentage': 92,
            'explanation': 'Strong technical interests...',
            'key_interests': ['Problem-solving', 'Building', 'Technology']
        }
        # Top 3 domains
    ],
    'messages': [
        # Full Stream & Subject Selection Q&A
    ]
}
```

## Key Differences from Stream & Subject Selection

| Aspect | Stream & Subject Selection | Career & Degree Selection |
|--------|------------------|------------------|
| **Granularity** | Broad areas (13 domains) | Specific jobs (thousands of careers) |
| **Questions** | 25 deep dive questions | 20 questions (2 phases) |
| **Output** | 3 domain recommendations | Up to 8 career recommendations |
| **Salary Info** | ❌ No | ✅ Yes |
| **Next Steps** | ❌ No | ✅ Yes (actionable guidance) |
| **Prerequisites** | None | Requires Stream & Subject Selection |
| **Context Used** | User profile only | User profile + Domain results |

## Development Quick Start

1. **Ensure Stream & Subject Selection is set up:**
   ```bash
   python manage.py migrate domain_discovery
   ```

2. **Set up Career & Degree Selection :**
   ```bash
   python manage.py migrate career_discovery
   ```

3. **Test the flow:**
   ```bash
   # Create and complete domain session
   # Then create career session (will auto-link to domain session)
   ```

## For Complete Documentation

- **Technical Details**: [career_discovery/README.md](../career_discovery/README.md)
- **Stream & Subject Selection Docs**: [domain-discovery.md](./domain-discovery.md)
- **API Specification**: Auto-generated at `/api/schema/swagger-ui/`

## Common Issues

### "Stream & Subject Selection required" Error
**Solution:** User must complete at least one Stream & Subject Selection session before starting Career & Degree Selection .

### Domain References Not Appearing
**Solution:** Ensure Domain Recommendations were generated (`/recommendations/generate/`) before creating Career session.

### Recommendations Don't Align with Domains
**Solution:** Check that `domain_session` foreign key is properly set and domain context is being passed to LLM.

---

**See Also:**
- [Stream & Subject Selection Documentation](./domain-discovery.md)
- [Career & Degree Selection Technical Docs](../career_discovery/README.md)
- [Prompting Guidelines](./prompting-guidegpt-5.2.md)
