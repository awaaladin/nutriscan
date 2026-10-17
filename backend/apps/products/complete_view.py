from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.community.nafdac import normalize_nafdac_number
from apps.integrations.vision_identify import IdentifyError, extract_nutrition_from_images

from .barcodes import find_product_by_barcode
from .identify_helpers import MAX_PHOTOS, inherit_nafdac_verification, read_valid_photos
from .identify_view import scored_response
from .nutrition_input import LIMITS, NutritionInputError, clean_nutrition, per_100g

# What can be filled in. Existing values are never overwritten.
_NUMERIC_FIELDS = tuple(LIMITS)


class CompleteSerializer(serializers.Serializer):
    calories_kcal = serializers.FloatField(required=False, allow_null=True)
    sugar_g = serializers.FloatField(required=False, allow_null=True)
    saturated_fat_g = serializers.FloatField(required=False, allow_null=True)
    sodium_mg = serializers.FloatField(required=False, allow_null=True)
    carbohydrates_g = serializers.FloatField(required=False, allow_null=True)
    fiber_g = serializers.FloatField(required=False, allow_null=True)
    protein_g = serializers.FloatField(required=False, allow_null=True)
    ingredients_text = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    nafdac_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
    # Labels usually list values per serving; these convert them to per 100g.
    per_serving = serializers.BooleanField(required=False, default=False)
    serving_size_g = serializers.FloatField(required=False, allow_null=True)


class CompleteProductView(APIView):
    """POST /api/products/<barcode>/complete/ -- fill in a product's missing
    nutrition so it can finally be scored.

    Accepts a photo of the nutrition table (`images`, read by AI), typed values,
    or both (typed values win over what the AI read). Rules that keep this safe,
    since the result changes the score everyone sees:
      - only blanks are filled; nothing already on file is overwritten
      - values are range-checked, converted from per-serving if asked, and
        cross-checked (sugar can't exceed carbohydrates)
      - the product is marked estimated, so the app discloses it
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @staticmethod
    def _error(detail, reason, http_status, retake=False):
        return Response({"detail": detail, "reason": reason, "retake": retake}, status=http_status)

    def post(self, request, barcode):
        product = find_product_by_barcode(barcode)
        if product is None:
            return self._error("We don't have that product yet.", "unknown_product", status.HTTP_404_NOT_FOUND)

        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        typed = {k: data.get(k) for k in _NUMERIC_FIELDS if data.get(k) is not None}
        try:
            if typed and data.get("per_serving"):
                typed = per_100g(typed, data.get("serving_size_g"))
            typed = clean_nutrition(typed, strict=True)
        except NutritionInputError as exc:
            return self._error(str(exc), "bad_values", status.HTTP_400_BAD_REQUEST)

        uploads = request.FILES.getlist("images")
        from_photo, photo_ingredients, photo_nafdac = {}, "", None
        if uploads:
            try:
                photos = read_valid_photos(uploads[:MAX_PHOTOS])
            except ValueError as exc:
                return self._error(str(exc), "bad_photos", status.HTTP_400_BAD_REQUEST, retake=True)
            try:
                result = extract_nutrition_from_images(photos)
            except IdentifyError as exc:
                if exc.retake:
                    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
                elif exc.reason == "ai_not_configured":
                    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
                else:
                    http_status = status.HTTP_502_BAD_GATEWAY
                # A typed fallback may still be enough to complete the product.
                if not typed:
                    return self._error(exc.message, exc.reason, http_status, retake=exc.retake)
            else:
                from_photo = clean_nutrition({k: result.get(k) for k in _NUMERIC_FIELDS}, strict=False)
                photo_ingredients = (result.get("ingredients_text") or "").strip()
                photo_nafdac = normalize_nafdac_number(result.get("nafdac_number"))

        ingredients = (data.get("ingredients_text") or "").strip() or photo_ingredients
        nafdac = normalize_nafdac_number(data.get("nafdac_number")) or photo_nafdac
        merged = {**from_photo, **typed}  # what the user typed wins over what the AI read

        if not merged and not ingredients:
            return self._error(
                "Send a photo of the nutrition table, or type at least one value.",
                "nothing_to_add", status.HTTP_400_BAD_REQUEST,
            )

        filled = []
        for field, value in merged.items():
            if getattr(product, field) is None:  # never overwrite what we already hold
                setattr(product, field, value)
                filled.append(field)
        if ingredients and not product.ingredients_text.strip():
            product.ingredients_text = ingredients
            filled.append("ingredients_text")
        if nafdac and not product.nafdac_number:
            product.nafdac_number = nafdac
            filled.append("nafdac_number")

        if filled:
            product.is_estimated = True  # part of this record is now user/AI supplied
            product.save()
            inherit_nafdac_verification(product)

        return scored_response(
            request,
            product,
            source="completed",
            notice="(Nutrition details added to this product.)" if filled else "",
        )
