from rest_framework import serializers

from apps.products.scoring_helpers import score_fields, score_product
from apps.products.serializers import ProductSerializer

from .models import Scan


class ScanSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Scan
        fields = ["id", "product", "score", "label", "diabetic_risk", "flags", "scanned_at"]

    def to_representation(self, instance):
        """History shows the product's CURRENT verdict, not the one saved when the
        scan happened, and the personal verdict for the user who owns the scan.
        Products get corrected over time (nutrition added, copied from a matching
        product, a scoring fix), and a list that still showed an old "Good 10/10"
        for a product we now know is incomplete would mislead."""
        data = super().to_representation(instance)
        product = instance.product
        if product.product_type != "food":
            return data
        data.update(score_fields(instance.user, product, score_product(product)))
        return data
