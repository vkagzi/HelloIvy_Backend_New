from django.contrib import admin
from .models import DomainSession, DomainMessage, DomainRecommendation


@admin.register(DomainSession)
class DomainSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'current_step', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'created_at', 'updated_at']


@admin.register(DomainMessage)
class DomainMessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'session', 'type', 'question_type', 'timestamp']
    list_filter = ['type', 'question_type', 'timestamp']
    search_fields = ['session__session_id', 'content']
    readonly_fields = ['message_id', 'timestamp']


@admin.register(DomainRecommendation)
class DomainRecommendationAdmin(admin.ModelAdmin):
    list_display = ['domain_title', 'session', 'match_percentage', 'rank', 'created_at']
    list_filter = ['created_at']
    search_fields = ['domain_title', 'session__session_id']
    readonly_fields = ['created_at']
