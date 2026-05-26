from django.db import models
from apps.accounts.models import User
from utils.message_constants import MessageType


class CollegeSelectorSession(models.Model):
    """Model for College Selector conversation sessions"""
    MIN_CONVERSATION_QUESTIONS = 2
    MAX_CONVERSATION_QUESTIONS = 20

    PHASE_CHOICES = [
        ('preferences', 'Preferences'),
        ('conversation', 'Conversation'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='college_selector_sessions')
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    current_step = models.IntegerField(default=0)
    total_steps = models.IntegerField(default=MAX_CONVERSATION_QUESTIONS)
    current_phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='preferences')
    preferences = models.JSONField(default=dict, blank=True, help_text="Static questionnaire answers")
    preferences_completed = models.BooleanField(default=False)
    notes = models.TextField(
        blank=True,
        default='',
        help_text="AI-generated observations about the student's preferences to guide conversation"
    )
    token_usage = models.JSONField(default=dict, blank=True, help_text="Accumulated LLM token usage")
    metadata = models.JSONField(default=dict, blank=True, help_text="Session metadata")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'College Selector Session'
        verbose_name_plural = 'College Selector Sessions'

    def __str__(self):
        return f"{self.user.email} - College Session {self.session_id}"

    @property
    def is_completed(self):
        return self.current_phase == 'completed' or self.current_step >= self.total_steps

    def conclude_conversation(self):
        self.total_steps = self.current_step
        self.current_phase = 'completed'
        self.save(update_fields=['total_steps', 'current_phase'])


class CollegeSelectorMessage(models.Model):
    """Model for College Selector conversation messages"""
    MEDIUM_CHOICES = [
        ('text', 'Text'),
        ('voice', 'Voice'),
    ]

    session = models.ForeignKey(CollegeSelectorSession, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=MessageType.CHOICES)
    content = models.TextField()
    medium = models.CharField(max_length=10, choices=MEDIUM_CHOICES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'College Selector Message'
        verbose_name_plural = 'College Selector Messages'
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['session', 'type']),
        ]

    def __str__(self):
        return f"{self.session.session_id} - {self.type}: {self.content[:50]}"


class CollegeRecommendation(models.Model):
    """Model for storing college recommendations — matches PRD comparison table"""
    FIT_CHOICES = [
        ('reach', 'Reach'),
        ('match', 'Match'),
        ('safe', 'Safe'),
    ]

    session = models.ForeignKey(CollegeSelectorSession, on_delete=models.CASCADE, related_name='recommendations')
    university_name = models.CharField(max_length=300)
    website_url = models.URLField(max_length=500, blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    deadlines = models.JSONField(default=dict, blank=True, help_text="EA/ED/RD/Rolling deadlines")
    degree_and_major = models.CharField(max_length=300, blank=True, default='')
    tuition_fees = models.CharField(max_length=200, blank=True, default='')
    cost_of_living = models.CharField(max_length=200, blank=True, default='')
    scholarships = models.JSONField(default=list, blank=True, help_text="Types & availability")
    academic_requirements = models.JSONField(default=dict, blank=True, help_text="GPA, SAT, ACT etc.")
    additional_requirements = models.JSONField(default=list, blank=True, help_text="SOPs, LORs, Portfolio")
    university_type = models.CharField(max_length=50, blank=True, default='')
    global_ranking = models.JSONField(default=dict, blank=True, help_text="QS/THE/USN rankings")
    acceptance_rate = models.CharField(max_length=50, blank=True, default='')
    application_fee = models.CharField(max_length=100, blank=True, default='')
    tests_required = models.JSONField(default=list, blank=True)
    post_study_work_visa = models.CharField(max_length=300, blank=True, default='')
    employment_rate = models.CharField(max_length=100, blank=True, default='')
    language = models.CharField(max_length=100, blank=True, default='English')
    campus_type = models.CharField(max_length=50, blank=True, default='')
    intl_student_support = models.TextField(blank=True, default='')
    fit_category = models.CharField(max_length=10, choices=FIT_CHOICES, default='match')
    fit_reasoning = models.TextField(
        blank=True,
        default='',
        help_text="Explanation of why this college is categorized as reach/match/safe for the student"
    )
    suggested_deadline = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Recommended application round and date for the student"
    )
    match_percentage = models.IntegerField(default=0)
    description = models.TextField(blank=True, default='')
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank', '-match_percentage']
        verbose_name = 'College Recommendation'
        verbose_name_plural = 'College Recommendations'

    def __str__(self):
        return f"{self.university_name} - {self.match_percentage}% ({self.fit_category})"
