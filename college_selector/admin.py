from django.contrib import admin
from .models import CollegeSelectorSession, CollegeSelectorMessage, CollegeRecommendation


@admin.register(CollegeSelectorSession)
class CollegeSelectorSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'current_step', 'current_phase', 'is_active', 'is_completed', 'created_at']
    list_filter = ['is_active', 'current_phase', 'created_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'created_at', 'updated_at']


@admin.register(CollegeSelectorMessage)
class CollegeSelectorMessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'session', 'type', 'medium', 'timestamp']
    list_filter = ['type', 'medium', 'timestamp']
    search_fields = ['session__session_id', 'content']
    readonly_fields = ['message_id', 'timestamp']


@admin.register(CollegeRecommendation)
class CollegeRecommendationAdmin(admin.ModelAdmin):
    list_display = ['university_name', 'session', 'match_percentage', 'fit_category', 'rank', 'created_at']
    list_filter = ['fit_category', 'country', 'created_at']
    search_fields = ['university_name', 'session__session_id']
    readonly_fields = ['created_at']
