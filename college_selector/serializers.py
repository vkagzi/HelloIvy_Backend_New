from rest_framework import serializers
from .models import CollegeSelectorSession, CollegeSelectorMessage, CollegeRecommendation


class CollegeSelectorMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollegeSelectorMessage
        fields = ['message_id', 'type', 'content', 'medium', 'timestamp']
        read_only_fields = ['timestamp']


class CollegeSelectorSessionSerializer(serializers.ModelSerializer):
    messages = CollegeSelectorMessageSerializer(many=True, read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = CollegeSelectorSession
        fields = [
            'session_id', 'current_step', 'total_steps', 'current_phase',
            'preferences', 'preferences_completed',
            'is_active', 'is_completed', 'notes', 'token_usage', 'metadata',
            'created_at', 'updated_at', 'messages',
        ]
        read_only_fields = ['session_id', 'created_at', 'updated_at']


class CollegeSelectorSessionBasicSerializer(serializers.ModelSerializer):
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = CollegeSelectorSession
        fields = [
            'session_id', 'current_step', 'total_steps', 'current_phase',
            'preferences_completed',
            'is_active', 'is_completed', 'token_usage', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['session_id', 'created_at', 'updated_at']


class CollegeRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollegeRecommendation
        fields = [
            'id', 'university_name', 'website_url', 'location', 'country',
            'deadlines', 'degree_and_major', 'tuition_fees', 'cost_of_living',
            'scholarships', 'academic_requirements', 'additional_requirements',
            'university_type', 'global_ranking', 'acceptance_rate',
            'application_fee', 'tests_required', 'post_study_work_visa',
            'employment_rate', 'language', 'campus_type', 'intl_student_support',
            'fit_category', 'fit_reasoning', 'suggested_deadline',
            'match_percentage', 'description', 'rank', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SavePreferencesRequestSerializer(serializers.Serializer):
    degree_level = serializers.CharField(required=True)
    degree_type = serializers.CharField(required=True)
    primary_major = serializers.CharField(required=True)
    secondary_major = serializers.CharField(required=False, default='', allow_blank=True)
    countries = serializers.ListField(child=serializers.CharField(), required=True, min_length=1, max_length=5)
    campus_setting = serializers.CharField(required=False, default='no_preference')
    campus_importance = serializers.CharField(required=False, default='nice_to_have')
    climate_preference = serializers.CharField(required=False, default='no_preference')
    college_type = serializers.CharField(required=False, default='no_preference')
    college_type_reasons = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    research_importance = serializers.CharField(required=False, default='unsure')
    research_exposure = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    cultural_fit = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    fit_importance = serializers.CharField(required=False, default='important')
    class_size = serializers.CharField(required=False, default='no_preference')
    teaching_style = serializers.CharField(required=False, default='', allow_blank=True)
    brand_preference = serializers.CharField(required=False, default='no_preference')
    financial_aid_preference = serializers.CharField(required=False, default='no_preference')
    financial_aid_required = serializers.BooleanField(required=False, default=False)
    prestige_important = serializers.BooleanField(required=False, default=False)
    additional_notes = serializers.CharField(required=False, default='', allow_blank=True)


class SendMessageRequestSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)


class SendMessageResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    bot_response = serializers.CharField()
    current_step = serializers.IntegerField()
    is_complete = serializers.BooleanField()
    progress_percentage = serializers.IntegerField()
    questions_completed = serializers.IntegerField()
    token_usage = serializers.DictField(required=False)


class TranscribeAudioRequestSerializer(serializers.Serializer):
    audio = serializers.FileField(required=True)


class TranscribeAudioResponseSerializer(serializers.Serializer):
    text = serializers.CharField()


class GenerateSpeechRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True, max_length=5000)
    voice = serializers.ChoiceField(
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        default='nova'
    )


class TranscriptMessageSerializer(serializers.Serializer):
    question_number = serializers.IntegerField()
    bot_question = serializers.CharField()
    student_response = serializers.CharField()
    timestamp = serializers.DateTimeField()


class TranscriptSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    student_name = serializers.CharField()
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField()
    total_questions = serializers.IntegerField()
    messages = TranscriptMessageSerializer(many=True)
