from rest_framework import serializers

from .models import Product, ProductSubmission


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class ProductSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSubmission
        fields = [
            "id", "barcode", "name", "brand", "nutrition_payload",
            "ingredients_text", "photo_url", "status", "created_at",
        ]
        read_only_fields = ["status", "created_at"]


class ScanRequestSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=32)


class AnalyzeRequestSerializer(serializers.Serializer):
    calories_kcal = serializers.FloatField(required=False, allow_null=True)
    sugar_g = serializers.FloatField(required=False, allow_null=True)
    saturated_fat_g = serializers.FloatField(required=False, allow_null=True)
    sodium_mg = serializers.FloatField(required=False, allow_null=True)
    carbohydrates_g = serializers.FloatField(required=False, allow_null=True)
    fiber_g = serializers.FloatField(required=False, allow_null=True)
    protein_g = serializers.FloatField(required=False, allow_null=True)
    ingredients_text = serializers.CharField(required=False, allow_blank=True)
