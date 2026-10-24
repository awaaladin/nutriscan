from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "status", "expires_at"]


class PaystackCheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=Subscription.Plan.choices)


class VerifyPurchaseSerializer(serializers.Serializer):
    # The plan is derived server-side from the product Google reports, so the
    # client can't claim a plan it didn't pay for.
    purchase_token = serializers.CharField(max_length=512)
    product_id = serializers.CharField(max_length=128)
