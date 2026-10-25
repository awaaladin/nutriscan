from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    # Both must be true: agreement to the Terms and Privacy Policy, and the explicit consent the
    # NDPA requires before we process health information (the app is built around it).
    accept_terms = serializers.BooleanField(write_only=True)
    health_consent = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "primary_goal", "region", "accept_terms", "health_consent"]

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the Terms and Privacy Policy to create an account.")
        return value

    def validate_health_consent(self, value):
        if not value:
            raise serializers.ValidationError("NutriScan needs your consent to use your health information.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("accept_terms")
        validated_data.pop("health_consent")
        now = timezone.now()
        user = User(**validated_data, terms_accepted_at=now, health_consent_at=now)
        user.set_password(password)
        user.save()
        return user


class PreferencesSerializer(serializers.ModelSerializer):
    # Accounts created before consent was recorded give it here (the app asks once).
    accept_terms = serializers.BooleanField(write_only=True, required=False)
    health_consent = serializers.BooleanField(write_only=True, required=False)
    tier = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "primary_goal", "is_diabetic", "has_hypertension", "region", "is_pro",
            "tier", "bonus_credits", "height_cm", "target_weight_kg", "terms_accepted_at", "health_consent_at",
            "accept_terms", "health_consent",
        ]
        read_only_fields = ["id", "username", "email", "is_pro", "bonus_credits", "terms_accepted_at", "health_consent_at"]
        extra_kwargs = {"height_cm": {"min_value": 50, "max_value": 250}}

    def get_tier(self, user):
        from apps.subscriptions.credits import tier_of

        return tier_of(user)

    def update(self, instance, validated_data):
        now = timezone.now()
        if validated_data.pop("accept_terms", False) and not instance.terms_accepted_at:
            instance.terms_accepted_at = now
        if validated_data.pop("health_consent", False) and not instance.health_consent_at:
            instance.health_consent_at = now
        return super().update(instance, validated_data)


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField()
