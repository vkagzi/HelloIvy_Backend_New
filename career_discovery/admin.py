from django.contrib import admin
from .models import CareerSession, CareerMessage, CareerRecommendation


@admin.register(CareerSession)
class CareerSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'current_step', 'total_steps', 'current_phase', 'is_active', 'is_completed', 'created_at']
    list_filter = ['is_active', 'current_phase', 'created_at']
    search_fields = ['session_id', 'user__email']
    ordering = ['-created_at']


@admin.register(CareerMessage)
class CareerMessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'session', 'type', 'step_number', 'phase', 'timestamp']
    list_filter = ['type', 'phase', 'timestamp']
    search_fields = ['message_id', 'content', 'session__session_id']
    ordering = ['-timestamp']


@admin.register(CareerRecommendation)
class CareerRecommendationAdmin(admin.ModelAdmin):
    list_display = ['career_title', 'session', 'match_percentage', 'rank', 'created_at']
    list_filter = ['match_percentage', 'created_at']
    search_fields = ['career_title', 'session__session_id']
    ordering = ['-created_at', 'rank']
