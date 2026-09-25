from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.llm_explanations import get_explanation_provider
from apps.integrations.open_food_facts import OpenFoodFactsClient
from apps.scans.models import Scan
from apps.scoring.engine import HealthScoreResult, NutritionFacts, compute_health_score

from .models import CachedExplanation, Product
from .serializers import (
    AnalyzeRequestSerializer,
    ProductSerializer,
    ProductSubmissionSerializer,
    ScanRequestSerializer,
)


def _nutrition_from_product(product: Product) -> NutritionFacts:
    return NutritionFacts(
        calories_kcal=product.calories_kcal,
        sugar_g=product.sugar_g,
        saturated_fat_g=product.saturated_fat_g,
        sodium_mg=product.sodium_mg,
        carbohydrates_g=product.carbohydrates_g,
        fiber_g=product.fiber_g,
        protein_g=product.protein_g,
    )


def _get_or_create_explanation(product: Product, result: HealthScoreResult) -> str:
    cached = CachedExplanation.objects.filter(
        product=product,
        score=result.score,
        label=result.label.value,
        diabetic_risk=result.diabetic_risk.value,
    ).first()
    if cached:
        return cached.explanation_text

    explanation = get_explanation_provider().explain(
        product_name=product.name,
        score=result.score,
        label=result.label.value,
        diabetic_risk=result.diabetic_risk.value,
        flags=result.flags,
    )
    CachedExplanation.objects.create(
        product=product,
        score=result.score,
        label=result.label.value,
        diabetic_risk=result.diabetic_risk.value,
        explanation_text=explanation,
    )
    return explanation


class ScanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barcode = serializer.validated_data["barcode"]

        product = Product.objects.filter(barcode=barcode).first()
        if product is None:
            off_data = OpenFoodFactsClient().fetch_product(barcode)
            if off_data is None:
                return Response(
                    {
                        "detail": "Product not found.",
                        "action": "submit_product",
                        "barcode": barcode,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            product = Product.objects.create(
                barcode=barcode, source=Product.Source.OPEN_FOOD_FACTS, **off_data
            )

        result = compute_health_score(_nutrition_from_product(product), product.ingredients_text)
        explanation = _get_or_create_explanation(product, result)

        scan = Scan.objects.create(
            user=request.user,
            product=product,
            score=result.score,
            label=result.label.value,
            diabetic_risk=result.diabetic_risk.value,
            flags=result.flags,
        )

        return Response(
            {
                "scan_id": scan.id,
                "product": ProductSerializer(product).data,
                "score": result.score,
                "label": result.label.value,
                "diabetic_risk": result.diabetic_risk.value,
                "flags": result.flags,
                "insufficient_data": result.insufficient_data,
                "explanation": explanation,
            }
        )


class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, barcode):
        product = get_object_or_404(Product, barcode=barcode)
        return Response(ProductSerializer(product).data)


class ProductSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProductSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(submitted_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AnalyzeView(APIView):
    """Score a raw nutrition payload without requiring a stored Product,
    e.g. for a manually-entered label the client hasn't submitted yet."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        nutrition = NutritionFacts(
            calories_kcal=data.get("calories_kcal"),
            sugar_g=data.get("sugar_g"),
            saturated_fat_g=data.get("saturated_fat_g"),
            sodium_mg=data.get("sodium_mg"),
            carbohydrates_g=data.get("carbohydrates_g"),
            fiber_g=data.get("fiber_g"),
            protein_g=data.get("protein_g"),
        )
        result = compute_health_score(nutrition, data.get("ingredients_text", ""))

        return Response(
            {
                "score": result.score,
                "label": result.label.value,
                "diabetic_risk": result.diabetic_risk.value,
                "flags": result.flags,
                "insufficient_data": result.insufficient_data,
            }
        )
