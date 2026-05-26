from django.db import models
from django.conf import settings
from django.db.models import Q, Count
from apps.accounts.models import User
from utils.message_constants import MessageType


class DomainSession(models.Model):
    """Model for Stream & Subject Selection conversation sessions"""
    RIASEC_QUESTIONS_COUNT = 0  # Number of RIASEC questions (class constant)
    MIN_DEEPDIVE_QUESTIONS = 15  # Minimum number of deep dive questions
    MAX_DEEPDIVE_QUESTIONS = 30  # Maximum number of deep dive questions
    DEEPDIVE_QUESTIONS_COUNT = MAX_DEEPDIVE_QUESTIONS  # For backward compat: use MAX as upper bound
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='domain_sessions')
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    current_step = models.IntegerField(default=0)
    total_steps = models.IntegerField(default=MAX_DEEPDIVE_QUESTIONS)  # Max questions for this session (stored to preserve count if constants change)
    riasec_scores = models.JSONField(default=dict, blank=True)  # RIASEC profile scores {Realistic, Investigative, Artistic, Social, Enterprising, Conventional}
    notes = models.TextField(
        blank=True,
        default='',
        help_text="AI-generated observations and insights about the student's profile to guide the conversation"
    )
    token_usage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Accumulated LLM token usage per category and totals for this session"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Session metadata updated by background conclusion check: should_conclude, pending_topics, etc."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Domain Session'
        verbose_name_plural = 'Domain Sessions'

    def __str__(self):
        return f"{self.user.email} - Domain Session {self.session_id}"

    @property
    def is_completed(self):
        """Derived field: True if conversation has been concluded (step >= total_steps or LLM decided to stop)"""
        return self.current_step >= self.total_steps

    def save(self, *args, **kwargs):
        """Set total_steps on creation based on current constants (uses MAX as upper bound)"""
        if not self.pk:
            self.total_steps = self.RIASEC_QUESTIONS_COUNT + self.MAX_DEEPDIVE_QUESTIONS
        super().save(*args, **kwargs)
    
    def conclude_conversation(self):
        """Mark the conversation as concluded by setting total_steps to current_step.
        Called when the LLM decides it has gathered enough information."""
        self.total_steps = self.current_step
        self.save(update_fields=['total_steps'])
    
    @property
    def riasec_questions_count(self):
        """Number of RIASEC questions"""
        return self.RIASEC_QUESTIONS_COUNT
    
    @property
    def min_deepdive_questions(self):
        """Minimum number of deep dive questions"""
        return self.MIN_DEEPDIVE_QUESTIONS
    
    @property
    def max_deepdive_questions(self):
        """Maximum number of deep dive questions"""
        return self.MAX_DEEPDIVE_QUESTIONS
    
    @property
    def deepdive_questions_count(self):
        """Number of deep dive questions (total_steps for backward compat)"""
        return self.total_steps
    
    @property
    def current_phase(self):
        """Current phase based on completed questions"""
        return self.get_current_phase()
    
    @property
    def riasec_completed(self):
        """Count of completed RIASEC questions
        OPTIMIZED: Simple COUNT query with indexes
        """
        return self.messages.filter(type=MessageType.BOT, question_type='riasec').count()
    
    @property
    def deepdive_completed(self):
        """Count of completed deep dive questions (user answers, not bot prompts).
        Counting USER messages avoids the off-by-one from the unanswered bot question,
        consistent with career_discovery which uses current_step (incremented per user answer).
        """
        return self.messages.filter(type=MessageType.USER).count()
    
    def get_current_phase(self):
        """Returns 'riasec' for RIASEC questions, 'deepdive' for deep dive questions"""
        if self.riasec_completed < self.RIASEC_QUESTIONS_COUNT:
            return 'riasec'
        return 'deepdive'


class DomainMessage(models.Model):
    """Model for Stream & Subject Selection conversation messages"""
    QUESTION_TYPES = [
        ('riasec', 'RIASEC Question'),
        ('deepdive', 'Deep Dive Question'),
        ('general', 'General Message'),
    ]

    MEDIUM_CHOICES = [
        ('text', 'Text'),
        ('voice', 'Voice'),
    ]

    session = models.ForeignKey(DomainSession, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=MessageType.CHOICES)
    content = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='general')
    choices = models.JSONField(default=list, blank=True)  # For RIASEC questions: ["Choice A", "Choice B"]
    medium = models.CharField(max_length=10, choices=MEDIUM_CHOICES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Domain Message'
        verbose_name_plural = 'Domain Messages'
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['session', 'type']),
        ]

    def __str__(self):
        return f"{self.session.session_id} - {self.type}: {self.content[:50]}"


class DomainRecommendation(models.Model):
    """Model for storing domain recommendations"""
    session = models.ForeignKey(DomainSession, on_delete=models.CASCADE, related_name='recommendations')
    domain_title = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)  # e.g., STEM, Arts, Business
    match_percentage = models.IntegerField(default=0)
    key_interests = models.JSONField(default=list)  # Related interests identified
    sub_domains = models.JSONField(default=list)  # Specific sub-areas
    related_subjects = models.JSONField(default=list)  # Rich subject objects with relevance, importance, and combination pathways
    description = models.TextField(blank=True)
    why_recommended = models.TextField(blank=True)
    exploration_activities = models.JSONField(default=list)  # Activities to explore this domain
    potential_careers = models.JSONField(default=list)  # Preview of career paths in this domain
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank', '-match_percentage']
        verbose_name = 'Domain Recommendation'
        verbose_name_plural = 'Domain Recommendations'

    def __str__(self):
        return f"{self.domain_title} - {self.match_percentage}% match"
    


class ModuleReview(models.Model):

    MODULE_CHOICES = [("stream", "Stream Selection"),("career", "Career Selection"),]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.CharField(max_length=20,choices=MODULE_CHOICES)
    rating = models.IntegerField()
    comment = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.module} ({self.rating})"
