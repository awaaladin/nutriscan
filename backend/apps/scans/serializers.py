from rest_framework import serializers

from apps.products.serializers import ProductSerializer

from .models import Scan


class ScanSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Scan
        fields = ["id", "product", "score", "label", "diabetic_risk", "flags", "scanned_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.label == "Incomplete":
            data["score"] = None  # stored as 0; there is no honest number to show
        return data
