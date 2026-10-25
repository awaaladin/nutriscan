"""Pro health tools. Which readings a user can log depends on their plan:
weight from Pro, blood pressure from Pro Plus, blood glucose with Pro Care."""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.vision_identify import IdentifyError
from apps.subscriptions import credits
from apps.subscriptions.credits import CreditError

from . import ai
from .models import HealthLog
from .summary import alert_for, summarize

KIND_TIER = {HealthLog.Kind.WEIGHT: "pro", HealthLog.Kind.BLOOD_PRESSURE: "plus", HealthLog.Kind.GLUCOSE: "care"}
KIND_FEATURE = {
    HealthLog.Kind.WEIGHT: "The weight tracker",
    HealthLog.Kind.BLOOD_PRESSURE: "The blood pressure tracker",
    HealthLog.Kind.GLUCOSE: "The blood sugar tracker",
}
TOOL_TIER = {"meal_plan": "plus", "progress_report": "plus", "doctor_summary": "care"}
TOOL_FEATURE = {"meal_plan": "Meal plans", "progress_report": "Weekly progress reports", "doctor_summary": "The doctor-visit summary"}
LIST_LIMIT = 120


def _error(exc: CreditError) -> Response:
    return Response(exc.as_response_data(), status=exc.status)


class HealthLogSerializer(serializers.ModelSerializer):
    alert = serializers.SerializerMethodField()

    class Meta:
        model = HealthLog
        fields = ["id", "kind", "value", "systolic", "diastolic", "timing", "note", "measured_at", "alert"]
        read_only_fields = ["id", "alert"]
        extra_kwargs = {"measured_at": {"required": False}}

    def get_alert(self, obj):
        return alert_for(obj)

    def validate(self, data):
        kind = data["kind"]
        if kind == HealthLog.Kind.BLOOD_PRESSURE:
            sys_, dia = data.get("systolic"), data.get("diastolic")
            if not sys_ or not dia or not (60 <= sys_ <= 260) or not (30 <= dia <= 160) or dia >= sys_:
                raise serializers.ValidationError("Enter blood pressure as two numbers, like 128 over 82.")
            data["value"], data["timing"] = None, ""
        else:
            value = data.get("value")
            limits = (20, 350) if kind == HealthLog.Kind.WEIGHT else (20, 600)
            if value is None or not (limits[0] <= value <= limits[1]):
                unit = "kg" if kind == HealthLog.Kind.WEIGHT else "mg/dL"
                raise serializers.ValidationError(f"Enter a value between {limits[0]} and {limits[1]} {unit}.")
            data["systolic"] = data["diastolic"] = None
            if kind == HealthLog.Kind.WEIGHT:
                data["timing"] = ""
            elif not data.get("timing"):
                data["timing"] = HealthLog.Timing.RANDOM
        if data.get("measured_at") and data["measured_at"] > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("That time is in the future.")
        return data


class HealthLogListView(APIView):
    """GET /api/health/logs/?kind=glucose -- the user's readings, newest first. POST adds one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        kind = request.query_params.get("kind")
        logs = HealthLog.objects.filter(user=request.user)
        if kind:
            logs = logs.filter(kind=kind)
        return Response(HealthLogSerializer(logs[:LIST_LIMIT], many=True).data)

    def post(self, request):
        serializer = HealthLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        try:
            credits.require_tier(request.user, KIND_TIER[kind], KIND_FEATURE[kind])
        except CreditError as exc:
            return _error(exc)
        log = serializer.save(user=request.user, measured_at=serializer.validated_data.get("measured_at") or timezone.now())
        return Response(HealthLogSerializer(log).data, status=status.HTTP_201_CREATED)


class HealthLogDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, log_id):
        get_object_or_404(HealthLog, pk=log_id, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HealthSummaryView(APIView):
    """GET /api/health/summary/ -- trends, targets and alerts, plus what the plan unlocks."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tier = credits.tier_of(request.user)
        rank = credits.TIER_RANK[tier]
        data = summarize(request.user)
        data["tier"] = tier
        data["unlocked"] = {
            **{kind: rank >= credits.TIER_RANK[t] for kind, t in KIND_TIER.items()},
            **{tool: rank >= credits.TIER_RANK[t] for tool, t in TOOL_TIER.items()},
        }
        data["height_cm"] = request.user.height_cm
        data["target_weight_kg"] = float(request.user.target_weight_kg) if request.user.target_weight_kg else None
        return Response(data)


class HealthToolSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)


class HealthToolView(APIView):
    """POST /api/health/<tool>/ -- meal_plan, progress_report or doctor_summary, written by AI."""

    permission_classes = [IsAuthenticated]

    def post(self, request, tool):
        if tool not in TOOL_TIER:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = HealthToolSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            credits.require_tier(request.user, TOOL_TIER[tool], TOOL_FEATURE[tool])
            credits.ensure_can_spend(request.user, tool)
        except CreditError as exc:
            return _error(exc)
        try:
            reply = ai.write(request.user, tool, serializer.validated_data.get("note", ""))
        except IdentifyError as exc:
            code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.reason == "ai_not_configured" else status.HTTP_502_BAD_GATEWAY
            return Response({"detail": exc.message, "reason": exc.reason}, status=code)
        credits.charge(request.user, tool, reply.get("usage"))
        return Response({
            "tool": tool,
            "text": reply["answer"],
            "created_at": timezone.now(),
            "credits_left": credits.balance(request.user)["total_remaining"],
        })
