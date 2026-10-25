from rest_framework import serializers

from .models import Subscription, Tier


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "status", "expires_at"]


class PaystackCheckoutSerializer(serializers.Serializer):
    # A plan period (tier + monthly/yearly), or kind="credits" for a top-up.
    kind = serializers.ChoiceField(choices=["subscription", "credits"], default="subscription")
    tier = serializers.ChoiceField(choices=Tier.choices, default=Tier.PRO)
    plan = serializers.ChoiceField(choices=Subscription.Plan.choices, default=Subscription.Plan.MONTHLY)
    # Paystack needs an email for the receipt; accounts registered without one supply it here.
    email = serializers.EmailField(required=False)


class VerifyPurchaseSerializer(serializers.Serializer):
    # The plan is derived server-side from the product Google reports, so the
    # client can't claim a plan it didn't pay for.
    purchase_token = serializers.CharField(max_length=512)
    product_id = serializers.CharField(max_length=128)
