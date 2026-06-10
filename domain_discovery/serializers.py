from rest_framework import serializers
from .models import DomainSession, DomainMessage, DomainRecommendation


class DomainMessageSerializer(serializers.ModelSerializer):
    """Serializer for domain conversation messages"""
    
    class Meta:
        model = DomainMessage
        fields = ['message_id', 'type', 'content', 'question_type', 'choices', 'medium', 'timestamp']
        read_only_fields = ['timestamp']


class DomainSessionSerializer(serializers.ModelSerializer):
    """Serializer for Stream & Subject Selection sessions"""
    messages = DomainMessageSerializer(many=True, read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_trial_locked = serializers.SerializerMethodField()
    
    def get_is_trial_locked(self, obj):
        from apps.accounts.services import check_module_access
        access_info = check_module_access(obj.user, "domain_discovery")
        return access_info["access"] == "trial" and obj.current_step >= access_info["limit"]
    
    
    class Meta:
        model = DomainSession
        fields = [
            'session_id', 'current_step', 'total_steps', 'current_phase',
            # RIASEC fields commented out - may be re-enabled later
            # 'riasec_questions_count', 'riasec_completed', 'riasec_scores',
            'min_deepdive_questions', 'max_deepdive_questions',
            'deepdive_questions_count', 'deepdive_completed',
            'is_active', 'is_completed', 'is_trial_locked', 'notes', 'token_usage', 'metadata', 'created_at', 'updated_at', 'messages'
        ]
        read_only_fields = ['session_id', 'created_at', 'updated_at']
    


class DomainSessionBasicSerializer(serializers.ModelSerializer):
    """Basic serializer for domain sessions without messages"""
    is_completed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = DomainSession
        fields = [
            'session_id', 'current_step', 'total_steps', 'current_phase',
            # RIASEC fields commented out - may be re-enabled later
            # 'riasec_questions_count', 'riasec_completed', 'riasec_scores',
            'min_deepdive_questions', 'max_deepdive_questions',
            'deepdive_questions_count', 'deepdive_completed',
            'is_active', 'is_completed', 'notes', 'token_usage', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['session_id', 'created_at', 'updated_at']


class DomainRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for domain recommendations"""
    
    class Meta:
        model = DomainRecommendation
        fields = [
            'id', 'domain_title', 'category', 'match_percentage',
            'key_interests', 'sub_domains', 'related_subjects',
            'description',
            'why_recommended', 'exploration_activities', 'potential_careers', 
            'rank', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SendMessageRequestSerializer(serializers.Serializer):
    """Serializer for the send message request"""
    content = serializers.CharField(required=True)


class SendMessageResponseSerializer(serializers.Serializer):
    """Serializer for the send message response"""
    session_id = serializers.CharField()
    bot_response = serializers.CharField()
    question_type = serializers.CharField(required=False)  # 'deepdive' or 'general'
    choices = serializers.ListField(child=serializers.CharField(), required=False)  # For multiple choice questions
    current_step = serializers.IntegerField()
    # RIASEC fields commented out - may be re-enabled later
    # riasec_completed = serializers.IntegerField()
    deepdive_completed = serializers.IntegerField()
    is_complete = serializers.BooleanField()
    is_last_question = serializers.BooleanField(required=False, default=False)
    phase = serializers.CharField()
    # NEW: Progress tracking
    progress_percentage = serializers.IntegerField()
    questions_completed = serializers.IntegerField()
    is_trial_locked = serializers.BooleanField(required=False, default=False)
    token_usage = serializers.DictField(required=False)


class GenerateRecommendationsRequestSerializer(serializers.Serializer):
    """Serializer for generate recommendations request"""
    session_id = serializers.CharField(max_length=100, required=True)


class TranscribeAudioRequestSerializer(serializers.Serializer):
    """Serializer for audio transcription request"""
    audio = serializers.FileField(required=True)


class TranscribeAudioResponseSerializer(serializers.Serializer):
    """Serializer for audio transcription response"""
    text = serializers.CharField()


class GenerateSpeechRequestSerializer(serializers.Serializer):
    """Serializer for TTS request"""
    text = serializers.CharField(required=True, max_length=5000)
    voice = serializers.ChoiceField(
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        default='nova'
    )

class RIASECScoresSerializer(serializers.Serializer):
    """Serializer for RIASEC scores"""
    Realistic = serializers.IntegerField(min_value=0, max_value=100)
    Investigative = serializers.IntegerField(min_value=0, max_value=100)
    Artistic = serializers.IntegerField(min_value=0, max_value=100)
    Social = serializers.IntegerField(min_value=0, max_value=100)
    Enterprising = serializers.IntegerField(min_value=0, max_value=100)
    Conventional = serializers.IntegerField(min_value=0, max_value=100)


class ResultsSummarySerializer(serializers.Serializer):
    """Serializer for results summary after conversation"""
    session_id = serializers.CharField()
    student_name = serializers.CharField()
    current_step = serializers.IntegerField()
    total_steps = serializers.IntegerField()
    interests_identified = serializers.ListField(child=serializers.CharField())
    strengths_identified = serializers.ListField(child=serializers.CharField())
    # RIASEC fields commented out - may be re-enabled later
    # riasec_scores = RIASECScoresSerializer()
    # top_dimensions = serializers.ListField(child=serializers.CharField())
    primary_domains = DomainRecommendationSerializer(many=True)
    secondary_domains = DomainRecommendationSerializer(many=True)
    completion_percentage = serializers.IntegerField()


class TranscriptMessageSerializer(serializers.Serializer):
    """Serializer for transcript message"""
    question_number = serializers.IntegerField()
    phase = serializers.CharField()
    bot_question = serializers.CharField()
    student_response = serializers.CharField()
    timestamp = serializers.DateTimeField()


class TranscriptSerializer(serializers.Serializer):
    """Serializer for conversation transcript"""
    session_id = serializers.CharField()
    student_name = serializers.CharField()
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField()
    total_questions = serializers.IntegerField()
    messages = TranscriptMessageSerializer(many=True)
    concluding_message = serializers.CharField(required=False, allow_null=True)
    download_url = serializers.CharField(required=False)