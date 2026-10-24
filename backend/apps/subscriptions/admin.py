from django.contrib import admin

from .models import PaystackPayment, Subscription

admin.site.register(Subscription)


@admin.register(PaystackPayment)
class PaystackPaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "plan", "amount_kobo", "status", "paid_at")
    list_filter = ("status", "plan")
    search_fields = ("reference", "user__username", "user__email", "paystack_transaction_id")
