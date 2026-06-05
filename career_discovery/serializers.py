from rest_framework import serializers
from .models import CareerSession, CareerMessage, CareerRecommendation


class CareerMessageSerializer(serializers.ModelSerializer):
    """Serializer for career conversation messages"""
    
    class Meta:
        model = CareerMessage
        fields = ['message_id', 'type', 'content', 'step_number', 'phase', 'medium', 'timestamp']
        read_only_fields = ['timestamp']


class CareerSessionSerializer(serializers.ModelSerializer):
    """Serializer for Career & Degree Selection  sessions"""
    messages = CareerMessageSerializer(many=True, read_only=True)
    domain_session_id = serializers.CharField(source='domain_session.session_id', read_only=True, allow_null=True)
    is_completed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CareerSession
        fields = [
            'session_id', 'domain_session_id', 'current_step', 'total_steps', 'current_phase',
            'is_active', 'is_completed', 'notes', 'token_usage', 'metadata', 'created_at', 'updated_at', 'messages'
        ]
        read_only_fields = ['session_id', 'domain_session_id', 'created_at', 'updated_at']


class CareerSessionBasicSerializer(serializers.ModelSerializer):
    """Basic serializer for career sessions without messages"""
    domain_session_id = serializers.CharField(source='domain_session.session_id', read_only=True, allow_null=True)
    is_completed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CareerSession
        fields = [
            'session_id', 'domain_session_id', 'current_step', 'total_steps', 'current_phase',
            'is_active', 'is_completed', 'notes', 'token_usage', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['session_id', 'domain_session_id', 'created_at', 'updated_at']


class CareerRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for career recommendations"""
    
    class Meta:
        model = CareerRecommendation
        fields = [
            'id', 'career_title', 'match_percentage',
            'required_skills', 'next_steps', 'description',
            'why_recommended', 'alignment_points', 'related_subjects',
            'degrees',
            'day_in_life', 'pros_and_cons', 'work_life_balance',
            'feasibility', 'skill_gaps',
            'rank', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SendMessageRequestSerializer(serializers.Serializer):
    """Serializer for the send message request"""
    content = serializers.CharField(required=True)


class SendMessageResponseSerializer(serializers.Serializer):
    """Serializer for the send message response"""
    session_id = serializers.CharField()
    user_message = serializers.CharField()
    bot_response = serializers.CharField()
    current_step = serializers.IntegerField()
    total_steps = serializers.IntegerField()
    is_complete = serializers.BooleanField()
    phase = serializers.CharField()
    token_usage = serializers.DictField(required=False)


class GenerateRecommendationsRequestSerializer(serializers.Serializer):
    """Serializer for generate recommendations request"""
    session_id = serializers.CharField(max_length=100, required=True)
