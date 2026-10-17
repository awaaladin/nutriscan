from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.community.models import ProductReport
from apps.community.services import integrity_dict
from apps.integrations.product_qa import (
    MAX_HISTORY_TURNS,
    MAX_QUESTION_CHARS,
    IdentifyError,
    ask_about_product,
    build_product_context,
)
from apps.scoring.engine import compute_health_score

from .barcodes import find_product_by_barcode
from .views import _nutrition_from_product

MAX_REPORTS_IN_CONTEXT = 5


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_CHARS)
    # Earlier turns of this conversation, oldest first, so follow-ups make sense.
    history = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)),
        required=False,
        max_length=MAX_HISTORY_TURNS * 2,
    )


class ProductAskView(APIView):
    """POST /api/products/<barcode>/ask/ -- the "ask about this product" screen.

    The answer comes from our own data first (score, ingredients, NAFDAC and
    authenticity status, community reports, the asker's health goals), with web
    search for the rest. Rate-limited per user because each question costs an
    AI call."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ask"

    def post(self, request, barcode):
        product = find_product_by_barcode(barcode)
        if product is None:
            return Response({"detail": "We don't have that product yet.", "reason": "unknown_product"}, status=404)
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        score = None
        if product.product_type == "food":
            result = compute_health_score(_nutrition_from_product(product), product.ingredients_text)
            score = {
                "score": result.score,
                "label": result.label.value,
                "diabetic_risk": result.diabetic_risk.value,
                "flags": result.flags,
            }
        reports = [
            {"verdict": r.verdict, "where": r.where_bought, "comment": (r.comment or "")[:200]}
            for r in ProductReport.objects.filter(product=product, is_hidden=False)[:MAX_REPORTS_IN_CONTEXT]
        ]
        user = request.user
        profile = {
            "goal": user.primary_goal,
            "diabetic": "yes" if user.is_diabetic else "no",
            "hypertension": "yes" if user.has_hypertension else "no",
        }
        context = build_product_context(product, integrity_dict(product), score, reports, profile)

        try:
            reply = ask_about_product(context, data["question"], data.get("history", []))
        except IdentifyError as exc:
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE if exc.reason == "ai_not_configured" else status.HTTP_502_BAD_GATEWAY
            )
            return Response({"detail": exc.message, "reason": exc.reason}, status=http_status)
        return Response(reply)
