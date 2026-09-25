from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "status", "expires_at"]


class VerifyPurchaseSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=Subscription.Plan.choices)
    purchase_token = serializers.CharField()
    product_id = serializers.CharField()
