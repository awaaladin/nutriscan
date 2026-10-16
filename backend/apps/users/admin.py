from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class NutriScanUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ("is_pro", "is_verified_reviewer")
    list_filter = UserAdmin.list_filter + ("is_verified_reviewer",)
    fieldsets = UserAdmin.fieldsets + (
        (
            "NutriScan",
            {"fields": ("primary_goal", "is_diabetic", "has_hypertension", "region", "is_pro", "is_verified_reviewer")},
        ),
    )
