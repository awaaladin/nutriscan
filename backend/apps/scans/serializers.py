from rest_framework import serializers

from apps.products.serializers import ProductSerializer
from apps.scoring.engine import NutritionFacts, compute_health_score

from .models import Scan


class ScanSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Scan
        fields = ["id", "product", "score", "label", "diabetic_risk", "flags", "scanned_at"]

    def to_representation(self, instance):
        """History shows the product's CURRENT verdict, not the one saved when the
        scan happened. Products get corrected over time (nutrition added, copied
        from a matching product, a scoring fix), and a list that still showed an
        old "Good 10/10" for a product we now know is incomplete would mislead."""
        data = super().to_representation(instance)
        product = instance.product
        if product.product_type != "food":
            return data
        result = compute_health_score(
            NutritionFacts(
                calories_kcal=product.calories_kcal,
                sugar_g=product.sugar_g,
                saturated_fat_g=product.saturated_fat_g,
                sodium_mg=product.sodium_mg,
                carbohydrates_g=product.carbohydrates_g,
                fiber_g=product.fiber_g,
                protein_g=product.protein_g,
            ),
            product.ingredients_text,
        )
        data.update(
            score=result.score,  # None when there is no honest number
            label=result.label.value,
            diabetic_risk=result.diabetic_risk.value,
            flags=result.flags,
        )
        return data
