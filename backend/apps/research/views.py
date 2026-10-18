import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.community.nafdac import normalize_nafdac_number
from apps.products.barcodes import barcode_variants, find_product_by_barcode
from apps.products.models import Product
from apps.products.scoring_helpers import score_fields, score_product
from apps.products.serializers import ProductSerializer

from . import corrections
from .agent import research_product
from .trust import data_trust

RESEARCH_COOLDOWN = timedelta(hours=24)
SEARCH_LIMIT = 20


def _not_found():
    return Response({"detail": "We don't have that product yet.", "reason": "unknown_product"}, status=status.HTTP_404_NOT_FOUND)


class ResearchView(APIView):
    """POST /api/products/<barcode>/research/ -- cross-check a product against other
    sources and return its updated, scored record (no new scan is recorded).

    Cached for 24 hours per product, so opening an unverified product repeatedly
    doesn't repeat the work."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "research"

    def post(self, request, barcode):
        product = find_product_by_barcode(barcode)
        if product is None:
            return _not_found()
        last = product.research_runs.first()
        ran = last is None or timezone.now() - last.created_at >= RESEARCH_COOLDOWN
        outcome = research_product(product) if ran else {"applied": [], "conflicts": [], "skipped": ["Researched recently."]}
        product.refresh_from_db()
        return Response(
            {
                "product": ProductSerializer(product).data,
                **score_fields(request.user, product, score_product(product)),
                "is_estimated": product.is_estimated,
                "source": "database",
                "research": {
                    "ran": ran,
                    "applied": outcome["applied"],
                    "conflicts": outcome["conflicts"],
                    "skipped": outcome["skipped"],
                },
            }
        )


class CorrectionSerializer(serializers.Serializer):
    field = serializers.CharField(max_length=32)
    value = serializers.CharField(max_length=3000)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)


class CorrectionView(APIView):
    """POST /api/products/<barcode>/corrections/ -- tell us a value is wrong.

    It is a vote: applied only once enough credible, independent people agree."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "corrections"

    def post(self, request, barcode):
        product = find_product_by_barcode(barcode)
        if product is None:
            return _not_found()
        serializer = CorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            correction, applied = corrections.submit(request.user, product, data["field"], data["value"], data.get("reason", ""))
        except ValueError as exc:
            return Response({"detail": str(exc), "reason": "bad_correction"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "applied": applied,
                "detail": (
                    "Thanks -- people and an independent source agreed, so the data has been updated."
                    if applied
                    else "Thanks. We check every report against independent sources or our team before changing anything."
                ),
                "trust": data_trust(product),
            },
            status=status.HTTP_201_CREATED,
        )


class SearchView(APIView):
    """GET /api/products/search/?q= -- find products in our own data set by name,
    brand, barcode or NAFDAC number, each with how far its data can be trusted."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"detail": "Type at least 2 characters.", "reason": "query_too_short"}, status=status.HTTP_400_BAD_REQUEST)

        found = {}
        for variant in barcode_variants(query):
            for product in Product.objects.filter(barcode=variant):
                found[product.pk] = (100.0, product)
        nafdac = normalize_nafdac_number(query)
        if nafdac:
            for product in Product.objects.filter(nafdac_number=nafdac):
                found.setdefault(product.pk, (90.0, product))

        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 2]
        if words:
            condition = Q()
            for word in words:
                condition |= Q(name__icontains=word) | Q(brand__icontains=word)
            for product in Product.objects.filter(condition)[:200]:
                haystack = f"{product.name} {product.brand}".lower()
                hits = sum(1 for w in words if w in haystack)
                if hits * 2 >= len(words):  # at least half of what was typed matches
                    found.setdefault(product.pk, (hits / len(words) * 80, product))

        ranked = sorted(found.values(), key=lambda t: (-t[0], t[1].name))[:SEARCH_LIMIT]
        results = []
        for _, product in ranked:
            trust = data_trust(product)
            row = {
                "barcode": product.barcode,
                "name": product.name,
                "brand": product.brand,
                "nafdac_number": product.nafdac_number,
                "product_type": product.product_type,
                "trust": {"level": trust["level"], "headline": trust["headline"]},
            }
            if product.product_type == Product.ProductType.FOOD:
                result = score_product(product)
                row.update(label=result.label.value, score=result.score, diabetic_risk=result.diabetic_risk.value)
            results.append(row)
        return Response({"query": query, "results": results})
