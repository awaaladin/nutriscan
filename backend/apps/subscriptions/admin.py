from django.contrib import admin

from .models import AiUsage, PaystackPayment, Subscription

admin.site.register(Subscription)


@admin.register(PaystackPayment)
class PaystackPaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "plan", "amount_kobo", "status", "paid_at")
    list_filter = ("status", "plan")
    search_fields = ("reference", "user__username", "user__email", "paystack_transaction_id")


@admin.register(AiUsage)
class AiUsageAdmin(admin.ModelAdmin):
    """Costs only: AiUsage holds no message text."""

    list_display = ("created_at", "user", "action", "tier", "credits", "bonus_credits", "model", "cost_usd")
    list_filter = ("action", "tier")
    date_hierarchy = "created_at"
