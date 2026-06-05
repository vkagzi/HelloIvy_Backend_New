from django.db import models
from apps.accounts.models import User
from utils.message_constants import MessageType


class CareerSession(models.Model):
    """Model for Career & Degree Selection conversation sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='career_sessions')
    domain_session = models.ForeignKey(
        'domain_discovery.DomainSession',
        on_delete=models.SET_NULL,
        related_name='career_sessions',
        null=True,
        blank=True,
        help_text="Reference to the Stream & Subject Selection session that preceded this Career & Degree Selection session"
    )
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    current_step = models.IntegerField(default=0)
    total_steps = models.IntegerField(default=20)  # 10 Profile Builder + 10 Career Explorer
    current_phase = models.CharField(
        max_length=20,
        choices=[('profile', 'Profile Builder'), ('explorer', 'Career Explorer')],
        default='profile'
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="AI-generated observations about the student derived from profile and Stream & Subject Selection context to guide career exploration"
    )
    token_usage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Accumulated LLM token usage per category and totals for this session"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Session metadata including pause/resume events"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Career Session'
        verbose_name_plural = 'Career Sessions'

    def __str__(self):
        return f"{self.user.email} - Session {self.session_id}"

    @property
    def is_completed(self):
        """Derived field: True if current_step >= total_steps"""
        return self.current_step >= self.total_steps

    def get_current_phase(self):
        """Returns 'profile' for first 10 questions, 'explorer' for next 10"""
        if self.current_step < 10:
            return 'profile'
        return 'explorer'


class CareerMessage(models.Model):
    """Model for Career & Degree Selection conversation messages"""
    MEDIUM_CHOICES = [
        ('text', 'Text'),
        ('voice', 'Voice'),
    ]

    session = models.ForeignKey(CareerSession, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=MessageType.CHOICES)
    content = models.TextField()
    step_number = models.IntegerField(default=0)
    phase = models.CharField(max_length=20, default='profile')
    medium = models.CharField(max_length=10, choices=MEDIUM_CHOICES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Career Message'
        verbose_name_plural = 'Career Messages'

    def __str__(self):
        return f"{self.session.session_id} - {self.type}: {self.content[:50]}"


class CareerRecommendation(models.Model):
    """Model for storing career recommendations"""
    session = models.ForeignKey(CareerSession, on_delete=models.CASCADE, related_name='recommendations')
    career_title = models.CharField(max_length=200)
    salary_range = models.CharField(max_length=100, blank=True)
    match_percentage = models.IntegerField(default=0)
    required_skills = models.JSONField(default=list)
    next_steps = models.JSONField(default=list)
    description = models.TextField(blank=True)
    why_recommended = models.TextField(blank=True)
    alignment_points = models.JSONField(default=list)
    related_subjects = models.JSONField(default=list)
    degrees = models.JSONField(default=list, help_text="Rich degree objects with fit scores, pathways, and decision filters")
    day_in_life = models.TextField(blank=True)
    pros_and_cons = models.JSONField(default=dict)
    work_life_balance = models.TextField(blank=True)
    feasibility = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feasibility metric: {level: High|Medium|Low, reason: str}"
    )
    skill_gaps = models.JSONField(
        default=list,
        blank=True,
        help_text="Top 5 personalised skill gaps for this career given the student's profile"
    )
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rank', '-match_percentage']
        verbose_name = 'Career Recommendation'
        verbose_name_plural = 'Career Recommendations'

    def __str__(self):
        return f"{self.career_title} - {self.match_percentage}% match"
