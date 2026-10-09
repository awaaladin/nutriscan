from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.llm_explanations import get_explanation_provider
from apps.integrations.open_food_facts import OpenFoodFactsClient
from apps.integrations.vision_identify import identify_product_from_image
from apps.scans.models import Scan
from apps.scoring.engine import HealthScoreResult, NutritionFacts, compute_health_score

from .medicine_names import is_known_medicine_name
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


def _non_food_message(product: Product) -> str:
    if product.product_type == Product.ProductType.MEDICINE:
        return (
            f"{product.name} looks like a medicine, not a packaged food. NutriScan scores "
            "food nutrition against WHO thresholds and can't assess drug dosage or safety -- "
            "please check the package insert or ask a pharmacist."
        )
    return f"{product.name} doesn't look like a packaged food, so a WHO health score doesn't apply here."


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

        if product.product_type != Product.ProductType.FOOD:
            # WHO scoring assumes a nutrition label; applying it to a drug or
            # other non-food item would look like dosage/safety advice, so
            # skip scoring entirely and tell the user plainly what this is.
            return Response(
                {
                    "product": ProductSerializer(product).data,
                    "product_type": product.product_type,
                    "detail": _non_food_message(product),
                }
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
        data = serializer.validated_data

        if is_known_medicine_name(data["name"]):
            # No barcode database exists for Nigerian pharmaceuticals, so a
            # name match is the only signal available. Skip the community
            # food-review queue entirely -- there's no nutrition data to
            # review for a drug -- and make the barcode recognizable the
            # moment anyone scans it again.
            product, _ = Product.objects.update_or_create(
                barcode=data["barcode"],
                defaults={
                    "name": data["name"],
                    "brand": data.get("brand", ""),
                    "source": Product.Source.COMMUNITY,
                    "product_type": Product.ProductType.MEDICINE,
                },
            )
            return Response(
                {
                    "product": ProductSerializer(product).data,
                    "product_type": product.product_type,
                    "detail": _non_food_message(product),
                },
                status=status.HTTP_201_CREATED,
            )

        serializer.save(submitted_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IdentifyProductView(APIView):
    """Fallback when a barcode isn't in Open Food Facts or our local table:
    identify the product from a photo of it instead (see
    apps.integrations.vision_identify). Best-effort -- results are marked
    is_estimated so the client can disclose that the nutrition numbers came
    from Gemini reading the label photo, not a verified source."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        barcode = request.data.get("barcode", "")
        image = request.FILES.get("image")
        if not barcode or not image:
            return Response({"detail": "barcode and image are required."}, status=status.HTTP_400_BAD_REQUEST)

        result = identify_product_from_image(image.read(), image.content_type or "image/jpeg")
        if result is None:
            return Response(
                {
                    "detail": "Couldn't identify this product from the photo.",
                    "action": "submit_product",
                    "barcode": barcode,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        product_type = result.get("product_type", "food")
        product, _ = Product.objects.update_or_create(
            barcode=barcode,
            defaults={
                "name": result.get("name") or "Unidentified product",
                "brand": result.get("brand", ""),
                "source": Product.Source.AI_VISION,
                "product_type": product_type,
                "is_estimated": True,
                "ingredients_text": result.get("ingredients_text", ""),
                "calories_kcal": result.get("calories_kcal"),
                "sugar_g": result.get("sugar_g"),
                "saturated_fat_g": result.get("saturated_fat_g"),
                "sodium_mg": result.get("sodium_mg"),
                "carbohydrates_g": result.get("carbohydrates_g"),
                "fiber_g": result.get("fiber_g"),
                "protein_g": result.get("protein_g"),
            },
        )

        if product.product_type != Product.ProductType.FOOD:
            return Response(
                {
                    "product": ProductSerializer(product).data,
                    "product_type": product.product_type,
                    "is_estimated": True,
                    "detail": _non_food_message(product) + " (Identified from photo, not a scanned barcode match.)",
                }
            )

        health_result = compute_health_score(_nutrition_from_product(product), product.ingredients_text)
        explanation = _get_or_create_explanation(product, health_result)

        scan = Scan.objects.create(
            user=request.user,
            product=product,
            score=health_result.score,
            label=health_result.label.value,
            diabetic_risk=health_result.diabetic_risk.value,
            flags=health_result.flags,
        )

        return Response(
            {
                "scan_id": scan.id,
                "product": ProductSerializer(product).data,
                "score": health_result.score,
                "label": health_result.label.value,
                "diabetic_risk": health_result.diabetic_risk.value,
                "flags": health_result.flags,
                "insufficient_data": health_result.insufficient_data,
                "is_estimated": True,
                "explanation": explanation + " Note: this was read from a photo, not a verified nutrition label match -- double-check against the package.",
            }
        )


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
