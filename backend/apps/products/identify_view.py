from uuid import uuid4

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.community.integrity import gtin_checksum_valid
from apps.community.nafdac import normalize_nafdac_number
from apps.integrations.vision_identify import IdentifyError, identify_product_from_images
from apps.scans.models import Scan
from apps.scoring.engine import compute_health_score

from .identify_helpers import (
    copy_from_twin,
    inherit_nafdac_verification,
    product_for_nafdac,
    read_valid_photos,
)
from .models import Product
from .serializers import ProductSerializer
from .views import _get_or_create_explanation, _non_food_message, _nutrition_from_product


def scored_response(request, product: Product, *, source: str, notice: str = "") -> Response:
    """Score and record a scan of `product`. `source` says where the data came
    from so the app can tell the user: "database" (already on file, no AI
    used), "twin" (copied from a product with the same NAFDAC number) or "ai"
    (just researched from the photos)."""
    if product.product_type != Product.ProductType.FOOD:
        return Response(
            {
                "product": ProductSerializer(product).data,
                "product_type": product.product_type,
                "is_estimated": product.is_estimated,
                "source": source,
                "detail": (_non_food_message(product) + (" " + notice if notice else "")),
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
    if product.is_estimated:
        explanation += (
            " Note: these details were read from photos, not a verified label match "
            "-- double-check against the package."
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
            "is_estimated": product.is_estimated,
            "source": source,
            "explanation": explanation,
        }
    )


class IdentifyProductView(APIView):
    """Researches a product the database doesn't have, from photos of its sides.

    Order matters -- our own data first, AI only as the last resort:
      1. Barcode already on file -> return it. No AI call.
      2. NAFDAC number supplied (typed) and already on file -> copy that
         registration's details onto this barcode, inheriting its admin
         verification. No AI call.
      3. Otherwise read ALL the photos in a single AI request (front, back,
         sides together), save the product under the scanned barcode with the
         NAFDAC number the AI read off the pack, and from then on every scan of
         that barcode is answered from the database.

    Form fields: `barcode` (the camera's reading; optional), `nafdac_number`
    (optional, typed by the user), `images` (1-6 files; the app asks for at
    least 3 sides). A legacy single `image` field is still accepted.

    If no barcode is known at all, one is read from the photos (only if it
    passes the GS1 checksum, since AI misreads digits); failing that a
    synthetic AI-... key is used, so two unreadable photo sets of the same
    product create two rows rather than merging -- a known limitation.

    Errors carry `reason`, a user-facing `detail`, and `retake` (whether better
    photos could fix it) so the app can say what actually went wrong."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _error(detail, reason, http_status, barcode="", retake=False):
        return Response(
            {"detail": detail, "reason": reason, "retake": retake, "action": "submit_product", "barcode": barcode},
            status=http_status,
        )

    def post(self, request):
        client_barcode = (request.data.get("barcode") or "").strip()
        typed_nafdac_raw = (request.data.get("nafdac_number") or "").strip()
        typed_nafdac = normalize_nafdac_number(typed_nafdac_raw) if typed_nafdac_raw else None
        if typed_nafdac_raw and typed_nafdac is None:
            return self._error(
                "That doesn't look like a NAFDAC number (e.g. A4-1234). Check it and try again.",
                "bad_nafdac_number", status.HTTP_400_BAD_REQUEST, client_barcode,
            )

        # 1. Our own data first: a barcode we already have never costs an AI call.
        if client_barcode:
            existing = Product.objects.filter(barcode=client_barcode).first()
            if existing:
                return scored_response(request, existing, source="database")

        # 2. A NAFDAC number we already have on file (barcode + NAFDAC at once).
        if client_barcode and typed_nafdac:
            twin = product_for_nafdac(typed_nafdac)
            if twin:
                product = copy_from_twin(client_barcode, twin)
                return scored_response(
                    request, product, source="twin",
                    notice="(Matched by NAFDAC number to a product already in our database.)",
                )

        # 3. Research from the photos.
        uploads = request.FILES.getlist("images") or [f for f in [request.FILES.get("image")] if f]
        if not uploads:
            return self._error(
                "This product isn't in our database yet. Take photos of its sides (at least 3: "
                "front, back, and the side with the NAFDAC number) so we can research it.",
                "no_photos", status.HTTP_400_BAD_REQUEST, client_barcode, retake=True,
            )
        try:
            photos = read_valid_photos(uploads)
        except ValueError as exc:
            return self._error(str(exc), "bad_photos", status.HTTP_400_BAD_REQUEST, client_barcode, retake=True)

        try:
            result = identify_product_from_images(photos)
        except IdentifyError as exc:
            if exc.retake:
                http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
            elif exc.reason == "ai_not_configured":
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            else:
                http_status = status.HTTP_502_BAD_GATEWAY
            return self._error(exc.message, exc.reason, http_status, client_barcode, retake=exc.retake)

        ai_barcode = (result.get("barcode") or "").strip()
        barcode = client_barcode or (ai_barcode if gtin_checksum_valid(ai_barcode) else "") or f"AI-{uuid4().hex[:12]}"

        # The AI may have read a barcode we already hold (the camera never did).
        existing = Product.objects.filter(barcode=barcode).first()
        if existing:
            return scored_response(request, existing, source="database")

        nafdac = normalize_nafdac_number(result.get("nafdac_number")) or typed_nafdac or ""
        product = Product.objects.create(
            barcode=barcode,
            name=result.get("name") or "Unidentified product",
            brand=result.get("brand", ""),
            source=Product.Source.AI_VISION,
            product_type=result.get("product_type", "food"),
            is_estimated=True,
            nafdac_number=nafdac,
            ingredients_text=result.get("ingredients_text", ""),
            calories_kcal=result.get("calories_kcal"),
            sugar_g=result.get("sugar_g"),
            saturated_fat_g=result.get("saturated_fat_g"),
            sodium_mg=result.get("sodium_mg"),
            carbohydrates_g=result.get("carbohydrates_g"),
            fiber_g=result.get("fiber_g"),
            protein_g=result.get("protein_g"),
        )
        inherit_nafdac_verification(product)
        return scored_response(
            request, product, source="ai",
            notice="(Researched from your photos and saved, so the next scan of this barcode is instant.)",
        )
