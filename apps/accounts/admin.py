from django.contrib import admin
from .models import User, UserPayment, SchoolPayment, UserModuleSubscription, SchoolModuleSubscription, CustomModule

@admin.register(CustomModule)
class CustomModuleAdmin(admin.ModelAdmin):
    list_display = ("value", "label", "icon", "color", "created_at")
    search_fields = ("value", "label")

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "created_at")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("role", "is_active")

@admin.register(UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "currency", "status", "gateway_transaction_id", "created_at")
    search_fields = ("gateway_transaction_id", "user__email")
    list_filter = ("status", "currency")

@admin.register(SchoolPayment)
class SchoolPaymentAdmin(admin.ModelAdmin):
    list_display = ("school_id", "amount", "status", "gateway_transaction_id", "created_at")
    search_fields = ("gateway_transaction_id", "school_id")
    list_filter = ("status",)

@admin.register(UserModuleSubscription)
class UserModuleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "module_name", "is_active", "expiry_date")
    search_fields = ("user__email", "module_name")

@admin.register(SchoolModuleSubscription)
class SchoolModuleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("school_id", "module_name", "is_active")
    search_fields = ("school_id", "module_name")
